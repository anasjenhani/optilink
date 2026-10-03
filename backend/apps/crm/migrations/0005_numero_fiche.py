from django.db import migrations, models


def numeroter(apps, schema_editor):
    Client = apps.get_model("crm", "Client")
    for numero, client in enumerate(Client.objects.order_by("cree_le", "pk"), start=1):
        client.numero = numero
        client.save(update_fields=["numero"])


class Migration(migrations.Migration):
    dependencies = [("crm", "0004_fiche_client_complete")]

    operations = [
        migrations.AddField(
            model_name="client",
            name="numero",
            field=models.PositiveIntegerField(editable=False, null=True, verbose_name="n° de fiche"),
        ),
        migrations.RunPython(numeroter, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="client",
            name="numero",
            field=models.PositiveIntegerField(
                editable=False,
                help_text="Numéro de fiche client, attribué à la création, commun à tout le réseau.",
                unique=True,
                verbose_name="n° de fiche",
            ),
        ),
    ]
