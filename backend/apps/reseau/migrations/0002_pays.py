from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models

# Pays de départ. Taux et droit de timbre à faire confirmer par le comptable ; ils se modifient
# ensuite dans l'administration, sans développement.
PAYS = [
    {
        "code": "TN",
        "nom": "Tunisie",
        "devise": "TND",
        "decimales": 3,
        "fuseau_horaire": "Africa/Tunis",
        "indicatif_telephonique": "+216",
        "timbre_fiscal": Decimal("1.000"),
        "libelle_identifiant_prescripteur": "N° d'inscription à l'Ordre des médecins",
        "format_identifiant_prescripteur": "",
        "taux": [("19.00", "Taux normal"), ("13.00", "Taux intermédiaire"), ("7.00", "Taux réduit")],
    },
    {
        "code": "FR",
        "nom": "France",
        "devise": "EUR",
        "decimales": 2,
        "fuseau_horaire": "Europe/Paris",
        "indicatif_telephonique": "+33",
        "timbre_fiscal": Decimal("0"),
        "libelle_identifiant_prescripteur": "N° RPPS",
        "format_identifiant_prescripteur": r"\d{11}",
        "taux": [("20.00", "Taux normal"), ("10.00", "Taux intermédiaire"), ("5.50", "Taux réduit")],
    },
]


def creer_pays(apps, schema_editor):
    Pays = apps.get_model("reseau", "Pays")
    TauxTva = apps.get_model("reseau", "TauxTva")
    Magasin = apps.get_model("reseau", "Magasin")
    for donnees in PAYS:
        donnees = dict(donnees)
        taux = donnees.pop("taux")
        pays, _ = Pays.objects.get_or_create(code=donnees.pop("code"), defaults=donnees)
        for valeur, libelle in taux:
            TauxTva.objects.get_or_create(pays=pays, taux=Decimal(valeur), defaults={"libelle": libelle})
    # OptiLink démarre en Tunisie : les magasins déjà créés y sont rattachés.
    Magasin.objects.filter(pays__isnull=True).update(pays=Pays.objects.get(code="TN"))


class Migration(migrations.Migration):
    dependencies = [("reseau", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Pays",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(help_text="ISO 3166, ex. TN", max_length=2, unique=True, verbose_name="code ISO")),
                ("nom", models.CharField(max_length=100)),
                ("devise", models.CharField(help_text="Code ISO 4217, ex. TND", max_length=3)),
                ("decimales", models.PositiveSmallIntegerField(default=2, help_text="Décimales de la monnaie : 3 pour le dinar (millimes).")),
                ("fuseau_horaire", models.CharField(default="Africa/Tunis", max_length=50)),
                ("indicatif_telephonique", models.CharField(blank=True, max_length=6)),
                ("timbre_fiscal", models.DecimalField(decimal_places=3, default=0, help_text="Droit de timbre ajouté à chaque facture (0 si le pays n'en a pas).", max_digits=10)),
                ("libelle_identifiant_prescripteur", models.CharField(default="Identifiant du prescripteur", max_length=100)),
                ("format_identifiant_prescripteur", models.CharField(blank=True, help_text="Expression régulière ; vide = pas de contrôle.", max_length=100)),
            ],
            options={"verbose_name": "pays", "verbose_name_plural": "pays", "ordering": ["nom"]},
        ),
        migrations.CreateModel(
            name="TauxTva",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("taux", models.DecimalField(decimal_places=2, max_digits=5)),
                ("libelle", models.CharField(max_length=50)),
                ("pays", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="taux_tva", to="reseau.pays")),
            ],
            options={"verbose_name": "taux de TVA", "verbose_name_plural": "taux de TVA", "ordering": ["pays", "-taux"]},
        ),
        migrations.AddConstraint(
            model_name="tauxtva",
            constraint=models.UniqueConstraint(fields=("pays", "taux"), name="taux_unique"),
        ),
        migrations.AddField(
            model_name="magasin",
            name="pays",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="magasins", to="reseau.pays"),
        ),
        migrations.RunPython(creer_pays, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="magasin",
            name="pays",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="magasins", to="reseau.pays"),
        ),
    ]
