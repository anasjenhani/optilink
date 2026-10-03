from django.db import migrations

# Profils demandés par Anas le 2026-10-03 : les anciens rôles équivalents sont renommés, les
# nouveaux profils sont créés après la migration par ``initialiser_roles``.
RENOMMAGES = {
    "Administrateur système": "Administrateur",
    "Responsable magasin": "Responsable de magasin",
    "Gestionnaire RH": "Ressources Humaines",
    "Comptable": "Comptabilité & Finance",
    "Logisticien": "Achats & Gestionnaire de Stock",
}
# Rôles sans équivalent : retirés s'ils ne sont donnés à personne, gardés sinon.
RETIRES = ("Direction", "Responsable société")


def vers_profils(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for ancien, nouveau in RENOMMAGES.items():
        if not Group.objects.filter(name=nouveau).exists():
            Group.objects.filter(name=ancien).update(name=nouveau)
    Group.objects.filter(name__in=RETIRES, affectations__isnull=True).delete()


def vers_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for ancien, nouveau in RENOMMAGES.items():
        if not Group.objects.filter(name=ancien).exists():
            Group.objects.filter(name=nouveau).update(name=ancien)


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("securite", "0004_perimetre_societe"),
    ]

    operations = [migrations.RunPython(vers_profils, vers_roles)]
