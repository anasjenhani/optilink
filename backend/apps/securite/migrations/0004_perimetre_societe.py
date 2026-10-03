import django.db.models.deletion
from django.db import migrations, models


def vers_societe(apps, schema_editor):
    apps.get_model("securite", "Affectation").objects.filter(portee="region").update(
        portee="societe"
    )
    Group = apps.get_model("auth", "Group")
    if not Group.objects.filter(name="Responsable société").exists():
        Group.objects.filter(name="Responsable régional").update(name="Responsable société")


def vers_region(apps, schema_editor):
    apps.get_model("securite", "Affectation").objects.filter(portee="societe").update(
        portee="region"
    )
    apps.get_model("auth", "Group").objects.filter(name="Responsable société").update(
        name="Responsable régional"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("reseau", "0005_societes"),
        ("securite", "0003_journaux_en_ajout_seul"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="affectation", name="affectation_perimetre_coherent"
        ),
        migrations.RenameField("affectation", "region", "societe"),
        migrations.AlterField(
            model_name="affectation",
            name="societe",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="reseau.societe",
                verbose_name="société",
            ),
        ),
        migrations.AlterField(
            model_name="affectation",
            name="portee",
            field=models.CharField(
                choices=[
                    ("magasin", "Magasin"),
                    ("societe", "Société"),
                    ("reseau", "Tout le réseau"),
                ],
                max_length=10,
            ),
        ),
        migrations.RunPython(vers_societe, vers_region),
        migrations.AddConstraint(
            model_name="affectation",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("magasin__isnull", False),
                        ("portee", "magasin"),
                        ("societe__isnull", True),
                    ),
                    models.Q(
                        ("magasin__isnull", True),
                        ("portee", "societe"),
                        ("societe__isnull", False),
                    ),
                    models.Q(
                        ("magasin__isnull", True),
                        ("portee", "reseau"),
                        ("societe__isnull", True),
                    ),
                    _connector="OR",
                ),
                name="affectation_perimetre_coherent",
            ),
        ),
    ]
