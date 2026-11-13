from django import forms

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
