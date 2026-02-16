import json
import os

import openai
import redis
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import CarePlan

# 连接 Redis
redis_client = redis.Redis(
    host=os.environ.get('REDIS_HOST', 'localhost'),
    port=6379,
    db=0,
)
QUEUE_NAME = 'careplan_queue'


def index(request):
    return render(request, 'careplan/index.html')


@csrf_exempt
@require_http_methods(["POST"])
def generate_careplan(request):
    data = json.loads(request.body)
    print(f"\n{'='*50}")
    print(f"[DEBUG 1] 收到请求, data = {data}")

    # 1) 存数据库，status = pending
    care_plan = CarePlan.objects.create(
        patient_name=data['patient_name'],
        patient_mrn=data['patient_mrn'],
        medication=data['medication'],
        icd10_code=data['icd10_code'],
        provider_name=data['provider_name'],
        provider_npi=data['provider_npi'],
        status='pending',
    )
    print(f"[DEBUG 2] CarePlan #{care_plan.id} 已存入数据库, status=pending")

    # 2) 把 careplan_id 放进 Redis 队列
    redis_client.rpush(QUEUE_NAME, care_plan.id)
    queue_length = redis_client.llen(QUEUE_NAME)
    print(f"[DEBUG 3] careplan_id={care_plan.id} 已放入 Redis 队列, 当前队列长度={queue_length}")

    # 3) 立刻返回给用户
    print(f"[DEBUG 4] 立刻返回 202 Accepted")
    print(f"{'='*50}\n")

    return JsonResponse({
        'id': care_plan.id,
        'status': 'pending',
        'message': 'Received, queued for processing',
    }, status=202)


@require_http_methods(["GET"])
def list_careplans(request):
    plans = CarePlan.objects.all().order_by('-created_at')

    q = request.GET.get('q', '').strip()
    if q:
        plans = plans.filter(patient_name__icontains=q) | \
                plans.filter(medication__icontains=q) | \
                plans.filter(icd10_code__icontains=q) | \
                plans.filter(provider_name__icontains=q)

    return JsonResponse([serialize_careplan(p) for p in plans], safe=False)


@require_http_methods(["GET"])
def download_careplan(request, pk):
    plan = CarePlan.objects.get(id=pk)

    content = (
        f"Care Plan #{plan.id}\n"
        f"{'=' * 40}\n"
        f"Patient: {plan.patient_name} (MRN: {plan.patient_mrn})\n"
        f"Medication: {plan.medication}\n"
        f"ICD-10: {plan.icd10_code}\n"
        f"Provider: {plan.provider_name} (NPI: {plan.provider_npi})\n"
        f"Status: {plan.status}\n"
        f"Created: {plan.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"{'=' * 40}\n\n"
        f"{plan.care_plan_text}\n"
    )

    response = HttpResponse(content, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="careplan_{plan.id}.txt"'
    return response


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
    print(f"[DEBUG LLM] api_key 存在: {bool(api_key and api_key != 'your-api-key-here')}")

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
