from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.reseau.models import Magasin
from apps.stock.models import Article, MouvementStock

ARTICLES = [
    ("MON-RB-001", "Monture Ray-Ban RB5154 écaille", "monture", "149.00", "20.00"),
    ("MON-OA-002", "Monture titane légère noire", "monture", "219.00", "20.00"),
    ("SOL-PO-003", "Lunettes de soleil polarisées", "monture", "129.00", "20.00"),
    ("LEN-MJ-004", "Lentilles journalières boîte de 30", "lentille", "32.90", "5.50"),
    ("ACC-ET-005", "Étui rigide", "accessoire", "15.00", "20.00"),
    ("ACC-SP-006", "Spray nettoyant 30 ml", "accessoire", "6.90", "20.00"),
]


class Command(BaseCommand):
    help = "Crée quelques articles et 10 unités de chacun dans chaque magasin actif (essais)."

    def handle(self, *args, **options):
        for reference, libelle, famille, prix, tva in ARTICLES:
            article, cree = Article.objects.get_or_create(
                reference=reference,
                defaults={
                    "libelle": libelle,
                    "famille": famille,
                    "prix_vente_ttc": Decimal(prix),
                    "taux_tva": Decimal(tva),
                },
            )
            if not cree:
                continue
            for magasin in Magasin.tous.filter(est_actif=True):
                MouvementStock.tous.create(
                    magasin=magasin,
                    article=article,
                    quantite=10,
                    type=MouvementStock.Type.RECEPTION,
                    reference="stock initial de démonstration",
                )
        self.stdout.write(self.style.SUCCESS("Articles de démonstration en place."))
