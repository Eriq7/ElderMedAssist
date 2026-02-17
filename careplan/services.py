import os
from datetime import date

import openai
from django.utils import timezone

from .exceptions import BlockError, WarningException
from .models import CarePlan, Order, Patient, Provider


# ── Provider ─────────────────────────────────────────────

def get_or_create_provider(name, npi):
    existing = Provider.objects.filter(npi=npi).first()

    if existing:
        if existing.name == name:
            return existing
        else:
            raise BlockError(
                message=f"NPI {npi} is already registered to '{existing.name}', "
                        f"but you submitted '{name}'. NPI is a national license number and must be unique.",
                code='duplicate_npi',
            )

    return Provider.objects.create(name=name, npi=npi)


# ── Patient ──────────────────────────────────────────────

def get_or_create_patient(first_name, last_name, mrn, date_of_birth):
    existing_by_mrn = Patient.objects.filter(mrn=mrn).first()

    if existing_by_mrn:
        if (existing_by_mrn.first_name == first_name and
                existing_by_mrn.last_name == last_name and
                str(existing_by_mrn.date_of_birth) == str(date_of_birth)):
            # MRN same + name and DOB same → reuse
            return existing_by_mrn, None
        else:
            # MRN same + name or DOB different → warning
            return existing_by_mrn, {
                'warning': f"MRN {mrn} exists for '{existing_by_mrn.first_name} {existing_by_mrn.last_name}' "
                           f"(DOB: {existing_by_mrn.date_of_birth}), "
                           f"but you submitted '{first_name} {last_name}' (DOB: {date_of_birth}). "
                           f"Using existing patient record.",
            }

    # Check name + DOB match with different MRN
    existing_by_name_dob = Patient.objects.filter(
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
    ).first()

    if existing_by_name_dob:
        # Name + DOB same + MRN different → warning, create new
        patient = Patient.objects.create(
            first_name=first_name,
            last_name=last_name,
            mrn=mrn,
            date_of_birth=date_of_birth,
        )
        return patient, {
            'warning': f"A patient named '{first_name} {last_name}' (DOB: {date_of_birth}) "
                       f"already exists with MRN {existing_by_name_dob.mrn}. "
                       f"Created new patient with MRN {mrn}. Please verify this is not a duplicate.",
        }

    patient = Patient.objects.create(
        first_name=first_name,
        last_name=last_name,
        mrn=mrn,
        date_of_birth=date_of_birth,
    )
    return patient, None


# ── Order ────────────────────────────────────────────────

def check_duplicate_order(patient, medication_name, confirm=False):
    today = timezone.now().date()

    # Same patient + same medication + same day → block
    same_day = Order.objects.filter(
        patient=patient,
        medication_name=medication_name,
        created_at__date=today,
    ).exists()

    if same_day:
        raise BlockError(
            message=f"An order for '{medication_name}' already exists today for this patient. "
                    f"Duplicate orders on the same day are not allowed.",
            code='duplicate_order_same_day',
        )

    # Same patient + same medication + different day → warning
    previous = Order.objects.filter(
        patient=patient,
        medication_name=medication_name,
    ).order_by('-created_at').first()

    if previous and not confirm:
        raise WarningException(
            message=f"This patient already has a previous order for '{medication_name}' "
                    f"from {previous.created_at.strftime('%Y-%m-%d')}. "
                    f"Submit again with confirm=true to proceed.",
            code='duplicate_order_previous',
        )


# ── Create CarePlan (main flow) ──────────────────────────

def create_careplan(data):
    # 1) Provider — raises BlockError if NPI conflict
    provider = get_or_create_provider(
        name=data['provider_name'],
        npi=data['provider_npi'],
    )

    # 2) Patient — returns (patient, warning_dict_or_None)
    patient, patient_warning = get_or_create_patient(
        first_name=data['patient_first_name'],
        last_name=data['patient_last_name'],
        mrn=data['patient_mrn'],
        date_of_birth=data['date_of_birth'],
    )

    # 3) Order — raises BlockError or WarningException if duplicate
    confirm = data.get('confirm', False)
    check_duplicate_order(patient, data['medication_name'], confirm=confirm)

    # 4) Create order + care plan
    order = Order.objects.create(
        patient=patient,
        provider=provider,
        medication_name=data['medication_name'],
        icd10_code=data['icd10_code'],
    )

    care_plan = CarePlan.objects.create(
        order=order,
        status='pending',
    )

    from .tasks import generate_careplan_task
    generate_careplan_task.delay(care_plan.id)

    result = {
        'id': care_plan.id,
        'status': 'pending',
        'message': 'Received, queued for processing',
    }
    if patient_warning:
        result['warning'] = patient_warning['warning']

    return result


def get_careplan(pk):
    return CarePlan.objects.get(id=pk)


def list_careplans(query=''):
    plans = CarePlan.objects.all().select_related('order__patient', 'order__provider').order_by('-created_at')
    if query:
        plans = plans.filter(order__patient__first_name__icontains=query) | \
                plans.filter(order__patient__last_name__icontains=query) | \
                plans.filter(order__medication_name__icontains=query) | \
                plans.filter(order__icd10_code__icontains=query) | \
                plans.filter(order__provider__name__icontains=query)
    return plans


def format_careplan_download(plan):
    order = plan.order
    patient = order.patient
    provider = order.provider
    return (
        f"Care Plan #{plan.id}\n"
        f"{'=' * 40}\n"
        f"Patient: {patient.first_name} {patient.last_name} (MRN: {patient.mrn})\n"
        f"Medication: {order.medication_name}\n"
        f"ICD-10: {order.icd10_code}\n"
        f"Provider: {provider.name} (NPI: {provider.npi})\n"
        f"Status: {plan.status}\n"
        f"Created: {plan.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"{'=' * 40}\n\n"
        f"{plan.care_plan_text}\n"
    )


def call_llm(patient_name, medication, icd10_code, provider_name):
    api_key = os.environ.get('OPENAI_API_KEY', '')

    if not api_key or api_key == 'your-api-key-here':
        return (
            f"## Problem List\n"
            f"- Patient {patient_name} requires {medication} therapy management\n"
            f"- Diagnosis: {icd10_code}\n\n"
            f"## Goals\n"
            f"1. Optimize {medication} therapy for maximum efficacy\n"
            f"2. Minimize adverse drug reactions\n"
            f"3. Improve patient medication adherence\n\n"
            f"## Pharmacist Interventions\n"
            f"1. Review current {medication} dosing and adjust as needed\n"
            f"2. Provide patient education on {medication} usage and side effects\n"
            f"3. Coordinate with Dr. {provider_name} on therapy modifications\n"
            f"4. Screen for drug-drug interactions\n\n"
            f"## Monitoring Plan\n"
            f"1. Follow-up assessment in 2 weeks\n"
            f"2. Monitor relevant lab values for {icd10_code}\n"
            f"3. Assess medication adherence at each visit\n"
            f"4. Document and report any adverse effects\n"
        )

    client = openai.OpenAI(api_key=api_key)

    prompt = (
        f"You are a clinical pharmacist. Generate a care plan for:\n\n"
        f"Patient: {patient_name}\n"
        f"Medication: {medication}\n"
        f"ICD-10: {icd10_code}\n"
        f"Provider: Dr. {provider_name}\n\n"
        f"Include these sections with ## markdown headers:\n"
        f"1. Problem List\n"
        f"2. Goals\n"
        f"3. Pharmacist Interventions\n"
        f"4. Monitoring Plan\n"
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an experienced clinical pharmacist."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=1500,
    )

    return response.choices[0].message.content
