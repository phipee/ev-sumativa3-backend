from django.contrib import admin

from .models import Categoria, DetallePedido, Pedido, Producto


admin.site.site_header = "Administración Cafetería Fiores"
admin.site.site_title = "Cafetería Fiores"
admin.site.index_title = "Gestión de cafetería"


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activa")
    list_filter = ("activa",)
    search_fields = ("nombre", "descripcion")


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "categoria", "precio", "stock", "disponible")
    list_filter = ("categoria", "disponible")
    search_fields = ("codigo", "nombre", "categoria__nombre")
    list_select_related = ("categoria",)


class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 0


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ("id", "cliente", "fecha", "hora_retiro", "estado", "total")
    list_filter = ("estado", "fecha", "hora_retiro")
    search_fields = ("id", "cliente__username", "cliente__first_name", "cliente__last_name")
    list_select_related = ("cliente",)
    readonly_fields = ("estado",)
    inlines = (DetallePedidoInline,)


@admin.register(DetallePedido)
class DetallePedidoAdmin(admin.ModelAdmin):
    list_display = ("pedido", "producto", "cantidad", "precio_unitario", "subtotal")
    list_filter = ("pedido__estado", "producto__categoria")
    search_fields = ("pedido__id", "producto__codigo", "producto__nombre")
    list_select_related = ("pedido", "producto")
