"""Tablas adicionales: sin alterar vehículos, clientes ni pólizas existentes."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('vehiculos', '0007_modeloanio')]
    operations = [
        migrations.CreateModel(name='FuenteCatalogoVehiculo',fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('codigo', models.CharField(max_length=70, unique=True)),
            ('titulo', models.CharField(max_length=150)),
            ('url', models.URLField(max_length=350, blank=True)),
            ('licencia', models.CharField(max_length=100, blank=True)),
            ('registrada_en', models.DateTimeField(auto_now_add=True)),
        ], options={'ordering':['codigo'],'verbose_name':'Fuente catálogo automotor'}),
        migrations.CreateModel(name='RegistroFuenteModelo',fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('primera_carga', models.DateTimeField(auto_now_add=True)),
            ('ultima_revision', models.DateTimeField(auto_now=True)),
            ('fuente', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='registros',to='vehiculos.fuentecatalogovehiculo')),
            ('modelo', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='procedencias',to='vehiculos.modelovehiculo')),
        ], options={'verbose_name':'Modelo en fuente'}),
        migrations.AddConstraint(model_name='registrofuentemodelo',constraint=models.UniqueConstraint(fields=('fuente','modelo'),name='uq_fuente_catalogo_modelo')),
        migrations.CreateModel(name='AliasMarcaVehiculo',fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('denominacion', models.CharField(max_length=160)),
            ('normalizado', models.CharField(max_length=160,db_index=True)),
            ('aprobada', models.BooleanField(default=False)),
            ('origen', models.CharField(max_length=100,default='revision_manual')),
            ('marca', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='equivalencias',to='vehiculos.marcavehiculo')),
        ], options={'verbose_name':'Equivalencia de marca'}),
        migrations.AddConstraint(model_name='aliasmarcavehiculo',constraint=models.UniqueConstraint(fields=('marca','normalizado'),name='uq_alias_marca_normalizado')),
        migrations.CreateModel(name='AliasModeloVehiculo',fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('denominacion', models.CharField(max_length=160)),
            ('normalizado', models.CharField(max_length=160,db_index=True)),
            ('aprobada', models.BooleanField(default=False)),
            ('origen', models.CharField(max_length=100,default='revision_manual')),
            ('modelo', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='equivalencias',to='vehiculos.modelovehiculo')),
        ], options={'verbose_name':'Equivalencia de modelo'}),
        migrations.AddConstraint(model_name='aliasmodelovehiculo',constraint=models.UniqueConstraint(fields=('modelo','normalizado'),name='uq_alias_modelo_normalizado')),
    ]
