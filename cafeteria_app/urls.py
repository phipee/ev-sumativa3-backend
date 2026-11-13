from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "cafeteria_app"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("productos/", views.lista_productos, name="lista_productos"),
    path("carrito/", views.ver_carrito, name="ver_carrito"),
    path(
        "carrito/agregar/<int:producto_id>/",
        views.agregar_al_carrito,
        name="agregar_al_carrito",
    ),
    path(
        "carrito/cantidad/<int:producto_id>/",
        views.actualizar_cantidad_carrito,
        name="actualizar_cantidad_carrito",
    ),
    path(
        "carrito/quitar/<int:producto_id>/",
        views.quitar_del_carrito,
        name="quitar_del_carrito",
    ),
    path("carrito/vaciar/", views.vaciar_carrito, name="vaciar_carrito"),
    path("carrito/confirmar/", views.confirmar_pedido, name="confirmar_pedido"),
    path("pedidos/", views.lista_pedidos, name="lista_pedidos"),
    path("pedidos/<int:pedido_id>/", views.detalle_pedido, name="detalle_pedido"),
    path(
        "pedidos/<int:pedido_id>/cancelar/",
        views.cancelar_pedido,
        name="cancelar_pedido",
    ),
    path("encargado/", views.panel_encargado, name="panel_encargado"),
    path("encargado/pedidos/", views.gestionar_pedidos, name="gestionar_pedidos"),
    path(
        "encargado/pedidos/<int:pedido_id>/avanzar/",
        views.avanzar_estado_pedido,
        name="avanzar_estado_pedido",
    ),
    path(
        "accounts/login/",
        views.InicioSesionView.as_view(),
        name="login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(next_page="cafeteria_app:login"),
        name="logout",
    ),
]
