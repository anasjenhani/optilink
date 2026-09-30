from celery import shared_task


@shared_task
def ping():
    """Tâche de contrôle : vérifie qu'un worker Celery répond."""
    return "pong"
