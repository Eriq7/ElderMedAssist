import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import redis
from careplan.models import CarePlan
from careplan.views import call_llm

QUEUE_NAME = 'careplan_queue'

redis_client = redis.Redis(
    host=os.environ.get('REDIS_HOST', 'localhost'),
    port=6379,
    db=0,
)


def process_one(careplan_id):
    plan = CarePlan.objects.get(id=careplan_id)
    print(f"[Worker] Processing CarePlan #{plan.id} - {plan.patient_name}")

    plan.status = 'processing'
    plan.save()

    try:
        result = call_llm(
            patient_name=plan.patient_name,
            medication=plan.medication,
            icd10_code=plan.icd10_code,
            provider_name=plan.provider_name,
        )
        plan.status = 'completed'
        plan.care_plan_text = result
        print(f"[Worker] CarePlan #{plan.id} completed")
    except Exception as e:
        plan.status = 'failed'
        plan.care_plan_text = str(e)
        print(f"[Worker] CarePlan #{plan.id} failed: {e}")

    plan.save()


def main():
    print("[Worker] Started, waiting for tasks...")
    while True:
        # blpop = blocking pop, waits until a task appears
        _, careplan_id = redis_client.blpop(QUEUE_NAME)
        careplan_id = int(careplan_id)
        print(f"\n[Worker] Got careplan_id={careplan_id} from queue")
        process_one(careplan_id)


if __name__ == '__main__':
    main()
