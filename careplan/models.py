from django.db import models


class CarePlan(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    patient_name = models.CharField(max_length=200)
    patient_mrn = models.CharField(max_length=20)
    medication = models.CharField(max_length=200)
    icd10_code = models.CharField(max_length=20)
    provider_name = models.CharField(max_length=200)
    provider_npi = models.CharField(max_length=20)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    care_plan_text = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"CarePlan #{self.id} - {self.patient_name} ({self.status})"
