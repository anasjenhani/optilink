import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def numeroter_et_renommer_droits(apps, schema_editor):
    """Codes SCTE001… dans l'ordre de création, et droits « région » renommés « société »."""
    Societe = apps.get_model("reseau", "Societe")
    for numero, societe in enumerate(Societe.objects.order_by("cree_le", "pk"), start=1):
        Societe.objects.filter(pk=societe.pk).update(code=f"SCTE{numero:03d}")
    Permission = apps.get_model("auth", "Permission")
    for permission in Permission.objects.filter(
        content_type__app_label="reseau", codename__endswith="_region"
    ):
        action = permission.codename.removesuffix("_region")
        if Permission.objects.filter(
            content_type=permission.content_type, codename=f"{action}_societe"
        ).exists():
            continue
        permission.codename = f"{action}_societe"
        permission.name = permission.name.replace("région", "société")
        permission.save()


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("reseau", "0004_code_numerique"),
        # Les affectations de securite pointent encore vers les régions jusqu'à securite 0004.
        ("securite", "0003_journaux_en_ajout_seul"),
    ]

    operations = [
        migrations.RenameModel("Region", "Societe"),
        migrations.RenameField("societe", "nom", "raison_sociale"),
        migrations.AlterField(
            model_name="societe",
            name="raison_sociale",
            field=models.CharField(max_length=150),
        ),
        migrations.AlterModelOptions(
            name="societe", options={"ordering": ["code"], "verbose_name": "société"}
        ),
        migrations.AddField(
            model_name="societe",
            name="responsable",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="societe",
            name="forme_juridique",
            field=models.CharField(
                blank=True,
                choices=[
                    ("SARL", "SARL"),
                    ("SUARL", "SUARL"),
                    ("SA", "SA"),
                    ("SNC", "SNC"),
                    ("SCS", "SCS"),
                    ("PP", "Personne physique"),
                ],
                max_length=5,
            ),
        ),
        migrations.AddField(
            model_name="societe",
            name="matricule_fiscal",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="societe",
            name="registre_commerce",
            field=models.CharField(blank=True, max_length=30, verbose_name="registre de commerce"),
        ),
        migrations.AddField(
            model_name="societe",
            name="numero_cnss",
            field=models.CharField(blank=True, max_length=30, verbose_name="n° CNSS"),
        ),
        migrations.AddField(
            model_name="societe",
            name="banque",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="societe",
            name="rib",
            field=models.CharField(
                blank=True,
                help_text="20 chiffres en Tunisie, ou IBAN.",
                max_length=34,
                validators=[
                    django.core.validators.RegexValidator(
                        "^[A-Za-z0-9 ]*$", "Chiffres et lettres seulement."
                    )
                ],
                verbose_name="RIB bancaire",
            ),
        ),
        migrations.AddField(
            model_name="societe", name="adresse", field=models.TextField(blank=True)
        ),
        migrations.AddField(
            model_name="societe",
            name="code_postal",
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AddField(
            model_name="societe", name="ville", field=models.CharField(blank=True, max_length=100)
        ),
        migrations.AddField(
            model_name="societe",
            name="pays",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="societes",
                to="reseau.pays",
            ),
        ),
        migrations.AddField(
            model_name="societe",
            name="telephone_1",
            field=models.CharField(blank=True, max_length=20, verbose_name="téléphone 1"),
        ),
        migrations.AddField(
            model_name="societe",
            name="telephone_2",
            field=models.CharField(blank=True, max_length=20, verbose_name="téléphone 2"),
        ),
        migrations.AddField(
            model_name="societe", name="fax", field=models.CharField(blank=True, max_length=20)
        ),
        migrations.AddField(
            model_name="societe",
            name="email",
            field=models.EmailField(blank=True, max_length=254, verbose_name="e-mail"),
        ),
        migrations.AddField(
            model_name="societe",
            name="site_web",
            field=models.URLField(blank=True, verbose_name="site web"),
        ),
        migrations.AddField(
            model_name="societe",
            name="facebook",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="societe", name="observation", field=models.TextField(blank=True)
        ),
        migrations.AddField(
            model_name="societe",
            name="code_douane",
            field=models.CharField(
                blank=True,
                help_text="Société établie à l'étranger.",
                max_length=30,
                verbose_name="code douane",
            ),
        ),
        migrations.AddField(
            model_name="societe",
            name="carte_sejour",
            field=models.CharField(
                blank=True,
                help_text="Société établie à l'étranger.",
                max_length=30,
                verbose_name="carte de séjour",
            ),
        ),
        migrations.AddField(
            model_name="societe",
            name="logo",
            field=models.BinaryField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="societe",
            name="logo_type",
            field=models.CharField(blank=True, editable=False, max_length=20),
        ),
        migrations.RenameField("magasin", "region", "societe"),
        migrations.AlterField(
            model_name="magasin",
            name="societe",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="magasins",
                to="reseau.societe",
                verbose_name="société",
            ),
        ),
        migrations.RunPython(numeroter_et_renommer_droits, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="societe",
            name="code",
            field=models.CharField(
                editable=False,
                help_text="Généré : SCTE001, SCTE002…",
                max_length=20,
                unique=True,
            ),
        ),
    ]
