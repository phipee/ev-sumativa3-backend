def resumen_carrito(request):
    carrito = request.session.get("carrito", {})
    cantidad = 0
    if isinstance(carrito, dict):
        cantidad = sum(
            valor
            for valor in carrito.values()
            if isinstance(valor, int) and not isinstance(valor, bool) and valor > 0
        )
    return {"carrito_unidades": cantidad}
