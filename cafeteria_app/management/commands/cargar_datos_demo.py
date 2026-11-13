from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from cafeteria_app.models import Categoria, Producto


CATEGORIAS = (
    ("Bebidas calientes", "Cafés, tés e infusiones preparados al momento."),
    ("Bebidas frías", "Jugos, aguas y bebidas refrescantes."),
    ("Sándwiches", "Opciones saladas para disfrutar durante el recreo."),
    ("Pastelería", "Queques, galletas y productos dulces."),
)

PRODUCTOS = (
    ("BC001", "Café americano", "Bebidas calientes", 1400, 20, True),
    ("BC002", "Café con leche", "Bebidas calientes", 1700, 18, True),
    ("BC003", "Cappuccino", "Bebidas calientes", 1900, 12, True),
    ("BC004", "Té negro", "Bebidas calientes", 1100, 15, True),
    ("BC005", "Té verde", "Bebidas calientes", 1100, 10, True),
    ("BC006", "Chocolate caliente", "Bebidas calientes", 1800, 0, True),
    ("BF001", "Agua mineral", "Bebidas frías", 900, 30, True),
    ("BF002", "Jugo de naranja", "Bebidas frías", 1300, 16, True),
    ("BF003", "Limonada", "Bebidas frías", 1200, 14, True),
    ("BF004", "Bebida cola", "Bebidas frías", 1000, 20, True),
    ("BF005", "Té helado", "Bebidas frías", 1250, 8, True),
    ("BF006", "Jugo de frutilla", "Bebidas frías", 1400, 0, False),
    ("SA001", "Ave palta", "Sándwiches", 2800, 10, True),
    ("SA002", "Jamón queso", "Sándwiches", 2400, 12, True),
    ("SA003", "Vegetariano", "Sándwiches", 2600, 8, True),
    ("SA004", "Barros luco", "Sándwiches", 3200, 6, True),
    ("SA005", "Atún tomate", "Sándwiches", 2700, 5, True),
    ("SA006", "Pollo lechuga", "Sándwiches", 2750, 0, True),
    ("PA001", "Queque de vainilla", "Pastelería", 1200, 10, True),
    ("PA002", "Brownie", "Pastelería", 1500, 12, True),
    ("PA003", "Galleta de avena", "Pastelería", 800, 20, True),
    ("PA004", "Muffin de arándano", "Pastelería", 1400, 8, True),
    ("PA005", "Pie de limón", "Pastelería", 1700, 5, True),
    ("PA006", "Medialuna", "Pastelería", 1000, 0, False),
)


class Command(BaseCommand):
    help = (
        "Carga cuatro categorías, 24 productos y un encargado con dos clientes "
        "de prueba. Las cuentas nuevas usan la contraseña FioresDemo2026!."
    )

    def handle(self, *args, **options):
        categorias = {}
        for nombre, descripcion in CATEGORIAS:
            categoria, _ = Categoria.objects.update_or_create(
                nombre=nombre,
                defaults={"descripcion": descripcion, "activa": True},
            )
            categorias[nombre] = categoria

        for codigo, nombre, categoria, precio, stock, disponible in PRODUCTOS:
            Producto.objects.update_or_create(
                codigo=codigo,
                defaults={
                    "nombre": nombre,
                    "categoria": categorias[categoria],
                    "precio": precio,
                    "stock": stock,
                    "disponible": disponible,
                },
            )

        user_model = get_user_model()
        usuarios = (
            ("encargado", "Encargado", "Fiores", True),
            ("cliente1", "Estudiante", "Uno", False),
            ("cliente2", "Estudiante", "Dos", False),
        )
        cuentas_nuevas = []
        for username, first_name, last_name, is_staff in usuarios:
            usuario, creado = user_model.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": f"{username}@fiores.cl",
                    "is_staff": is_staff,
                    "is_superuser": False,
                },
            )
            if creado:
                usuario.set_password("FioresDemo2026!")
                usuario.save(update_fields=["password"])
                cuentas_nuevas.append(username)
            elif is_staff and not usuario.is_staff:
                usuario.is_staff = True
                usuario.save(update_fields=["is_staff"])

        self.stdout.write(
            self.style.SUCCESS(
                "Datos listos: 4 categorías, 24 productos, un encargado y dos clientes."
            )
        )
        if cuentas_nuevas:
            self.stdout.write(
                "Contraseña de las cuentas recién creadas: FioresDemo2026!"
            )
