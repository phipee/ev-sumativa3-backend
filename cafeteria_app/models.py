from django.conf import settings
from django.db import models


class Categoria(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField()
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["nombre"]

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
