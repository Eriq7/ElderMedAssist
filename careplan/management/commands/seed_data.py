from django.core.management.base import BaseCommand
from careplan.models import Patient, CarePlan


MOCK_DATA = [
    {
        "patient": {
            "first_name": "Alice", "last_name": "Johnson", "date_of_birth": "1948-03-12",
            "medications": "Metformin 500mg, Lisinopril 10mg",
            "allergies": "Penicillin",
            "health_conditions": "Type 2 Diabetes, Hypertension",
        },
        "status": "completed",
        "care_plan_text": (
            "## Medication Overview\n"
            "- Metformin 500mg: helps control blood sugar for Type 2 Diabetes\n"
            "- Lisinopril 10mg: lowers blood pressure\n\n"
            "## How to Take Your Medications\n"
            "1. Metformin: take with your largest meal to reduce stomach upset\n"
            "2. Lisinopril: take once daily, same time each day\n\n"
            "## Possible Drug Interactions\n"
            "- No major interactions between Metformin and Lisinopril\n"
            "- Lisinopril may slightly lower blood sugar - monitor closely\n\n"
            "## Allergy Warnings\n"
            "- You are allergic to Penicillin - avoid all penicillin-type antibiotics\n\n"
            "## When to Call Your Doctor\n"
            "1. Blood sugar consistently below 70 or above 250\n"
            "2. Persistent dry cough (Lisinopril side effect)\n"
            "3. Dizziness or fainting\n"
        ),
    },
    {
        "patient": {
            "first_name": "Bob", "last_name": "Williams", "date_of_birth": "1952-07-25",
            "medications": "Atorvastatin 20mg, Aspirin 81mg",
            "allergies": "Sulfa drugs",
            "health_conditions": "High Cholesterol, Heart Disease",
        },
        "status": "completed",
        "care_plan_text": (
            "## Medication Overview\n"
            "- Atorvastatin 20mg: lowers cholesterol levels\n"
            "- Aspirin 81mg: helps prevent blood clots\n\n"
            "## How to Take Your Medications\n"
            "1. Atorvastatin: take at bedtime for best results\n"
            "2. Aspirin: take with food to reduce stomach irritation\n\n"
            "## Possible Drug Interactions\n"
            "- Avoid grapefruit juice with Atorvastatin\n"
            "- Both medications thin the blood - watch for unusual bruising\n\n"
            "## When to Call Your Doctor\n"
            "1. Unexplained muscle pain or weakness\n"
            "2. Unusual bleeding or bruising\n"
            "3. Dark-colored urine\n"
        ),
    },
    {
        "patient": {
            "first_name": "Carol", "last_name": "Davis", "date_of_birth": "1945-11-08",
            "medications": "Levothyroxine 50mcg, Omeprazole 20mg",
            "allergies": "",
            "health_conditions": "Hypothyroidism, Acid Reflux",
        },
        "status": "processing",
        "care_plan_text": "",
    },
    {
        "patient": {
            "first_name": "David", "last_name": "Martinez", "date_of_birth": "1960-05-30",
            "medications": "Amlodipine 5mg",
            "allergies": "Ibuprofen",
            "health_conditions": "High Blood Pressure",
        },
        "status": "pending",
        "care_plan_text": "",
    },
    {
        "patient": {
            "first_name": "Emily", "last_name": "Brown", "date_of_birth": "1955-09-14",
            "medications": "Sertraline 50mg, Metformin 1000mg, Amlodipine 10mg",
            "allergies": "Codeine",
            "health_conditions": "Depression, Type 2 Diabetes, Hypertension",
        },
        "status": "failed",
        "care_plan_text": "OpenAI API rate limit exceeded. Please retry.",
    },
]


class Command(BaseCommand):
    help = "Seed database with mock medication guide data"

    def handle(self, *args, **options):
        count = CarePlan.objects.count()
        if count > 0:
            self.stdout.write(f"Database already has {count} records. Clearing first...")
            CarePlan.objects.all().delete()
            Patient.objects.all().delete()

        for data in MOCK_DATA:
            patient = Patient.objects.create(**data['patient'])
            CarePlan.objects.create(
                patient=patient,
                status=data['status'],
                care_plan_text=data['care_plan_text'],
            )

        self.stdout.write(self.style.SUCCESS(f"Created {len(MOCK_DATA)} mock medication guides!"))

        for status in ['completed', 'processing', 'pending', 'failed']:
            n = CarePlan.objects.filter(status=status).count()
            self.stdout.write(f"  {status}: {n}")
