from celery import shared_task
from django.core.management import call_command


@shared_task
def expire_pending_rides_task():
    call_command("expire_pending_rides")

