from django import forms
from .models import Poliza


class DatosAPForm(forms.ModelForm):
    """Validación compartida por alta y edición; el cliente es el tomador."""

    class Meta:
        model = Poliza
        fields = ("asegurado_nombre", "asegurado_documento", "actividad_declarada", "cobertura")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True
