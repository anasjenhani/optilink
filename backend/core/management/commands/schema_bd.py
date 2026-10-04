"""Schéma de la base de données, généré depuis les modèles Django.

``python manage.py schema_bd`` réécrit ``docs/base-de-donnees.md`` : une section par module,
la liste de ses tables et un diagramme entité-relation (Mermaid, affiché par GitHub).
``--check`` échoue si le fichier n'est plus à jour : la CI le lance à chaque modification.
"""

from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

FICHIER = Path(settings.BASE_DIR).parent / "docs" / "base-de-donnees.md"

# Types Django vers des types SQL lisibles (PostgreSQL).
TYPES = {
    "AutoField": "int",
    "BigAutoField": "bigint",
    "BigIntegerField": "bigint",
    "BinaryField": "bytea",
    "BooleanField": "bool",
    "CharField": "varchar",
    "DateField": "date",
    "DateTimeField": "timestamptz",
    "DecimalField": "numeric",
    "DurationField": "interval",
    "EmailField": "varchar",
    "FileField": "varchar",
    "FloatField": "float",
    "GenericIPAddressField": "inet",
    "ImageField": "varchar",
    "IntegerField": "int",
    "JSONField": "jsonb",
    "PositiveIntegerField": "int",
    "PositiveSmallIntegerField": "smallint",
    "SlugField": "varchar",
    "SmallIntegerField": "smallint",
    "TextField": "text",
    "TimeField": "time",
    "URLField": "varchar",
    "UUIDField": "uuid",
}


def _nom(modele):
    return f"{modele._meta.app_label}_{modele.__name__}"


def _texte(valeur):
    return str(valeur).replace('"', "'")


def _type(champ):
    if champ.is_relation:
        return TYPES.get(champ.target_field.get_internal_type(), "int")
    return TYPES.get(champ.get_internal_type(), champ.get_internal_type().lower())


def _colonnes(modele):
    for champ in modele._meta.concrete_fields:
        cles = []
        if champ.primary_key:
            cles.append("PK")
        if champ.is_relation:
            cles.append("FK")
        elif champ.unique and not champ.primary_key:
            cles.append("UK")
        attribut = " ".join([_type(champ), champ.column, ",".join(cles)]).strip()
        yield f'        {attribut} "{_texte(champ.verbose_name)}"'


def _relations(modele):
    """Clés étrangères et liens plusieurs-à-plusieurs, au format Mermaid."""
    for champ in modele._meta.concrete_fields:
        if not champ.is_relation:
            continue
        cible = champ.related_model
        gauche = "|o" if champ.null else "||"
        droite = "||" if champ.one_to_one else "o{"
        yield cible, f'{_nom(cible)} {gauche}--{droite} {_nom(modele)} : "{champ.name}"'
    for champ in modele._meta.local_many_to_many:
        cible = champ.related_model
        yield cible, f'{_nom(modele)} }}o--o{{ {_nom(cible)} : "{champ.name}"'


def modules():
    """Modules métier d'OptiLink (apps/…), dans l'ordre des réglages."""
    return [
        config
        for config in apps.get_app_configs()
        if config.name.startswith("apps.") and list(config.get_models())
    ]


def generer():
    lignes = [
        "# Schéma de la base de données",
        "",
        "<!-- Fichier généré par `python manage.py schema_bd` : ne pas modifier à la main. -->",
        "",
        "Base PostgreSQL d'OptiLink, une section par module. Chaque table a en général",
        "`public_id` (identifiant exposé par l'API), `cree_le` et `modifie_le`. Une table",
        "d'un autre module apparaît dans un diagramme par ses seuls liens, sans ses colonnes.",
        "",
        "Les modifications de données (qui, quand, avant et après) sont conservées dans",
        "`auditlog_logentry` ; l'historique des versions du logiciel est dans `CHANGELOG.md`.",
        "",
        "## Sommaire",
        "",
    ]
    configs = modules()
    for config in configs:
        lignes.append(
            f"- [{config.verbose_name}](#{config.label}) ({len(list(config.get_models()))} tables)"
        )
    for config in configs:
        modeles = sorted(config.get_models(), key=lambda m: m.__name__)
        lignes += ["", f'<a id="{config.label}"></a>', "", f"## {config.verbose_name}", ""]
        lignes += ["| Table | Contenu | Colonnes |", "| --- | --- | --- |"]
        for modele in modeles:
            meta = modele._meta
            contenu = _texte(meta.verbose_name).capitalize()
            if modele.__doc__ and not modele.__doc__.startswith(f"{modele.__name__}("):
                contenu += " : " + " ".join(modele.__doc__.strip().split("\n\n")[0].split())
            lignes.append(
                f"| `{meta.db_table}` | {contenu.replace('|', '/')} | {len(meta.concrete_fields)} |"
            )
        lignes += ["", "```mermaid", "erDiagram"]
        liens = []
        for modele in modeles:
            lignes.append(f"    {_nom(modele)} {{")
            lignes += list(_colonnes(modele))
            lignes.append("    }")
            liens += [lien for _cible, lien in _relations(modele)]
        lignes += [f"    {lien}" for lien in liens]
        lignes.append("```")
    return "\n".join(lignes) + "\n"


class Command(BaseCommand):
    help = "Génère docs/base-de-donnees.md, le schéma de la base (tables et relations)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check", action="store_true", help="Échoue si le fichier est à refaire."
        )

    def handle(self, *args, check=False, **options):
        contenu = generer()
        if check:
            actuel = FICHIER.read_text(encoding="utf-8") if FICHIER.exists() else ""
            if actuel != contenu:
                raise CommandError(
                    f"{FICHIER.name} n'est plus à jour : lancez `python manage.py schema_bd`."
                )
            self.stdout.write(f"{FICHIER.name} est à jour.")
            return
        FICHIER.parent.mkdir(exist_ok=True)
        FICHIER.write_text(contenu, encoding="utf-8")
        self.stdout.write(f"{FICHIER} écrit.")
