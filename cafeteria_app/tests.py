from datetime import datetime, time, timedelta, timezone as datetime_timezone
from unittest.mock import patch

from django.conf import settings
from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .admin import DetallePedidoInline, PedidoAdmin
from .models import Categoria, DetallePedido, Pedido, Producto


class CatalogoCarritoTests(TestCase):
    def setUp(self):
        self.cliente = get_user_model().objects.create_user(
            username="cliente_catalogo",
            password="demo12345",
        )
        self.bebidas = Categoria.objects.create(nombre="Bebidas", descripcion="Bebidas")
        self.pasteleria = Categoria.objects.create(
            nombre="Pastelería",
            descripcion="Dulces",
            activa=False,
        )
        self.cafe = Producto.objects.create(
            categoria=self.bebidas,
            codigo="CAF001",
            nombre="Café americano",
            precio=1500,
            stock=2,
        )
        self.agotado = Producto.objects.create(
            categoria=self.bebidas,
            codigo="CAF002",
            nombre="Café frío",
            precio=1800,
            stock=0,
        )
        self.no_disponible = Producto.objects.create(
            categoria=self.bebidas,
            codigo="CAF003",
            nombre="Café de temporada",
            precio=2000,
            stock=5,
            disponible=False,
        )
        self.categoria_inactiva = Producto.objects.create(
            categoria=self.pasteleria,
            codigo="PAS001",
            nombre="Queque",
            precio=1200,
            stock=5,
        )
        self.client.force_login(self.cliente)

    def test_catalogo_incluye_agotados_pero_excluye_no_disponibles_y_categoria_inactiva(self):
        respuesta = self.client.get(reverse("cafeteria_app:lista_productos"))

        self.assertContains(respuesta, self.cafe.nombre)
        self.assertContains(respuesta, self.agotado.nombre)
        self.assertContains(respuesta, "Agotado")
        self.assertNotContains(respuesta, self.no_disponible.nombre)
        self.assertNotContains(respuesta, self.categoria_inactiva.nombre)
        self.assertContains(respuesta, "$1.500")
        self.assertNotContains(
            respuesta,
            reverse("cafeteria_app:agregar_al_carrito", args=[self.agotado.pk]),
        )

    def test_busqueda_por_nombre_y_filtro_de_categoria_se_combinan(self):
        te = Producto.objects.create(
            categoria=self.bebidas,
            codigo="BEB001",
            nombre="Té helado",
            precio=1000,
            stock=4,
        )

        respuesta = self.client.get(
            reverse("cafeteria_app:lista_productos"),
            {"q": "aMeRiCaNo", "categoria": self.bebidas.pk},
        )

        self.assertContains(respuesta, self.cafe.nombre)
        self.assertNotContains(respuesta, self.agotado.nombre)
        self.assertNotContains(respuesta, te.nombre)
        self.assertNotContains(respuesta, self.categoria_inactiva.nombre)

    def test_agregar_al_carrito_valida_stock_y_limita_cantidad(self):
        url = reverse("cafeteria_app:agregar_al_carrito", args=[self.cafe.pk])

        self.assertRedirects(self.client.post(url), reverse("cafeteria_app:ver_carrito"))
        self.assertRedirects(self.client.post(url), reverse("cafeteria_app:ver_carrito"))
        self.assertRedirects(self.client.post(url), reverse("cafeteria_app:lista_productos"))
        self.assertEqual(self.client.session["carrito"], {str(self.cafe.pk): 2})

    def test_producto_agotado_no_se_puede_agregar_al_carrito(self):
        url = reverse("cafeteria_app:agregar_al_carrito", args=[self.agotado.pk])
        respuesta = self.client.post(url)

        self.assertRedirects(respuesta, reverse("cafeteria_app:lista_productos"))
        self.assertNotIn(str(self.agotado.pk), self.client.session.get("carrito", {}))

    def test_producto_no_disponible_no_se_puede_agregar_al_carrito(self):
        url = reverse("cafeteria_app:agregar_al_carrito", args=[self.no_disponible.pk])

        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertNotIn(str(self.no_disponible.pk), self.client.session.get("carrito", {}))

    def test_carrito_muestra_subtotal_en_pesos_chilenos(self):
        self.client.post(reverse("cafeteria_app:agregar_al_carrito", args=[self.cafe.pk]))
        respuesta = self.client.get(reverse("cafeteria_app:ver_carrito"))

        self.assertContains(respuesta, "$1.500")


class CarritoPedidosTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.cliente = user_model.objects.create_user(username="comprador", password="demo12345")
        self.otro_cliente = user_model.objects.create_user(username="otro_comprador")
        self.encargado = user_model.objects.create_user(
            username="encargado_pedidos",
            password="demo12345",
            is_staff=True,
        )
        self.categoria = Categoria.objects.create(nombre="Colaciones", descripcion="Comidas")
        self.producto = Producto.objects.create(
            categoria=self.categoria,
            codigo="COL001",
            nombre="Sándwich",
            precio=1200,
            stock=20,
        )
        self.otro_producto = Producto.objects.create(
            categoria=self.categoria,
            codigo="COL002",
            nombre="Jugo",
            precio=800,
            stock=1,
        )
        self.client.force_login(self.cliente)

    def poner_carrito(self, carrito):
        session = self.client.session
        session["carrito"] = {str(producto_id): cantidad for producto_id, cantidad in carrito.items()}
        session.save()

    def checkout(self, cantidades, hora="11:00"):
        self.poner_carrito(cantidades)
        return self.client.post(
            reverse("cafeteria_app:confirmar_pedido"),
            {"hora_retiro": hora},
        )

    def test_agrega_actualiza_quita_y_vacia_carrito(self):
        agregar = reverse("cafeteria_app:agregar_al_carrito", args=[self.producto.pk])
        for _ in range(10):
            self.client.post(agregar)
        self.client.post(agregar)
        self.assertEqual(self.client.session["carrito"], {str(self.producto.pk): 10})

        actualizar = reverse(
            "cafeteria_app:actualizar_cantidad_carrito",
            args=[self.producto.pk],
        )
        self.client.post(actualizar, {"cantidad": 5})
        self.assertEqual(self.client.session["carrito"], {str(self.producto.pk): 5})
        self.client.post(actualizar, {"cantidad": 11})
        self.assertEqual(self.client.session["carrito"], {str(self.producto.pk): 5})
        self.producto.stock = 4
        self.producto.save(update_fields=["stock"])
        self.client.post(actualizar, {"cantidad": 5})
        self.assertEqual(self.client.session["carrito"], {str(self.producto.pk): 5})

        quitar = reverse("cafeteria_app:quitar_del_carrito", args=[self.producto.pk])
        self.client.post(quitar)
        self.assertEqual(self.client.session["carrito"], {})

        self.client.post(agregar)
        self.client.post(reverse("cafeteria_app:vaciar_carrito"))
        self.assertEqual(self.client.session.get("carrito", {}), {})

    def test_contador_del_carrito_aparece_en_el_menu(self):
        self.poner_carrito({self.producto.pk: 2, self.otro_producto.pk: 1})
        respuesta = self.client.get(reverse("cafeteria_app:inicio"))

        self.assertContains(respuesta, "Carrito (3)")

    def test_pedido_guarda_precio_total_descuenta_stock_y_vacia_carrito(self):
        hora_fija = datetime(2026, 1, 1, 10, 0, tzinfo=datetime_timezone.utc)
        with patch("django.utils.timezone.localtime", return_value=hora_fija):
            respuesta = self.checkout(
                {self.producto.pk: 2, self.otro_producto.pk: 1},
                "11:00",
            )

        pedido = Pedido.objects.get()
        self.assertRedirects(
            respuesta,
            reverse("cafeteria_app:detalle_pedido", args=[pedido.pk]),
        )
        self.assertEqual(pedido.estado, "pendiente")
        self.assertEqual(pedido.total, 3200)
        detalles = {detalle.producto_id: detalle for detalle in pedido.detalles.all()}
        self.assertEqual(detalles[self.producto.pk].precio_unitario, 1200)
        self.assertEqual(detalles[self.producto.pk].subtotal, 2400)
        self.assertEqual(detalles[self.otro_producto.pk].precio_unitario, 800)
        self.producto.refresh_from_db()
        self.otro_producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 18)
        self.assertEqual(self.otro_producto.stock, 0)
        self.assertEqual(self.client.session.get("carrito", {}), {})

    def test_retiro_pasado_no_crea_pedido_ni_descuenta_stock(self):
        hora_fija = datetime(2026, 1, 1, 10, 0, tzinfo=datetime_timezone.utc)
        with patch("django.utils.timezone.localtime", return_value=hora_fija):
            respuesta = self.checkout({self.producto.pk: 2}, "09:59")

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(Pedido.objects.count(), 0)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 20)
        self.assertEqual(self.client.session["carrito"], {str(self.producto.pk): 2})

    def test_checkout_con_stock_insuficiente_es_todo_o_nada(self):
        hora_fija = datetime(2026, 1, 1, 10, 0, tzinfo=datetime_timezone.utc)
        with patch("django.utils.timezone.localtime", return_value=hora_fija):
            respuesta = self.checkout(
                {self.producto.pk: 2, self.otro_producto.pk: 2},
                "11:00",
            )

        self.assertRedirects(respuesta, reverse("cafeteria_app:ver_carrito"))
        self.assertEqual(Pedido.objects.count(), 0)
        self.producto.refresh_from_db()
        self.otro_producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 20)
        self.assertEqual(self.otro_producto.stock, 1)
        self.assertEqual(
            self.client.session["carrito"],
            {str(self.producto.pk): 2, str(self.otro_producto.pk): 2},
        )

    def test_cancelar_pedido_pendiente_repone_stock_solo_una_vez(self):
        self.producto.stock -= 2
        self.producto.save(update_fields=["stock"])
        pedido = Pedido.objects.create(
            cliente=self.cliente,
            hora_retiro=time(11, 0),
            total=2400,
        )
        DetallePedido.objects.create(
            pedido=pedido,
            producto=self.producto,
            cantidad=2,
            precio_unitario=1200,
            subtotal=2400,
        )
        url = reverse("cafeteria_app:cancelar_pedido", args=[pedido.pk])

        self.assertRedirects(self.client.post(url), reverse("cafeteria_app:detalle_pedido", args=[pedido.pk]))
        pedido.refresh_from_db()
        self.producto.refresh_from_db()
        self.assertEqual(pedido.estado, "cancelado")
        self.assertEqual(self.producto.stock, 20)
        self.client.post(url)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 20)

    def test_cliente_no_cancela_pedidos_ajenos_o_no_pendientes(self):
        pedido_ajeno = Pedido.objects.create(
            cliente=self.otro_cliente,
            hora_retiro=time(11, 0),
        )
        url_ajeno = reverse("cafeteria_app:cancelar_pedido", args=[pedido_ajeno.pk])
        self.assertEqual(self.client.post(url_ajeno).status_code, 404)

        pedido = Pedido.objects.create(
            cliente=self.cliente,
            hora_retiro=time(11, 0),
            estado="preparando",
        )
        url = reverse("cafeteria_app:cancelar_pedido", args=[pedido.pk])
        self.client.post(url)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, "preparando")

    def test_encargado_avanza_estados_en_orden(self):
        pedido = Pedido.objects.create(
            cliente=self.cliente,
            hora_retiro=time(11, 0),
        )
        url = reverse("cafeteria_app:avanzar_estado_pedido", args=[pedido.pk])

        for indice, estado in enumerate(("preparando", "listo", "entregado")):
            self.client.force_login(self.encargado)
            intento = {"estado": "entregado" if indice == 0 else "pendiente"}
            respuesta = self.client.post(url, intento)
            self.assertRedirects(respuesta, reverse("cafeteria_app:gestionar_pedidos"))
            pedido.refresh_from_db()
            self.assertEqual(pedido.estado, estado)

        self.client.post(url)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, "entregado")

    def test_encargado_ve_pedidos_del_dia_y_filtra_por_estado(self):
        pendiente = Pedido.objects.create(
            cliente=self.cliente,
            hora_retiro=time(11, 0),
        )
        preparando = Pedido.objects.create(
            cliente=self.otro_cliente,
            hora_retiro=time(11, 30),
            estado="preparando",
        )
        antiguo = Pedido.objects.create(
            cliente=self.cliente,
            hora_retiro=time(12, 0),
        )
        Pedido.objects.filter(pk=antiguo.pk).update(
            fecha=timezone.now() - timedelta(days=2)
        )
        self.client.force_login(self.encargado)

        respuesta = self.client.get(reverse("cafeteria_app:gestionar_pedidos"))
        self.assertContains(respuesta, f"Pedido #{pendiente.pk}")
        self.assertContains(respuesta, f"Pedido #{preparando.pk}")
        self.assertNotContains(respuesta, f"Pedido #{antiguo.pk}")

        respuesta = self.client.get(
            reverse("cafeteria_app:gestionar_pedidos"),
            {"estado": "pendiente"},
        )
        self.assertContains(respuesta, f"Pedido #{pendiente.pk}")
        self.assertNotContains(respuesta, f"Pedido #{preparando.pk}")
        self.assertNotContains(respuesta, f"Pedido #{antiguo.pk}")


class ModeloCafeteriaTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.cliente = user_model.objects.create_user(
            username="cliente",
            password="prueba-segura-123",
        )
        self.categoria = Categoria.objects.create(nombre="Bebidas", descripcion="Bebidas")
        self.producto = Producto.objects.create(
            categoria=self.categoria,
            codigo="BEB001",
            nombre="Café",
            precio=1500,
            stock=10,
        )
        self.pedido = Pedido.objects.create(
            cliente=self.cliente,
            hora_retiro=time(10, 30),
            total=1500,
        )

    def test_categoria_con_productos_no_se_puede_eliminar(self):
        with self.assertRaises(ProtectedError):
            self.categoria.delete()

    def test_producto_en_pedido_no_se_puede_eliminar(self):
        DetallePedido.objects.create(
            pedido=self.pedido,
            producto=self.producto,
            cantidad=1,
            precio_unitario=1500,
            subtotal=1500,
        )

        with self.assertRaises(ProtectedError):
            self.producto.delete()

    def test_detalle_no_admite_producto_repetido_en_el_mismo_pedido(self):
        DetallePedido.objects.create(
            pedido=self.pedido,
            producto=self.producto,
            cantidad=1,
            precio_unitario=1500,
            subtotal=1500,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            DetallePedido.objects.create(
                pedido=self.pedido,
                producto=self.producto,
                cantidad=2,
                precio_unitario=1500,
                subtotal=3000,
            )

    def test_pedido_admin_muestra_sus_detalles_en_linea(self):
        self.assertIn(Pedido, site._registry)
        self.assertIn(DetallePedidoInline, PedidoAdmin.inlines)

    def test_comando_carga_datos_demo_y_es_repetible(self):
        call_command("cargar_datos_demo", verbosity=0)
        call_command("cargar_datos_demo", verbosity=0)

        self.assertEqual(Categoria.objects.count(), 5)
        self.assertEqual(Producto.objects.count(), 25)
        self.assertTrue(Producto.objects.filter(stock=0).exists())
        self.assertTrue(Producto.objects.filter(disponible=False).exists())

        user_model = get_user_model()
        self.assertTrue(user_model.objects.get(username="encargado").is_staff)
        self.assertTrue(user_model.objects.filter(username__in=["cliente1", "cliente2"]).count() == 2)


class RutasCafeteriaTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.cliente = user_model.objects.create_user(username="cliente", password="demo12345")
        self.otro_cliente = user_model.objects.create_user(
            username="otro",
            password="demo12345",
        )
        self.categoria = Categoria.objects.create(nombre="Bebidas", descripcion="Bebidas")
        self.producto = Producto.objects.create(
            categoria=self.categoria,
            codigo="BEB001",
            nombre="Café",
            precio=1500,
            stock=5,
        )
        self.pedido = Pedido.objects.create(
            cliente=self.cliente,
            hora_retiro=time(10, 30),
            total=1500,
        )

    def test_inicio_y_catalogo_cargan(self):
        self.client.force_login(self.cliente)
        self.assertEqual(self.client.get(reverse("cafeteria_app:inicio")).status_code, 200)
        respuesta = self.client.get(reverse("cafeteria_app:lista_productos"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.producto.nombre)

    def test_todas_las_paginas_requieren_autenticacion(self):
        rutas = (
            reverse("cafeteria_app:inicio"),
            reverse("cafeteria_app:lista_productos"),
            reverse("cafeteria_app:lista_pedidos"),
            reverse("cafeteria_app:detalle_pedido", args=[self.pedido.pk]),
            reverse("cafeteria_app:panel_encargado"),
            reverse("cafeteria_app:gestionar_pedidos"),
        )

        for ruta in rutas:
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)
                self.assertRedirects(
                    respuesta,
                    f"{reverse('cafeteria_app:login')}?next={ruta}",
                )

    def test_cliente_no_accede_a_funciones_del_encargado(self):
        self.client.force_login(self.cliente)
        respuesta = self.client.get(reverse("cafeteria_app:panel_encargado"))
        respuesta_pedidos = self.client.get(reverse("cafeteria_app:gestionar_pedidos"))

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta_pedidos.status_code, 403)

    def test_encargado_no_accede_a_funciones_del_cliente(self):
        encargado = get_user_model().objects.create_user(
            username="encargado",
            password="demo12345",
            is_staff=True,
        )
        self.client.force_login(encargado)

        for ruta in (
            reverse("cafeteria_app:inicio"),
            reverse("cafeteria_app:lista_productos"),
            reverse("cafeteria_app:lista_pedidos"),
        ):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 403)

    def test_login_y_logout_separan_roles(self):
        encargado = get_user_model().objects.create_user(
            username="encargado",
            password="demo12345",
            is_staff=True,
        )

        respuesta_cliente = self.client.post(
            reverse("cafeteria_app:login"),
            {"username": self.cliente.username, "password": "demo12345"},
        )
        self.assertRedirects(respuesta_cliente, reverse("cafeteria_app:inicio"))
        self.assertContains(
            self.client.get(reverse("cafeteria_app:inicio")),
            "Cliente",
        )
        self.client.post(reverse("cafeteria_app:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

        respuesta_encargado = self.client.post(
            reverse("cafeteria_app:login"),
            {"username": encargado.username, "password": "demo12345"},
        )
        self.assertRedirects(
            respuesta_encargado,
            reverse("cafeteria_app:panel_encargado"),
        )
        self.assertContains(
            self.client.get(reverse("cafeteria_app:panel_encargado")),
            "Encargado",
        )

    def test_sesion_expira_despues_de_30_minutos_de_inactividad(self):
        self.client.force_login(self.cliente)
        self.assertEqual(self.client.session.get_expiry_age(), 30 * 60)
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)
        self.assertFalse(self.client.session.get_expire_at_browser_close())

    def test_sesion_expirada_exige_autenticarse_de_nuevo(self):
        self.client.force_login(self.cliente)
        session = self.client.session
        session.set_expiry(-1)
        session.save()
        respuesta = self.client.get(reverse("cafeteria_app:lista_pedidos"))

        self.assertRedirects(
            respuesta,
            f"{reverse('cafeteria_app:login')}?next={reverse('cafeteria_app:lista_pedidos')}",
        )

    def test_menu_muestra_el_usuario_y_su_rol(self):
        self.client.force_login(self.cliente)
        respuesta = self.client.get(reverse("cafeteria_app:inicio"))

        self.assertContains(respuesta, "Conectado: cliente")
        self.assertContains(respuesta, "Cliente")

    def test_cliente_solo_accede_a_sus_pedidos(self):
        pedido_ajeno = Pedido.objects.create(
            cliente=self.otro_cliente,
            hora_retiro=time(11, 0),
        )
        self.client.force_login(self.cliente)

        respuesta_lista = self.client.get(reverse("cafeteria_app:lista_pedidos"))
        DetallePedido.objects.create(
            pedido=self.pedido,
            producto=self.producto,
            cantidad=1,
            precio_unitario=1500,
            subtotal=1500,
        )
        respuesta_propia = self.client.get(
            reverse("cafeteria_app:detalle_pedido", args=[self.pedido.pk])
        )
        respuesta_ajena = self.client.get(
            reverse("cafeteria_app:detalle_pedido", args=[pedido_ajeno.pk])
        )

        self.assertEqual(respuesta_lista.status_code, 200)
        self.assertContains(respuesta_lista, f"Pedido #{self.pedido.pk}")
        self.assertNotContains(respuesta_lista, f"Pedido #{pedido_ajeno.pk}")
        self.assertEqual(respuesta_propia.status_code, 200)
        self.assertContains(respuesta_propia, self.producto.nombre)
        self.assertContains(respuesta_propia, "$1.500")
        self.assertEqual(respuesta_ajena.status_code, 404)
        respuesta_cancelacion_ajena = self.client.post(
            reverse("cafeteria_app:cancelar_pedido", args=[pedido_ajeno.pk])
        )
        self.assertEqual(respuesta_cancelacion_ajena.status_code, 404)
        pedido_ajeno.refresh_from_db()
        self.assertEqual(pedido_ajeno.estado, "pendiente")
