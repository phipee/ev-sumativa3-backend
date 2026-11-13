from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from .forms import CatalogoForm
from .models import Categoria, Pedido, Producto


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
        }
        for producto in productos
    ]
    return render(request, "cafeteria_app/carrito.html", {"items": items})


@solo_cliente
@require_POST
def agregar_al_carrito(request, producto_id):
    producto = get_object_or_404(
        Producto.objects.filter(categoria__activa=True, disponible=True),
        pk=producto_id,
    )
    carrito = request.session.get("carrito", {})
    cantidad_actual = carrito.get(str(producto.pk), 0)

    if producto.stock <= 0 or cantidad_actual >= producto.stock:
        messages.error(request, f"{producto.nombre} está agotado o no tiene stock suficiente.")
        return redirect("cafeteria_app:lista_productos")

    carrito[str(producto.pk)] = cantidad_actual + 1
    request.session["carrito"] = carrito

    messages.success(request, f"{producto.nombre} se agregó al carrito.")
    return redirect("cafeteria_app:ver_carrito")


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


@solo_encargado
def panel_encargado(request):
    return render(request, "cafeteria_app/panel_encargado.html")
