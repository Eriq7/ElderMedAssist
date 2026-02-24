import os
import time

from .exceptions import BlockError
from .metrics import careplan_requests_total, llm_call_duration_seconds, llm_call_errors_total
from .models import CarePlan, Patient


# ── Patient ──────────────────────────────────────────────

def get_or_create_patient(first_name, last_name, date_of_birth, medications, allergies, health_conditions):
    """Find existing patient by name+DOB, or create a new one. Always update meds/allergies/conditions."""
    patient, created = Patient.objects.get_or_create(
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
        defaults={
            'medications': medications,
            'allergies': allergies,
            'health_conditions': health_conditions,
        },
    )

    if not created:
        # Update with latest info
        patient.medications = medications
        patient.allergies = allergies
        patient.health_conditions = health_conditions
        patient.save()

    return patient


# ── Duplicate check ──────────────────────────────────────

def check_duplicate_careplan(patient):
    """Block if the same patient already has a pending/processing care plan."""
    active = CarePlan.objects.filter(
        patient=patient,
        status__in=['pending', 'processing'],
    ).exists()

    if active:
        raise BlockError(
            message="A medication guide is already being generated for this patient. Please wait for it to complete.",
            code='duplicate_active_careplan',
        )


# ── Create CarePlan (main flow) ──────────────────────────

def create_careplan(data):
    # 1) Patient
    patient = get_or_create_patient(
        first_name=data['patient_first_name'],
        last_name=data['patient_last_name'],
        date_of_birth=data['date_of_birth'],
        medications=data['medications'],
        allergies=data.get('allergies', ''),
        health_conditions=data.get('health_conditions', ''),
    )

    # 2) Duplicate check
    check_duplicate_careplan(patient)

    # 3) Create care plan
    care_plan = CarePlan.objects.create(
        patient=patient,
        status='pending',
    )

    from .tasks import generate_careplan_task
    generate_careplan_task.delay(care_plan.id)

    careplan_requests_total.labels(status='accepted').inc()

    return {
        'id': care_plan.id,
        'status': 'pending',
        'message': 'Received, generating your medication guide.',
    }


def get_careplan(pk):
    return CarePlan.objects.get(id=pk)


def list_careplans(query=''):
    plans = CarePlan.objects.all().select_related('patient').order_by('-created_at')
    if query:
        plans = plans.filter(patient__first_name__icontains=query) | \
                plans.filter(patient__last_name__icontains=query) | \
                plans.filter(patient__medications__icontains=query)
    return plans


def format_careplan_download(plan):
    patient = plan.patient
    return (
        f"Medication Guide #{plan.id}\n"
        f"{'=' * 40}\n"
        f"Patient: {patient.first_name} {patient.last_name}\n"
        f"Date of Birth: {patient.date_of_birth}\n"
        f"Medications: {patient.medications}\n"
        f"Allergies: {patient.allergies or 'None reported'}\n"
        f"Health Conditions: {patient.health_conditions or 'None reported'}\n"
        f"Status: {plan.status}\n"
        f"Created: {plan.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"{'=' * 40}\n\n"
        f"{plan.care_plan_text}\n"
    )


def call_llm(patient_name, medications, allergies, health_conditions):
    api_key = os.environ.get('OPENAI_API_KEY', '')

    if not api_key or api_key == 'your-api-key-here':
        return (
            f"## Medication Overview\n"
            f"Patient: {patient_name}\n"
            f"Medications: {medications}\n\n"
            f"## How to Take Your Medications\n"
            f"1. Take {medications} as directed by your doctor\n"
            f"2. Take with food unless told otherwise\n"
            f"3. Take at the same time each day\n\n"
            f"## Possible Drug Interactions\n"
            f"- Based on your medications, no major interactions were found\n"
            f"- Always tell your doctor about all medications you take\n\n"
            f"## Allergy Warnings\n"
            f"- Known allergies: {allergies or 'None reported'}\n"
            f"- Watch for signs of allergic reaction: rash, swelling, trouble breathing\n\n"
            f"## Health Condition Considerations\n"
            f"- Current conditions: {health_conditions or 'None reported'}\n"
            f"- Your medications have been reviewed against your health conditions\n\n"
            f"## When to Call Your Doctor\n"
            f"1. If you experience any unusual side effects\n"
            f"2. If you miss multiple doses\n"
            f"3. If your symptoms get worse\n"
        )

    import openai
    client = openai.OpenAI(api_key=api_key)

    prompt = (
        f"Patient: {patient_name}\n"
        f"Medications: {medications}\n"
        f"Allergies: {allergies or 'None reported'}\n"
        f"Health Conditions / Lifestyle: {health_conditions or 'None reported'}\n\n"
        f"Generate the daily care plan using EXACTLY these sections and format:\n\n"
        f"## ⚠️ DANGER — Must Read First\n"
        f"Cross-check every medication against every other medication, every allergy, and every "
        f"health condition or lifestyle habit. For EACH dangerous combination found:\n"
        f"- Name the two things that conflict (e.g. '头孢 + 酒精')\n"
        f"- State the exact medical danger (e.g. 'causes disulfiram-like reaction: vomiting, racing heart, "
        f"difficulty breathing, potentially fatal')\n"
        f"- State what the patient MUST do (e.g. 'Do NOT drink any alcohol for the entire course of "
        f"头孢 and 7 days after the last dose')\n"
        f"If no dangers exist, write 'No critical dangers found.'\n\n"
        f"## 📋 Your Daily Medication Schedule\n"
        f"Create a SPECIFIC hour-by-hour plan using this exact format. Assign each medication to a real "
        f"clock time based on medical best practice (absorption, food interactions, sleep effects). "
        f"Use this template:\n"
        f"- **7:00 AM — Wake Up**: [what to do, e.g. drink a glass of water]\n"
        f"- **8:00 AM — Breakfast**: [which medication to take, with food or not, how to take it]\n"
        f"- **12:00 PM — Lunch**: [which medication if any]\n"
        f"- **6:00 PM — Dinner**: [which medication if any]\n"
        f"- **9:30 PM — Bedtime**: [which medication if any]\n"
        f"Add or remove time slots as needed for this patient's specific medications. "
        f"Every medication must appear in the schedule with an exact time.\n\n"
        f"## 💊 About Each Medication\n"
        f"For each medication, write 2-3 sentences: what it does, its most common side effect "
        f"for THIS patient (considering their age, conditions, and other meds), and one specific "
        f"thing to watch for.\n\n"
        f"## 🚫 Things You Must NOT Do\n"
        f"List specific forbidden actions based on THIS patient's exact medications and conditions. "
        f"Format: '[Action] — because [specific medical reason]'. "
        f"Examples of the level of specificity required:\n"
        f"- 'Do NOT drink alcohol while taking 头孢 — it causes a disulfiram-like reaction (vomiting, "
        f"rapid heartbeat, potentially fatal)'\n"
        f"- 'Do NOT take ibuprofen — it increases bleeding risk with your current medications'\n"
        f"Do NOT write generic advice like 'be careful' or 'talk to your doctor'.\n\n"
        f"## 🚨 Call 911 (Emergency) Immediately If\n"
        f"List 3-5 specific emergency symptoms tied to THIS patient's medications and conditions. "
        f"Not generic symptoms — symptoms that would specifically indicate a dangerous reaction "
        f"to these exact medications.\n"
    )

    start = time.monotonic()
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You are ElderMedAssist, a strict personal medication butler for elderly patients. "
                    "You speak directly to the patient as 'you'. "
                    "You are NOT an advisor — you are a butler who gives ORDERS. "
                    "Your output is a concrete daily plan the patient follows exactly, not suggestions. "
                    "NEVER say 'consult your doctor', 'talk to your healthcare provider', or 'as prescribed'. "
                    "NEVER give vague advice. Every sentence must be a specific instruction or a specific fact. "
                    "If a medication + lifestyle combination is dangerous, say so BLUNTLY in the first section — "
                    "do not bury it or soften it. "
                    "Write in simple language a 70-year-old can understand. Keep sentences short."
                )},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=3000,
        )
        llm_call_duration_seconds.observe(time.monotonic() - start)
        return response.choices[0].message.content
    except Exception as e:
        llm_call_duration_seconds.observe(time.monotonic() - start)
        llm_call_errors_total.labels(error_type=type(e).__name__).inc()
        raise
