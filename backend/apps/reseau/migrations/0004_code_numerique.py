import json
from pathlib import Path

import django.core.validators
from django.db import migrations, models

LISTE = Path(__file__).resolve().parent.parent / "pays_du_monde.json"


def remplir_code_numerique(apps, schema_editor):
    Pays = apps.get_model("reseau", "Pays")
    numeriques = {
        p["code"]: p["code_numerique"] for p in json.loads(LISTE.read_text(encoding="utf-8"))
    }
    for pays in Pays.objects.all():
        if pays.code not in numeriques:
            raise RuntimeError(f"Code ISO numérique inconnu pour le pays {pays.code} ({pays.nom}).")
        pays.code_numerique = numeriques[pays.code]
        pays.save(update_fields=["code_numerique"])


class Migration(migrations.Migration):
    dependencies = [("reseau", "0003_peniches")]

    operations = [
        migrations.AddField(
            model_name="pays",
            name="code_numerique",
            field=models.CharField(max_length=3, null=True),
        ),
        migrations.RunPython(remplir_code_numerique, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="pays",
            name="code_numerique",
            field=models.CharField(
                help_text="Code numérique ISO 3166-1, ex. 788 pour la Tunisie.",
                max_length=3,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator("^\\d{3}$", "Trois chiffres, ex. 788.")
                ],
                verbose_name="code ISO",
            ),
        ),
        migrations.AlterField(
            model_name="pays",
            name="code",
            field=models.CharField(
                help_text="ISO 3166-1 alpha-2, ex. TN",
                max_length=2,
                unique=True,
                verbose_name="code alpha-2",
            ),
        ),
    ]
