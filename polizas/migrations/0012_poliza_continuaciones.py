from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("polizas", "0011_poliza_cobertura")]

    operations = [
        migrations.AddField(
            model_name="poliza", name="poliza_anterior",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name="continuaciones", to="polizas.poliza",
                                    help_text="Póliza original conservada al renovar o cambiar aseguradora."),
        ),
        migrations.AddField(
            model_name="poliza", name="tipo_continuacion",
            field=models.CharField(max_length=20, blank=True, default="", choices=[
                ("renovacion", "Renovación"), ("cambio", "Cambio de aseguradora")]),
        ),
    ]
