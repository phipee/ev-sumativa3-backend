from datetime import time

from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from .admin import DetallePedidoInline, PedidoAdmin
from .models import Categoria, DetallePedido, Pedido, Producto


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
        self.assertEqual(self.client.get(reverse("cafeteria_app:inicio")).status_code, 200)
        respuesta = self.client.get(reverse("cafeteria_app:lista_productos"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.producto.nombre)

    def test_pedidos_requieren_autenticacion(self):
        respuesta = self.client.get(reverse("cafeteria_app:lista_pedidos"))

        self.assertRedirects(
            respuesta,
            f"{reverse('cafeteria_app:login')}?next={reverse('cafeteria_app:lista_pedidos')}",
        )

    def test_cliente_solo_accede_a_sus_pedidos(self):
        pedido_ajeno = Pedido.objects.create(
            cliente=self.otro_cliente,
            hora_retiro=time(11, 0),
        )
        self.client.force_login(self.cliente)

        respuesta_lista = self.client.get(reverse("cafeteria_app:lista_pedidos"))
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
        self.assertEqual(respuesta_ajena.status_code, 404)
