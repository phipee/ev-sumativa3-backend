from datetime import time, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class Categoria(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField()
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["nombre"]

    @classmethod
    def crear(cls, nombre, descripcion, activa=True):
        return cls.objects.create(
            nombre=nombre,
            descripcion=descripcion,
            activa=activa,
        )

    @classmethod
    def listar(cls):
        return cls.objects.all()

    def editar(self, nombre, descripcion, activa):
        self.nombre = nombre
        self.descripcion = descripcion
        self.activa = activa
        self.save()
        return self

    def eliminar(self):
        self.delete()

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name="productos",
    )
    codigo = models.CharField(max_length=10, unique=True)
    nombre = models.CharField(max_length=100)
    precio = models.IntegerField()
    stock = models.IntegerField()
    disponible = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]

    @classmethod
    def crear(cls, categoria, codigo, nombre, precio, stock, disponible=True):
        return cls.objects.create(
            categoria=categoria,
            codigo=codigo,
            nombre=nombre,
            precio=precio,
            stock=stock,
            disponible=disponible,
        )

    @classmethod
    def listar(cls):
        return cls.objects.all()

    def editar(self, categoria, codigo, nombre, precio, stock, disponible):
        self.categoria = categoria
        self.codigo = codigo
        self.nombre = nombre
        self.precio = precio
        self.stock = stock
        self.disponible = disponible
        self.save()
        return self

    def eliminar(self):
        self.delete()

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"


class Pedido(models.Model):
    ESTADOS = [
        ("pendiente", "Pendiente"),
        ("preparando", "En preparación"),
        ("listo", "Listo para retiro"),
        ("entregado", "Entregado"),
        ("cancelado", "Cancelado"),
    ]

    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pedidos",
    )
    fecha = models.DateTimeField(auto_now_add=True)
    hora_retiro = models.TimeField()
    estado = models.CharField(max_length=15, choices=ESTADOS, default="pendiente")
    total = models.IntegerField(default=0)
    observacion = models.TextField(blank=True)

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        return f"Pedido #{self.pk} - {self.cliente}"


class DetallePedido(models.Model):
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name="detalles",
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="detalles_pedido",
    )
    cantidad = models.IntegerField()
    precio_unitario = models.IntegerField()
    subtotal = models.IntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["pedido", "producto"],
                name="detalle_pedido_producto_unico",
            )
        ]

    def __str__(self):
        return f"{self.cantidad} x {self.producto} (pedido #{self.pedido_id})"


class Carrito:
    MAX_UNIDADES = 10
    CLAVE_SESION = "carrito"

    @classmethod
    def contenido(cls, sesion):
        carrito = sesion.get(cls.CLAVE_SESION, {})
        if not isinstance(carrito, dict):
            raise ValidationError("El carrito no es válido.")
        resultado = {}
        for producto_id, cantidad in carrito.items():
            try:
                producto_id = str(int(producto_id))
            except (TypeError, ValueError):
                raise ValidationError("El carrito contiene un producto no válido.")
            if type(cantidad) is not int or cantidad < 1:
                raise ValidationError("El carrito contiene una cantidad no válida.")
            resultado[producto_id] = cantidad
        return resultado

    @classmethod
    def unidades(cls, sesion):
        return sum(cls.contenido(sesion).values())

    @classmethod
    def agregar(cls, sesion, producto_id, cantidad=1):
        carrito = cls.contenido(sesion)
        producto = cls._producto_disponible(producto_id)
        clave = str(producto.pk)
        if type(cantidad) is not int or cantidad < 1:
            raise ValidationError("La cantidad debe ser mayor que cero.")
        nueva_cantidad = carrito.get(clave, 0) + cantidad
        if nueva_cantidad > producto.stock:
            raise ValidationError(f"Stock insuficiente para {producto.nombre}.")
        if sum(carrito.values()) + cantidad > cls.MAX_UNIDADES:
            raise ValidationError("El carrito no puede superar 10 unidades.")
        carrito[clave] = nueva_cantidad
        cls._guardar(sesion, carrito)

    @classmethod
    def cambiar_cantidad(cls, sesion, producto_id, cantidad):
        carrito = cls.contenido(sesion)
        clave = str(int(producto_id))
        if clave not in carrito:
            raise ValidationError("El producto no está en el carrito.")
        if type(cantidad) is not int or cantidad < 1:
            raise ValidationError("La cantidad debe ser mayor que cero.")
        producto = cls._producto_disponible(producto_id)
        if cantidad > producto.stock:
            raise ValidationError(f"Stock insuficiente para {producto.nombre}.")
        if sum(carrito.values()) - carrito[clave] + cantidad > cls.MAX_UNIDADES:
            raise ValidationError("El carrito no puede superar 10 unidades.")
        carrito[clave] = cantidad
        cls._guardar(sesion, carrito)

    @classmethod
    def quitar(cls, sesion, producto_id):
        carrito = cls.contenido(sesion)
        carrito.pop(str(int(producto_id)), None)
        cls._guardar(sesion, carrito)

    @classmethod
    def vaciar(cls, sesion):
        cls._guardar(sesion, {})

    @classmethod
    def confirmar(cls, sesion, cliente, hora_retiro, observacion=""):
        carrito = cls.contenido(sesion)
        if not carrito:
            raise ValidationError("El carrito está vacío.")
        if sum(carrito.values()) > cls.MAX_UNIDADES:
            raise ValidationError("El carrito no puede superar 10 unidades.")
        if not isinstance(hora_retiro, time) or hora_retiro.tzinfo is not None:
            raise ValidationError("La hora de retiro no es válida.")
        ahora = timezone.localtime()
        minimo = (ahora + timedelta(minutes=20)).time()
        if hora_retiro < time(8, 0) or hora_retiro > time(18, 0):
            raise ValidationError("La hora de retiro debe estar entre las 08:00 y las 18:00.")
        if hora_retiro < minimo:
            raise ValidationError("La hora de retiro debe ser al menos 20 minutos después de ahora.")

        cantidades = {int(producto_id): cantidad for producto_id, cantidad in carrito.items()}
        with transaction.atomic():
            productos = list(
                Producto.objects.select_for_update()
                .select_related("categoria")
                .filter(pk__in=cantidades)
                .order_by("pk")
            )
            if len(productos) != len(cantidades):
                raise ValidationError("Uno o más productos ya no existen.")
            por_id = {producto.pk: producto for producto in productos}
            total = 0
            for producto_id, cantidad in cantidades.items():
                producto = por_id[producto_id]
                if not producto.categoria.activa or not producto.disponible:
                    raise ValidationError(f"{producto.nombre} ya no está disponible.")
                if producto.stock < cantidad:
                    raise ValidationError(f"Stock insuficiente para {producto.nombre}.")
                total += producto.precio * cantidad

            pedido = Pedido.objects.create(
                cliente=cliente,
                hora_retiro=hora_retiro,
                observacion=observacion,
                total=total,
                estado="pendiente",
            )
            detalles = []
            for producto_id, cantidad in cantidades.items():
                producto = por_id[producto_id]
                detalles.append(
                    DetallePedido(
                        pedido=pedido,
                        producto=producto,
                        cantidad=cantidad,
                        precio_unitario=producto.precio,
                        subtotal=producto.precio * cantidad,
                    )
                )
                producto.stock -= cantidad
                producto.save(update_fields=["stock"])
            DetallePedido.objects.bulk_create(detalles)

        cls.vaciar(sesion)
        return pedido

    @staticmethod
    def _producto_disponible(producto_id):
        try:
            producto = Producto.objects.select_related("categoria").get(pk=producto_id)
        except Producto.DoesNotExist:
            raise ValidationError("El producto no existe.")
        if not producto.disponible or not producto.categoria.activa:
            raise ValidationError(f"{producto.nombre} ya no está disponible.")
        return producto

    @classmethod
    def _guardar(cls, sesion, carrito):
        sesion[cls.CLAVE_SESION] = carrito
        sesion.modified = True


