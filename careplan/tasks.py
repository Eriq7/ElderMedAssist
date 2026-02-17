from celery import shared_task
from .models import CarePlan
from .services import call_llm


@shared_task(bind=True, max_retries=3)
def generate_careplan_task(self, careplan_id):
    plan = CarePlan.objects.select_related('order__patient', 'order__provider').get(id=careplan_id)
    patient = plan.order.patient
    order = plan.order
    provider = plan.order.provider

    print(f"[Celery] Processing CarePlan #{plan.id} - {patient.first_name} {patient.last_name}")

    plan.status = 'processing'
    plan.save()

    try:
        result = call_llm(
            patient_name=f"{patient.first_name} {patient.last_name}",
            medication=order.medication_name,
            icd10_code=order.icd10_code,
            provider_name=provider.name,
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
