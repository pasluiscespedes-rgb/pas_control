from django import forms
from .models import Poliza


class ImporteAPField(forms.DecimalField):
    def to_python(self, value):
        if isinstance(value, str):
            value = value.strip().replace(" ", "")
            if "," in value:
                value = value.replace(".", "").replace(",", ".")
        return super().to_python(value)


class DatosAPForm(forms.ModelForm):
    """Validación compartida por alta y edición; el cliente es el tomador."""

    importe_cuota = ImporteAPField(required=False, max_digits=12, decimal_places=2, min_value=0)
    porcentaje_comision = ImporteAPField(required=False, max_digits=5, decimal_places=2, min_value=0, max_value=100)

    class Meta:
        model = Poliza
        fields = ("asegurado_nombre", "asegurado_documento", "actividad_declarada", "cobertura",
                  "importe_cuota", "porcentaje_comision", "fecha_alta", "periodicidad", "compania", "numero_poliza")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("asegurado_nombre", "asegurado_documento", "actividad_declarada", "cobertura"):
            self.fields[name].required = True
