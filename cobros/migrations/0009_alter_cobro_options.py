from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('cobros', '0008_cobro_turno')]

    operations = [
        migrations.AlterModelOptions(
            name='cobro',
            options={'permissions': [('anular_cobro', 'Puede anular cobros autorizados')]},
        ),
    ]
