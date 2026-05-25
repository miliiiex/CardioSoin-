# Generated manually — ajoute la colonne avatar à accounts_user

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="avatar",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="staff_avatars/%Y/%m/",
                verbose_name="Photo de profil",
            ),
        ),
    ]
