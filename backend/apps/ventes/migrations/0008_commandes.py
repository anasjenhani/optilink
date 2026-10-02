import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def dater_paiements(apps, schema_editor):
    Paiement = apps.get_model("ventes", "Paiement")
    for paiement in Paiement.objects.select_related("vente"):
        paiement.recu_le = paiement.vente.cree_le
        paiement.recu_par_id = paiement.vente.vendeur_id
        paiement.save(update_fields=["recu_le", "recu_par"])


def dater_livraisons(apps, schema_editor):
    Vente = apps.get_model("ventes", "Vente")
    for vente in Vente.objects.all():
        vente.livree_le = vente.cree_le
        vente.livree_par_id = vente.vendeur_id
        vente.save(update_fields=["livree_le", "livree_par"])


class Migration(migrations.Migration):
    dependencies = [
        ("ventes", "0007_droits_devis"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            "vente",
            "statut",
            models.CharField(
                choices=[("en_commande", "En commande"), ("livree", "Livrée")],
                default="livree",
                max_length=12,
            ),
        ),
        migrations.AddField("vente", "livraison_prevue_le", models.DateField(blank=True, null=True)),
        migrations.AddField("vente", "livree_le", models.DateTimeField(blank=True, null=True)),
        migrations.AddField(
            "vente",
            "livree_par",
            models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(dater_livraisons, migrations.RunPython.noop),
        migrations.AddField(
            "paiement", "recu_le", models.DateTimeField(default=django.utils.timezone.now)
        ),
        migrations.AddField(
            "paiement",
            "recu_par",
            models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(dater_paiements, migrations.RunPython.noop),
    ]
