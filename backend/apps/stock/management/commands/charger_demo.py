from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.achats.models import Fournisseur
from apps.reseau.models import Magasin, Pays, TauxTva
from apps.stock.models import Article, Lentille, Monture, MouvementStock, PrixArticle, Verre

# Prix de démonstration par pays : (prix TTC, taux de TVA). Taux réels à valider.
ARTICLES = [
    (
        "MON-RB-001",
        "Monture Ray-Ban RB5154 écaille",
        "monture",
        {"TN": ("489.000", "19"), "FR": ("149.00", "20")},
    ),
    (
        "MON-OA-002",
        "Monture titane légère noire",
        "monture",
        {"TN": ("650.000", "19"), "FR": ("219.00", "20")},
    ),
    (
        "SOL-PO-003",
        "Lunettes de soleil polarisées",
        "monture",
        {"TN": ("320.000", "19"), "FR": ("129.00", "20")},
    ),
    (
        "LEN-MJ-004",
        "Lentilles journalières boîte de 30",
        "lentille",
        {"TN": ("85.500", "7"), "FR": ("32.90", "5.50")},
    ),
    (
        "VER-PR-007",
        "Verre progressif 1.6 antireflet",
        "verre",
        {"TN": ("180.000", "7"), "FR": ("190.00", "5.50")},
    ),
    ("ACC-ET-005", "Étui rigide", "divers", {"TN": ("25.000", "19"), "FR": ("15.00", "20")}),
    (
        "ACC-SP-006",
        "Spray nettoyant 30 ml",
        "divers",
        {"TN": ("12.500", "19"), "FR": ("6.90", "20")},
    ),
]


# Fournisseur de chaque article de démonstration, par préfixe de référence.
FOURNISSEURS = {
    "MON-RB": "Luxottica Tunisie",
    "MON-OA": "Lindberg",
    "SOL": "Safilo Tunisie",
    "LEN": "Johnson & Johnson Vision",
    "VER": "Essilor Tunisie",
    "ACC": "Optique Accessoires",
}

# Caractéristiques des articles de démonstration, par référence.
FICHES = {
    "MON-RB-001": (
        Monture,
        {
            "marque": "Ray-Ban",
            "modele": "RB5154",
            "couleur": "écaille",
            "matiere": "acétate",
            "type": "cerclee",
            "genre": "mixte",
            "calibre": 51,
            "pont": 21,
            "branche": 145,
        },
    ),
    "MON-OA-002": (
        Monture,
        {
            "marque": "Lindberg",
            "modele": "Air Titanium",
            "couleur": "noir",
            "matiere": "titane",
            "type": "percee",
            "genre": "homme",
            "calibre": 52,
            "pont": 18,
            "branche": 140,
        },
    ),
    "SOL-PO-003": (
        Monture,
        {
            "marque": "Polaroid",
            "modele": "PLD 2108",
            "couleur": "noir",
            "type": "cerclee",
            "genre": "mixte",
            "calibre": 55,
            "pont": 17,
            "branche": 145,
            "solaire": True,
        },
    ),
    "LEN-MJ-004": (
        Lentille,
        {
            "marque": "Acuvue",
            "modele": "Moist",
            "renouvellement": "journaliere",
            "type": "spherique",
            "rayon": Decimal("8.5"),
            "diametre": Decimal("14.2"),
            "lentilles_par_boite": 30,
        },
    ),
    "VER-PR-007": (
        Verre,
        {
            "marque": "Essilor",
            "gamme": "Varilux Comfort",
            "geometrie": "progressif",
            "indice": Decimal("1.600"),
            "matiere": "organique",
            "traitements": "antireflet, durci",
        },
    ),
}


class Command(BaseCommand):
    help = (
        "Crée quelques articles avec leurs prix par pays, et 10 unités de chacun dans chaque "
        "magasin actif qui n'en a pas encore (essais)."
    )

    def handle(self, *args, **options):
        pays = {p.code: p for p in Pays.objects.all()}
        magasins = list(Magasin.tous.filter(est_actif=True))
        for reference, libelle, famille, tarifs in ARTICLES:
            nom = next(n for prefixe, n in FOURNISSEURS.items() if reference.startswith(prefixe))
            fournisseur, _ = Fournisseur.objects.get_or_create(
                nom=nom, defaults={"pays": pays["TN"]}
            )
            article, _ = Article.objects.get_or_create(
                reference=reference,
                defaults={
                    "libelle": libelle,
                    "famille": famille,
                    "fournisseur": fournisseur,
                    "sur_commande": famille == "verre",
                },
            )
            if reference in FICHES:
                modele, valeurs = FICHES[reference]
                modele.objects.get_or_create(article=article, defaults=valeurs)
            for code, (prix, taux) in tarifs.items():
                if code in pays:
                    tva = TauxTva.objects.filter(pays=pays[code], taux=Decimal(taux)).first()
                    if tva is None:
                        continue
                    PrixArticle.objects.get_or_create(
                        article=article,
                        pays=pays[code],
                        defaults={"prix_vente_ttc": Decimal(prix), "tva": tva},
                    )
            for magasin in magasins if not article.sur_commande else []:
                if MouvementStock.tous.filter(magasin=magasin, article=article).exists():
                    continue
                MouvementStock.tous.create(
                    magasin=magasin,
                    article=article,
                    quantite=10,
                    type=MouvementStock.Type.RECEPTION,
                    reference="stock initial de démonstration",
                )
        self.stdout.write(self.style.SUCCESS("Articles de démonstration en place."))
