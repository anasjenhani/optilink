from django.db import migrations


class Migration(migrations.Migration):
    """Réunit la corbeille et le journal des droits, arrivés en parallèle."""

    dependencies = [
        ("securite", "0006_corbeille"),
        ("securite", "0006_journal_des_droits"),
    ]

    operations = []
