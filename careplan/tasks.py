import time

from celery import shared_task

from .models import CarePlan
from .services import call_llm
from .metrics import (
    careplan_status_total,
    careplan_active_count,
    careplan_generation_duration_seconds,
    celery_task_duration_seconds,
    celery_task_retries_total,
    celery_task_failures_total,
)


@shared_task(bind=True, max_retries=3)
def generate_careplan_task(self, careplan_id):
    plan = CarePlan.objects.select_related('patient').get(id=careplan_id)
    patient = plan.patient

    print(f"[Celery] Processing CarePlan #{plan.id} - {patient.first_name} {patient.last_name}")

    plan.status = 'processing'
    plan.save()

    start = time.monotonic()
    try:
        result = call_llm(
            patient_name=f"{patient.first_name} {patient.last_name}",
            medications=patient.medications,
            allergies=patient.allergies,
            health_conditions=patient.health_conditions,
        )
        duration = time.monotonic() - start

        plan.status = 'completed'
        plan.care_plan_text = result
        plan.save()

        careplan_status_total.labels(status='completed').inc()
        careplan_generation_duration_seconds.observe(duration)
        celery_task_duration_seconds.labels(task_name='generate_careplan_task').observe(duration)
        print(f"[Celery] CarePlan #{plan.id} completed")

    except Exception as e:
        duration = time.monotonic() - start
        celery_task_duration_seconds.labels(task_name='generate_careplan_task').observe(duration)

        print(f"[Celery] CarePlan #{plan.id} failed (attempt {self.request.retries + 1}/3): {e}")
        try:
            celery_task_retries_total.labels(task_name='generate_careplan_task').inc()
            self.retry(countdown=2 ** self.request.retries)
        except self.MaxRetriesExceededError:
            plan.status = 'failed'
            plan.care_plan_text = str(e)
            plan.save()
            careplan_status_total.labels(status='failed').inc()
            celery_task_failures_total.labels(task_name='generate_careplan_task').inc()
            print(f"[Celery] CarePlan #{plan.id} permanently failed after 3 retries")


@shared_task
def update_careplan_gauge():
    """Sync the Prometheus gauge with actual DB counts every 30s."""
    for status in ['pending', 'processing', 'completed', 'failed']:
        count = CarePlan.objects.filter(status=status).count()
        careplan_active_count.labels(status=status).set(count)
