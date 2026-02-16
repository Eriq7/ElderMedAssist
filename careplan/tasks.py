from celery import shared_task
from .models import CarePlan
from .views import call_llm


@shared_task(bind=True, max_retries=3)
def generate_careplan_task(self, careplan_id):
    plan = CarePlan.objects.get(id=careplan_id)
    print(f"[Celery] Processing CarePlan #{plan.id} - {plan.patient_name}")

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
        plan.save()
        print(f"[Celery] CarePlan #{plan.id} completed")

    except Exception as e:
        print(f"[Celery] CarePlan #{plan.id} failed (attempt {self.request.retries + 1}/3): {e}")
        try:
            self.retry(countdown=2 ** self.request.retries)
        except self.MaxRetriesExceededError:
            plan.status = 'failed'
            plan.care_plan_text = str(e)
            plan.save()
            print(f"[Celery] CarePlan #{plan.id} permanently failed after 3 retries")