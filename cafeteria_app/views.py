from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import Categoria, Pedido, Producto


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


def lista_productos(request):
    productos = Producto.objects.filter(
        categoria__activa=True,
        disponible=True,
        stock__gt=0,
    ).select_related("categoria")
    return render(request, "cafeteria_app/productos.html", {"productos": productos})


@login_required
def lista_pedidos(request):
    pedidos = Pedido.objects.filter(cliente=request.user).prefetch_related(
        "detalles__producto"
    )
    return render(request, "cafeteria_app/pedidos.html", {"pedidos": pedidos})


@login_required
def detalle_pedido(request, pedido_id):
    pedido = get_object_or_404(
        Pedido.objects.prefetch_related("detalles__producto"),
        pk=pedido_id,
        cliente=request.user,
    )
    return render(request, "cafeteria_app/detalle_pedido.html", {"pedido": pedido})
