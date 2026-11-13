from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from .forms import (
    CantidadCarritoForm,
    CatalogoForm,
    ConfirmarPedidoForm,
    FiltroPedidosForm,
)
from .models import Categoria, DetallePedido, Pedido, Producto


class InicioSesionView(LoginView):
    template_name = "cafeteria_app/login.html"

    def get_success_url(self):
        if self.request.user.is_staff:
            return reverse_lazy("cafeteria_app:panel_encargado")
        return reverse_lazy("cafeteria_app:inicio")


def solo_cliente(view_func):
    @wraps(view_func)
    @login_required
    def wrapped(request, *args, **kwargs):
        if request.user.is_staff:
            return HttpResponseForbidden("Esta función está disponible solo para clientes.")
        return view_func(request, *args, **kwargs)

    return wrapped


def solo_encargado(view_func):
    @wraps(view_func)
    @login_required
    def wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponseForbidden("Esta función está disponible solo para encargados.")
        return view_func(request, *args, **kwargs)

    return wrapped


@solo_cliente
def inicio(request):
    categorias = Categoria.objects.filter(activa=True)
    productos_destacados = Producto.objects.filter(
        categoria__activa=True,
        disponible=True,
        stock__gt=0,
    ).select_related("categoria")[:4]
    return render(
        request,
        "cafeteria_app/inicio.html",
        {
            "categorias": categorias,
            "productos_destacados": productos_destacados,
        },
    )


@solo_cliente
def lista_productos(request):
    formulario = CatalogoForm(request.GET or None)
    productos = Producto.objects.filter(
        categoria__activa=True,
        disponible=True,
    ).select_related("categoria")

    if formulario.is_valid():
        nombre = formulario.cleaned_data["q"]
        categoria = formulario.cleaned_data["categoria"]
        if nombre:
            productos = productos.filter(nombre__icontains=nombre)
        if categoria:
            productos = productos.filter(categoria=categoria)

    return render(
        request,
        "cafeteria_app/productos.html",
        {"productos": productos, "formulario": formulario},
    )


@solo_cliente
def ver_carrito(request):
    carrito = request.session.get("carrito", {})
    productos = Producto.objects.filter(pk__in=carrito.keys()).select_related("categoria")
    items = [
        {
            "producto": producto,
            "cantidad": carrito[str(producto.pk)],
            "subtotal": producto.precio * carrito[str(producto.pk)],
            "maximo": min(producto.stock, 10),
        }
        for producto in productos
        if str(producto.pk) in carrito
    ]
    return render(
        request,
        "cafeteria_app/carrito.html",
        {
            "items": items,
            "total_estimado": sum(item["subtotal"] for item in items),
            "formulario_pedido": ConfirmarPedidoForm(),
        },
    )


@solo_cliente
@require_POST
def agregar_al_carrito(request, producto_id):
    producto = get_object_or_404(
        Producto.objects.filter(categoria__activa=True, disponible=True),
        pk=producto_id,
    )
    carrito = request.session.get("carrito", {})
    cantidad_actual = carrito.get(str(producto.pk), 0)

    if (
        type(cantidad_actual) is not int
        or producto.stock <= 0
        or cantidad_actual >= min(producto.stock, 10)
    ):
        messages.error(request, f"{producto.nombre} está agotado o no tiene stock suficiente.")
        return redirect("cafeteria_app:lista_productos")

    carrito[str(producto.pk)] = cantidad_actual + 1
    request.session["carrito"] = carrito

    messages.success(request, f"{producto.nombre} se agregó al carrito.")
    return redirect("cafeteria_app:ver_carrito")


@solo_cliente
@require_POST
def actualizar_cantidad_carrito(request, producto_id):
    carrito = request.session.get("carrito", {})
    clave = str(producto_id)
    formulario = CantidadCarritoForm(request.POST)
    if clave not in carrito or not formulario.is_valid():
        messages.error(request, "La cantidad indicada no es válida.")
        return redirect("cafeteria_app:ver_carrito")

    producto = get_object_or_404(
        Producto.objects.filter(categoria__activa=True, disponible=True),
        pk=producto_id,
    )
    cantidad = formulario.cleaned_data["cantidad"]
    if cantidad > min(producto.stock, 10):
        messages.error(request, "La cantidad supera el stock disponible.")
        return redirect("cafeteria_app:ver_carrito")

    carrito[clave] = cantidad
    request.session["carrito"] = carrito
    messages.success(request, "Cantidad actualizada.")
    return redirect("cafeteria_app:ver_carrito")


@solo_cliente
@require_POST
def quitar_del_carrito(request, producto_id):
    carrito = request.session.get("carrito", {})
    if str(producto_id) in carrito:
        del carrito[str(producto_id)]
        request.session["carrito"] = carrito
        messages.success(request, "Producto quitado del carrito.")
    return redirect("cafeteria_app:ver_carrito")


@solo_cliente
@require_POST
def vaciar_carrito(request):
    request.session.pop("carrito", None)
    messages.success(request, "Carrito vacío.")
    return redirect("cafeteria_app:ver_carrito")


def crear_pedido_desde_carrito(cliente, carrito, hora_retiro):
    if not isinstance(carrito, dict) or not carrito:
        raise ValidationError("El carrito está vacío.")
    try:
        cantidades = {int(producto_id): cantidad for producto_id, cantidad in carrito.items()}
    except (TypeError, ValueError):
        raise ValidationError("El carrito contiene productos no válidos.")

    if any(type(cantidad) is not int or not 1 <= cantidad <= 10
           for cantidad in cantidades.values()):
        raise ValidationError("Cada producto debe tener entre 1 y 10 unidades.")
    if hora_retiro <= timezone.localtime().time().replace(second=0, microsecond=0):
        raise ValidationError("La hora de retiro debe ser futura.")

    with transaction.atomic():
        productos = list(
            Producto.objects.select_for_update()
            .select_related("categoria")
            .filter(pk__in=cantidades)
            .order_by("pk")
        )
        if len(productos) != len(cantidades):
            raise ValidationError("Uno o más productos ya no están disponibles.")

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
            total=total,
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

    return pedido


@solo_cliente
@require_POST
def confirmar_pedido(request):
    formulario = ConfirmarPedidoForm(request.POST)
    if not formulario.is_valid():
        carrito = request.session.get("carrito", {})
        productos = Producto.objects.filter(pk__in=carrito.keys()).select_related("categoria")
        items = [
            {
                "producto": producto,
                "cantidad": carrito[str(producto.pk)],
                "subtotal": producto.precio * carrito[str(producto.pk)],
                "maximo": min(producto.stock, 10),
            }
            for producto in productos
            if str(producto.pk) in carrito
        ]
        return render(
            request,
            "cafeteria_app/carrito.html",
            {
                "items": items,
                "total_estimado": sum(item["subtotal"] for item in items),
                "formulario_pedido": formulario,
            },
            status=400,
        )

    try:
        pedido = crear_pedido_desde_carrito(
            request.user,
            request.session.get("carrito", {}),
            formulario.cleaned_data["hora_retiro"],
        )
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
        return redirect("cafeteria_app:ver_carrito")

    request.session.pop("carrito", None)
    messages.success(request, f"Pedido #{pedido.pk} confirmado.")
    return redirect("cafeteria_app:detalle_pedido", pedido_id=pedido.pk)


@solo_cliente
def lista_pedidos(request):
    pedidos = Pedido.objects.filter(cliente=request.user).prefetch_related(
        "detalles__producto"
    )
    return render(request, "cafeteria_app/pedidos.html", {"pedidos": pedidos})


@solo_cliente
def detalle_pedido(request, pedido_id):
    pedido = get_object_or_404(
        Pedido.objects.prefetch_related("detalles__producto"),
        pk=pedido_id,
        cliente=request.user,
    )
    return render(request, "cafeteria_app/detalle_pedido.html", {"pedido": pedido})


@solo_cliente
@require_POST
def cancelar_pedido(request, pedido_id):
    with transaction.atomic():
        pedido = get_object_or_404(
            Pedido.objects.select_for_update(),
            pk=pedido_id,
            cliente=request.user,
        )
        if pedido.estado != "pendiente":
            messages.error(request, "Solo se pueden cancelar pedidos pendientes.")
            return redirect("cafeteria_app:detalle_pedido", pedido_id=pedido.pk)

        detalles = list(pedido.detalles.all())
        productos = {
            producto.pk: producto
            for producto in Producto.objects.select_for_update()
            .filter(pk__in=[detalle.producto_id for detalle in detalles])
            .order_by("pk")
        }
        for detalle in detalles:
            producto = productos[detalle.producto_id]
            producto.stock += detalle.cantidad
            producto.save(update_fields=["stock"])
        pedido.estado = "cancelado"
        pedido.save(update_fields=["estado"])

    messages.success(request, f"Pedido #{pedido.pk} cancelado. El stock fue repuesto.")
    return redirect("cafeteria_app:detalle_pedido", pedido_id=pedido.pk)


@solo_encargado
def panel_encargado(request):
    return render(request, "cafeteria_app/panel_encargado.html")


@solo_encargado
def gestionar_pedidos(request):
    formulario = FiltroPedidosForm(request.GET or None)
    siguientes = {
        "pendiente": "En preparación",
        "preparando": "Listo para retiro",
        "listo": "Entregado",
    }
    pedidos = (
        Pedido.objects.filter(fecha__date=timezone.localdate())
        .select_related("cliente")
        .prefetch_related("detalles__producto")
    )
    if formulario.is_valid() and formulario.cleaned_data["estado"]:
        pedidos = pedidos.filter(estado=formulario.cleaned_data["estado"])
    pedidos = list(pedidos)
    for pedido in pedidos:
        pedido.estado_siguiente = siguientes.get(pedido.estado)
    return render(
        request,
        "cafeteria_app/gestionar_pedidos.html",
        {"pedidos": pedidos, "formulario": formulario, "today": timezone.localdate()},
    )


@solo_encargado
@require_POST
def avanzar_estado_pedido(request, pedido_id):
    siguientes = {
        "pendiente": "preparando",
        "preparando": "listo",
        "listo": "entregado",
    }
    with transaction.atomic():
        pedido = get_object_or_404(Pedido.objects.select_for_update(), pk=pedido_id)
        siguiente = siguientes.get(pedido.estado)
        if not siguiente:
            messages.error(request, "El pedido ya no tiene estados siguientes.")
            return redirect("cafeteria_app:gestionar_pedidos")
        pedido.estado = siguiente
        pedido.save(update_fields=["estado"])

    messages.success(request, f"Pedido #{pedido.pk}: {pedido.get_estado_display()}.")
    return redirect("cafeteria_app:gestionar_pedidos")
