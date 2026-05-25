from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("patients", "0002_add_patient_genre"),
    ]

    operations = [
        migrations.AddField(
            model_name="patient",
            name="cin",
            field=models.CharField(
                blank=True,
                default="",
                max_length=32,
                verbose_name="C.I.N.",
                help_text="Numéro de la carte d'identité nationale (optionnel).",
            ),
        ),
    ]
