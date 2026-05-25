from django.apps import AppConfig


class PatientsConfig(AppConfig):
    name = "patients"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import signals  # noqa: F401

        signals.connect_patient_signals()
