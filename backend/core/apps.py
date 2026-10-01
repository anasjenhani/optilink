from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"
    verbose_name = "Noyau"

    def ready(self):
        from . import checks  # noqa: F401
