import django.core.validators
import django.db.models.deletion
from decimal import Decimal

from django.db import migrations, models


def reprendre_les_prix(apps, schema_editor):
    """Les prix du prototype étaient en euros avec la TVA française : ils deviennent le tarif France."""
    Article = apps.get_model("stock", "Article")
    PrixArticle = apps.get_model("stock", "PrixArticle")
    Pays = apps.get_model("reseau", "Pays")
    TauxTva = apps.get_model("reseau", "TauxTva")
    france = Pays.objects.filter(code="FR").first()
    if france is None:
        return
    for article in Article.objects.all():
        tva, _ = TauxTva.objects.get_or_create(
            pays=france, taux=article.taux_tva, defaults={"libelle": f"{article.taux_tva} %"}
        )
        PrixArticle.objects.create(
            article=article, pays=france, prix_vente_ttc=article.prix_vente_ttc, tva=tva
        )


class Migration(migrations.Migration):
    dependencies = [
        ("stock", "0001_initial"),
        ("reseau", "0002_pays"),
    ]

    operations = [
        migrations.CreateModel(
            name="PrixArticle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("prix_vente_ttc", models.DecimalField(decimal_places=3, max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal("0"))])),
                ("article", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="prix", to="stock.article")),
                ("pays", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="reseau.pays")),
                ("tva", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="prix", to="reseau.tauxtva", verbose_name="TVA")),
            ],
            options={"verbose_name": "prix de vente", "verbose_name_plural": "prix de vente"},
        ),
        migrations.AddConstraint(
            model_name="prixarticle",
            constraint=models.UniqueConstraint(fields=("article", "pays"), name="un_prix_par_pays"),
        ),
        migrations.RunPython(reprendre_les_prix, migrations.RunPython.noop),
        migrations.RemoveField(model_name="article", name="prix_vente_ttc"),
        migrations.RemoveField(model_name="article", name="taux_tva"),
    ]
