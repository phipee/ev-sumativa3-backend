from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "cafeteria_app"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("productos/", views.lista_productos, name="lista_productos"),
    path("pedidos/", views.lista_pedidos, name="lista_pedidos"),
    path("pedidos/<int:pedido_id>/", views.detalle_pedido, name="detalle_pedido"),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="cafeteria_app/login.html"),
        name="login",
    ),
]
