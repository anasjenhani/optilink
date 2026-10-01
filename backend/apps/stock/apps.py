from django.apps import AppConfig


class StockConfig(AppConfig):
    name = "apps.stock"
    label = "stock"
    verbose_name = "Stock"

    def ready(self):
        from auditlog.registry import auditlog

        from .models import Article, PrixArticle

        auditlog.register(Article)
        auditlog.register(PrixArticle)
