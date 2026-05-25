# Generated manually — demandes RDV sans compte patient (landing)

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0001_initial"),
        ("patients", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="rendezvous",
            name="patient",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="rendez_vous",
                to="patients.patient",
            ),
        ),
        migrations.AddField(
            model_name="rendezvous",
            name="guest_nom_complet",
            field=models.CharField(
                blank=True,
                max_length=200,
                verbose_name="Nom du demandeur (hors portail)",
            ),
        ),
        migrations.AddField(
            model_name="rendezvous",
            name="guest_email",
            field=models.EmailField(blank=True, verbose_name="E-mail demandeur"),
        ),
        migrations.AddField(
            model_name="rendezvous",
            name="guest_telephone",
            field=models.CharField(
                blank=True,
                max_length=32,
                verbose_name="Téléphone demandeur",
            ),
        ),
    ]
