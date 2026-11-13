from django import forms
from django.utils import timezone

from .models import Categoria


class CatalogoForm(forms.Form):
    q = forms.CharField(
        label="Buscar por nombre",
        max_length=100,
        required=False,
    )
    categoria = forms.ModelChoiceField(
        label="Categoría",
        queryset=Categoria.objects.filter(activa=True),
        required=False,
        empty_label="Todas las categorías",
    )


class CantidadCarritoForm(forms.Form):
    cantidad = forms.IntegerField(min_value=1, max_value=10)


class ConfirmarPedidoForm(forms.Form):
    hora_retiro = forms.TimeField(
        label="Hora de retiro",
        input_formats=["%H:%M"],
        widget=forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
    )

    def clean_hora_retiro(self):
        hora = self.cleaned_data["hora_retiro"]
        ahora = timezone.localtime().time().replace(second=0, microsecond=0)
        if hora <= ahora:
            raise forms.ValidationError("Elige una hora futura para hoy.")
        return hora
