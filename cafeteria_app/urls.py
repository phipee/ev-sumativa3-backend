from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "cafeteria_app"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("productos/", views.lista_productos, name="lista_productos"),
    path("pedidos/", views.lista_pedidos, name="lista_pedidos"),
    path("pedidos/<int:pedido_id>/", views.detalle_pedido, name="detalle_pedido"),
    path("encargado/", views.panel_encargado, name="panel_encargado"),
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
