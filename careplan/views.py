import json
import os

import openai
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import CarePlan


def index(request):
    return render(request, 'careplan/index.html')


@csrf_exempt
@require_http_methods(["POST"])
def generate_careplan(request):
    data = json.loads(request.body)

    # 1) 创建，状态 = pending
    care_plan = CarePlan.objects.create(
        patient_name=data['patient_name'],
        patient_mrn=data['patient_mrn'],
        medication=data['medication'],
        icd10_code=data['icd10_code'],
        provider_name=data['provider_name'],
        provider_npi=data['provider_npi'],
        status='pending',
    )

    # 2) 改为 processing
    care_plan.status = 'processing'
    care_plan.save()

    # 3) 同步调用 LLM
    try:
        result = call_llm(
            patient_name=care_plan.patient_name,
            medication=care_plan.medication,
            icd10_code=care_plan.icd10_code,
            provider_name=care_plan.provider_name,
        )
        care_plan.status = 'completed'
        care_plan.care_plan_text = result
    except Exception as e:
        care_plan.status = 'failed'
        care_plan.care_plan_text = str(e)

    care_plan.save()

    return JsonResponse(serialize_careplan(care_plan))


@require_http_methods(["GET"])
def list_careplans(request):
    plans = CarePlan.objects.all().order_by('-created_at')
    return JsonResponse([serialize_careplan(p) for p in plans], safe=False)


def serialize_careplan(p):
    return {
        'id': p.id,
        'patient_name': p.patient_name,
        'patient_mrn': p.patient_mrn,
        'medication': p.medication,
        'icd10_code': p.icd10_code,
        'provider_name': p.provider_name,
        'provider_npi': p.provider_npi,
        'status': p.status,
        # 只有 completed 才返回内容 —— 前端只在完成时显示
        'care_plan_text': p.care_plan_text if p.status == 'completed' else '',
        'created_at': p.created_at.isoformat(),
    }


# ── LLM 调用 ─────────────────────────────────────────────

def call_llm(patient_name, medication, icd10_code, provider_name):
    api_key = os.environ.get('OPENAI_API_KEY', '')

    if not api_key or api_key == 'your-api-key-here':
        # 没有 API key 时返回 mock 数据，方便你先跑通流程
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
