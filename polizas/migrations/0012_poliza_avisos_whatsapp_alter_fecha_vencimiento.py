# Generated for FORTEX WhatsFORTEX recordatorios v2

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("polizas", "0011_poliza_cobertura"),
    ]

    operations = [
        migrations.AddField(
            model_name="poliza",
            name="avisos_whatsapp",
            field=models.BooleanField(
                default=False,
                verbose_name="Recordatorios automáticos por WhatsApp",
            ),
        ),
        migrations.AlterField(
            model_name="poliza",
            name="avisos_whatsapp",
            field=models.BooleanField(
                default=True,
                verbose_name="Recordatorios automáticos por WhatsApp",
            ),
        ),
        migrations.AlterField(
            model_name="poliza",
            name="fecha_vencimiento",
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name="Próximo vencimiento de pago",
            ),
        ),
    ]
}
