from django.core.management.base import BaseCommand
from careplan.models import CarePlan


MOCK_PATIENTS = [
    {
        "patient_name": "Alice Johnson",
        "patient_mrn": "100001",
        "medication": "Metformin 500mg",
        "icd10_code": "E11.9",
        "provider_name": "Dr. Smith",
        "provider_npi": "1234567890",
        "status": "completed",
        "care_plan_text": (
            "## Problem List\n"
            "- Type 2 Diabetes Mellitus (E11.9)\n"
            "- Initiated on Metformin 500mg for glycemic control\n\n"
            "## Goals\n"
            "1. Achieve HbA1c < 7% within 3 months\n"
            "2. Fasting blood glucose 80-130 mg/dL\n"
            "3. No hypoglycemic episodes\n\n"
            "## Pharmacist Interventions\n"
            "1. Educate patient on taking Metformin with meals to reduce GI side effects\n"
            "2. Review renal function before and during therapy\n"
            "3. Screen for drug interactions with current medications\n"
            "4. Counsel on signs/symptoms of lactic acidosis\n\n"
            "## Monitoring Plan\n"
            "1. HbA1c in 3 months\n"
            "2. Renal function (eGFR) every 6 months\n"
            "3. Fasting glucose log review at each visit\n"
            "4. Vitamin B12 level annually\n"
        ),
    },
    {
        "patient_name": "Bob Williams",
        "patient_mrn": "100002",
        "medication": "Lisinopril 10mg",
        "icd10_code": "I10",
        "provider_name": "Dr. Chen",
        "provider_npi": "2345678901",
        "status": "completed",
        "care_plan_text": (
            "## Problem List\n"
            "- Essential Hypertension (I10)\n"
            "- Started on Lisinopril 10mg daily\n\n"
            "## Goals\n"
            "1. Blood pressure < 130/80 mmHg within 4 weeks\n"
            "2. No adverse effects (cough, angioedema)\n"
            "3. Patient adherence > 90%\n\n"
            "## Pharmacist Interventions\n"
            "1. Educate on importance of daily adherence even when asymptomatic\n"
            "2. Counsel to avoid potassium supplements and salt substitutes\n"
            "3. Review for NSAID use which may reduce efficacy\n"
            "4. Advise to report persistent dry cough\n\n"
            "## Monitoring Plan\n"
            "1. Blood pressure check in 2 weeks\n"
            "2. Serum potassium and creatinine in 1-2 weeks\n"
            "3. Renal function every 6 months\n"
            "4. Home BP log review at follow-up\n"
        ),
    },
    {
        "patient_name": "Carol Davis",
        "patient_mrn": "100003",
        "medication": "Atorvastatin 20mg",
        "icd10_code": "E78.5",
        "provider_name": "Dr. Patel",
        "provider_npi": "3456789012",
        "status": "completed",
        "care_plan_text": (
            "## Problem List\n"
            "- Hyperlipidemia, unspecified (E78.5)\n"
            "- Initiated Atorvastatin 20mg for LDL reduction\n\n"
            "## Goals\n"
            "1. LDL cholesterol < 100 mg/dL within 6 weeks\n"
            "2. No myopathy symptoms\n"
            "3. Liver function remains within normal limits\n\n"
            "## Pharmacist Interventions\n"
            "1. Advise to take at bedtime for optimal efficacy\n"
            "2. Counsel to avoid excessive grapefruit juice\n"
            "3. Screen for drug interactions (CYP3A4 inhibitors)\n"
            "4. Educate on lifestyle modifications (diet, exercise)\n\n"
            "## Monitoring Plan\n"
            "1. Lipid panel in 6-8 weeks\n"
            "2. Liver enzymes (ALT/AST) at baseline and as needed\n"
            "3. Report any unexplained muscle pain or weakness\n"
            "4. Annual cardiovascular risk assessment\n"
        ),
    },
    {
        "patient_name": "David Martinez",
        "patient_mrn": "100004",
        "medication": "Amlodipine 5mg",
        "icd10_code": "I10",
        "provider_name": "Dr. Smith",
        "provider_npi": "1234567890",
        "status": "processing",
        "care_plan_text": "",
    },
    {
        "patient_name": "Emily Brown",
        "patient_mrn": "100005",
        "medication": "Omeprazole 20mg",
        "icd10_code": "K21.0",
        "provider_name": "Dr. Lee",
        "provider_npi": "4567890123",
        "status": "pending",
        "care_plan_text": "",
    },
    {
        "patient_name": "Frank Wilson",
        "patient_mrn": "100006",
        "medication": "Sertraline 50mg",
        "icd10_code": "F32.1",
        "provider_name": "Dr. Garcia",
        "provider_npi": "5678901234",
        "status": "failed",
        "care_plan_text": "OpenAI API rate limit exceeded. Please retry.",
    },
    {
        "patient_name": "Grace Kim",
        "patient_mrn": "100007",
        "medication": "Levothyroxine 50mcg",
        "icd10_code": "E03.9",
        "provider_name": "Dr. Patel",
        "provider_npi": "3456789012",
        "status": "completed",
        "care_plan_text": (
            "## Problem List\n"
            "- Hypothyroidism, unspecified (E03.9)\n"
            "- Initiated Levothyroxine 50mcg daily\n\n"
            "## Goals\n"
            "1. TSH within normal range (0.4-4.0 mIU/L) in 6-8 weeks\n"
            "2. Resolution of fatigue and other symptoms\n"
            "3. Stable long-term thyroid function\n\n"
            "## Pharmacist Interventions\n"
            "1. Take on empty stomach, 30-60 min before breakfast\n"
            "2. Separate from calcium, iron, antacids by 4 hours\n"
            "3. Review for drug interactions affecting absorption\n"
            "4. Counsel on consistent daily timing\n\n"
            "## Monitoring Plan\n"
            "1. TSH level in 6-8 weeks\n"
            "2. Free T4 if TSH remains abnormal\n"
            "3. Annual TSH once stable\n"
            "4. Monitor for signs of over-replacement (palpitations, tremor)\n"
        ),
    },
    {
        "patient_name": "Henry Thompson",
        "patient_mrn": "100008",
        "medication": "Metformin 1000mg",
        "icd10_code": "E11.65",
        "provider_name": "Dr. Smith",
        "provider_npi": "1234567890",
        "status": "completed",
        "care_plan_text": (
            "## Problem List\n"
            "- Type 2 DM with hyperglycemia (E11.65)\n"
            "- Dose escalation: Metformin 500mg -> 1000mg\n\n"
            "## Goals\n"
            "1. HbA1c < 7% within 3 months\n"
            "2. Reduce fasting glucose to < 130 mg/dL\n"
            "3. Minimize GI side effects during dose titration\n\n"
            "## Pharmacist Interventions\n"
            "1. Titrate gradually: 500mg x 1 week, then 1000mg\n"
            "2. Take with largest meal to reduce GI upset\n"
            "3. Consider extended-release if GI intolerance persists\n"
            "4. Reinforce dietary adherence and exercise\n\n"
            "## Monitoring Plan\n"
            "1. HbA1c in 3 months\n"
            "2. eGFR - hold if < 30 mL/min\n"
            "3. GI symptom check in 2 weeks\n"
            "4. Vitamin B12 annually\n"
        ),
    },
]


class Command(BaseCommand):
    help = "Seed database with mock care plan data"

    def handle(self, *args, **options):
        count = CarePlan.objects.count()
        if count > 0:
            self.stdout.write(f"Database already has {count} records. Clearing first...")
            CarePlan.objects.all().delete()

        for data in MOCK_PATIENTS:
            CarePlan.objects.create(**data)

        self.stdout.write(self.style.SUCCESS(f"Created {len(MOCK_PATIENTS)} mock care plans!"))

        # 打印统计
        for status in ['completed', 'processing', 'pending', 'failed']:
            n = CarePlan.objects.filter(status=status).count()
            self.stdout.write(f"  {status}: {n}")
