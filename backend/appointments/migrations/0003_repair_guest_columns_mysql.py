# Répare l’écart schéma / django_migrations (colonnes guest absentes alors que 0002 est marquée appliquée).

from django.db import migrations


def _table_has_column(cursor, table: str, column: str) -> bool:
    cursor.execute(
        """
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
        LIMIT 1
        """,
        [table, column],
    )
    return cursor.fetchone() is not None


def repair_guest_columns(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return

    table = "appointments_rendezvous"
    with schema_editor.connection.cursor() as cursor:
        if _table_has_column(cursor, table, "guest_nom_complet"):
            return

        # Permettre les RDV sans fiche patient (aligné sur 0002)
        try:
            cursor.execute(
                f"ALTER TABLE `{table}` MODIFY COLUMN `patient_id` BIGINT NULL"
            )
        except Exception:
            pass

        cursor.execute(
            f"ALTER TABLE `{table}` ADD COLUMN `guest_nom_complet` VARCHAR(200) NOT NULL DEFAULT ''"
        )
        cursor.execute(
            f"ALTER TABLE `{table}` ADD COLUMN `guest_email` VARCHAR(254) NOT NULL DEFAULT ''"
        )
        cursor.execute(
            f"ALTER TABLE `{table}` ADD COLUMN `guest_telephone` VARCHAR(32) NOT NULL DEFAULT ''"
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0002_rendezvous_demande_visiteur"),
    ]

    operations = [
        migrations.RunPython(repair_guest_columns, noop_reverse),
    ]
