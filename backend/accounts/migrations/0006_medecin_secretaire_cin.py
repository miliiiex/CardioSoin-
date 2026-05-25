# C.I.N. optionnel sur les fiches médecin et secrétaire (profil personnel).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_data_salma_yaaqoub_landing_copy"),
    ]

    operations = [
        migrations.AddField(
            model_name="medecin",
            name="cin",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Carte d'identité nationale (optionnel).",
                max_length=32,
                verbose_name="C.I.N.",
            ),
        ),
        migrations.AddField(
            model_name="secretaire",
            name="cin",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Carte d'identité nationale (optionnel).",
                max_length=32,
                verbose_name="C.I.N.",
            ),
        ),
    ]
