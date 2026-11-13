"""Extensión no destructiva del catálogo existente de FORTEX."""
from django.db import models


class FuenteCatalogoVehiculo(models.Model):
    codigo = models.CharField(max_length=70, unique=True)
    titulo = models.CharField(max_length=150)
    url = models.URLField(max_length=350, blank=True)
    licencia = models.CharField(max_length=100, blank=True)
    registrada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'vehiculos'
        ordering = ['codigo']
        verbose_name = 'Fuente catálogo automotor'

    def __str__(self):
        return self.codigo


class RegistroFuenteModelo(models.Model):
    fuente = models.ForeignKey('vehiculos.FuenteCatalogoVehiculo', on_delete=models.PROTECT, related_name='registros')
    modelo = models.ForeignKey('vehiculos.ModeloVehiculo', on_delete=models.PROTECT, related_name='procedencias')
    primera_carga = models.DateTimeField(auto_now_add=True)
    ultima_revision = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'vehiculos'
        constraints = [models.UniqueConstraint(fields=['fuente', 'modelo'], name='uq_fuente_catalogo_modelo')]
        verbose_name = 'Modelo en fuente'


class AliasMarcaVehiculo(models.Model):
    marca = models.ForeignKey('vehiculos.MarcaVehiculo', on_delete=models.PROTECT, related_name='equivalencias')
    denominacion = models.CharField(max_length=160)
    normalizado = models.CharField(max_length=160, db_index=True)
    aprobada = models.BooleanField(default=False)
    origen = models.CharField(max_length=100, default='revision_manual')

    class Meta:
        app_label = 'vehiculos'
        constraints = [models.UniqueConstraint(fields=['marca', 'normalizado'], name='uq_alias_marca_normalizado')]
        verbose_name = 'Equivalencia de marca'

    def save(self, *args, **kwargs):
        from .normalizacion import normalizar
        self.normalizado = normalizar(self.denominacion)
        super().save(*args, **kwargs)


class AliasModeloVehiculo(models.Model):
    modelo = models.ForeignKey('vehiculos.ModeloVehiculo', on_delete=models.PROTECT, related_name='equivalencias')
    denominacion = models.CharField(max_length=160)
    normalizado = models.CharField(max_length=160, db_index=True)
    aprobada = models.BooleanField(default=False)
    origen = models.CharField(max_length=100, default='revision_manual')

    class Meta:
        app_label = 'vehiculos'
        constraints = [models.UniqueConstraint(fields=['modelo', 'normalizado'], name='uq_alias_modelo_normalizado')]
        verbose_name = 'Equivalencia de modelo'

    def save(self, *args, **kwargs):
        from .normalizacion import normalizar
        self.normalizado = normalizar(self.denominacion)
        super().save(*args, **kwargs)
