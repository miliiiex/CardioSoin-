from django.db import models
class MedicalHistory(models.Model):
    patient = models.ForeignKey('patients.Patient', on_delete=models.CASCADE)
    condition = models.CharField(max_length=255)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.patient.user.username} - {self.condition}"
# Create your models here.
