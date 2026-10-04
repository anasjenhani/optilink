"""Import des clients depuis un autre logiciel (fichier Excel .xlsx ou CSV).

Les noms de colonnes courants des autres logiciels sont reconnus (« Tél », « GSM »,
« Date de naissance », « N° fiche »…). L'ancien n° de fiche est conservé : réimporter le même
fichier met les fiches à jour au lieu de créer des doublons. Comme pour le catalogue, tout le
fichier est contrôlé avant d'enregistrer quoi que ce soit, et l'import exige la vérification.
"""

from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from apps.stock.imports import Rapport, _Annuler, _booleen, _choix, _message

from .models import Client

# Colonnes du modèle d'import, dans l'ordre du fichier modèle.
COLONNES_CLIENTS = [
    "ancien_numero",
    "civilite",
    "nom",
    "prenom",
    "date_naissance",
    "telephone",
    "telephone_2",
    "email",
    "adresse",
    "code_postal",
    "ville",
    "societe",
    "matricule_fiscal",
    "accepte_relances",
    "notes",
]

# Autres noms de colonnes rencontrés dans les logiciels d'optique et les CRM (normalisés).
SYNONYMES = {
    "ancien_numero": [
        "numero",
        "n_fiche",
        "no_fiche",
        "num_fiche",
        "numero_fiche",
        "numero_de_fiche",
        "fiche",
        "code_client",
        "id_client",
        "ref_client",
        "reference_client",
        "reference",
        "id",
        "code",
    ],
    "civilite": ["titre", "civ"],
    "nom": ["nom_client", "nom_de_famille", "last_name", "lastname", "surname"],
    "prenom": ["prenom_client", "first_name", "firstname"],
    "nom_complet": ["nom_prenom", "nom_et_prenom", "nom_et_prenoms", "client", "full_name"],
    "date_naissance": [
        "date_de_naissance",
        "naissance",
        "date_naiss",
        "ne_le",
        "nee_le",
        "birthdate",
        "date_of_birth",
    ],
    "telephone": [
        "tel",
        "tel_1",
        "telephone_1",
        "mobile",
        "portable",
        "gsm",
        "gsm_1",
        "phone",
        "tel_mobile",
    ],
    "telephone_2": ["tel_2", "gsm_2", "fixe", "tel_fixe", "telephone_fixe", "domicile"],
    "email": ["e_mail", "mail", "courriel", "adresse_email", "adresse_mail"],
    "adresse": ["rue", "address", "adresse_1"],
    "code_postal": ["cp", "zip", "code_post"],
    "ville": ["localite", "city", "commune"],
    "societe": ["entreprise", "raison_sociale", "company"],
    "matricule_fiscal": ["mf", "matricule", "identifiant_fiscal"],
    "accepte_relances": ["relances", "consentement", "newsletter", "accepte_sms"],
    "notes": [
        "remarque",
        "remarques",
        "observation",
        "observations",
        "commentaire",
        "commentaires",
    ],
}
COLONNE_DE = {nom: nom for nom in [*COLONNES_CLIENTS, "nom_complet"]} | {
    autre: nom for nom, autres in SYNONYMES.items() for autre in autres
}
FORMATS_DATE = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y"]


def renommer(ligne):
    """{« tel »: …} → {« telephone »: …} ; la première colonne trouvée l'emporte."""
    resultat = {}
    for colonne, valeur in ligne.items():
        nom = COLONNE_DE.get(colonne)
        if nom and nom not in resultat:
            resultat[nom] = valeur
    return resultat


def _date(texte):
    if texte == "":
        return None
    for format_ in FORMATS_DATE:
        try:
            jour = datetime.strptime(texte, format_).date()
        except ValueError:
            continue
        if not date(1900, 1, 1) <= jour <= date.today():
            raise ValidationError(f"date_naissance : « {texte} » n'est pas plausible.")
        return jour
    raise ValidationError(f"date_naissance : « {texte} » n'est pas une date (jj/mm/aaaa).")


def _nom_et_prenom(ligne):
    nom, prenom = ligne.get("nom", ""), ligne.get("prenom", "")
    if not nom and ligne.get("nom_complet"):
        # « BEN SALAH Amira » : le nom en premier, le prénom ensuite.
        nom, _, reste = ligne["nom_complet"].partition(" ")
        prenom = prenom or reste.strip()
    if not nom:
        raise ValidationError("nom : obligatoire.")
    if not prenom:
        raise ValidationError("prenom : obligatoire.")
    return nom, prenom


def _ressemblant(client):
    """Fiche déjà en base qui semble être la même personne (téléphone, ou nom et naissance)."""
    autres = Client.objects.exclude(pk=client.pk) if client.pk else Client.objects.all()
    telephones = {t for t in (client.telephone, client.telephone_2) if t}
    critere = Q()
    if telephones:
        critere |= Q(telephone__in=telephones) | Q(telephone_2__in=telephones)
    if client.date_naissance:
        critere |= Q(
            nom__iexact=client.nom,
            prenom__iexact=client.prenom,
            date_naissance=client.date_naissance,
        )
    return autres.filter(critere).order_by("numero").first() if critere else None


def importer_clients(lignes, *, magasin, apercu=False):
    """Crée les clients (ou met à jour ceux déjà importés, par ancien n° de fiche)."""
    rapport = Rapport(apercu=apercu, lignes=len(lignes))
    colonnes = set(renommer(lignes[0][1])) if lignes else set()
    if "nom" not in colonnes and "nom_complet" not in colonnes:
        rapport.erreur(1, "Colonne obligatoire absente : nom (ou « nom et prénom »).")
        return rapport
    vus = {}
    try:
        with transaction.atomic():
            for numero, brute in lignes:
                ligne = renommer(brute)
                ancien = ligne.get("ancien_numero", "")
                if ancien and ancien in vus:
                    rapport.erreur(numero, f"Ancien n° {ancien} déjà en ligne {vus[ancien]}.")
                    continue
                if ancien:
                    vus[ancien] = numero
                try:
                    with transaction.atomic():
                        client, cree = _importer_client(ligne, ancien, magasin)
                except ValidationError as erreur:
                    rapport.erreur(numero, _message(erreur))
                    continue
                if cree:
                    rapport.crees += 1
                    double = _ressemblant(client)
                    if double:
                        rapport.alerte(
                            numero,
                            f"{client} ressemble à la fiche n° {double.numero} ({double}) : "
                            "doublon possible.",
                        )
                else:
                    rapport.modifies += 1
                    rapport.alerte(
                        numero,
                        f"Ancien n° {ancien} déjà importé (fiche n° {client.numero}) : "
                        "elle sera mise à jour.",
                    )
            if rapport.erreurs or apercu:
                raise _Annuler
    except _Annuler:
        pass
    return rapport


def _importer_client(ligne, ancien, magasin):
    client = Client.objects.filter(reference_externe=ancien).first() if ancien else None
    cree = client is None
    if cree:
        client = Client(reference_externe=ancien, magasin_origine=magasin)
    client.nom, client.prenom = _nom_et_prenom(ligne)
    if "civilite" in ligne:
        client.civilite = _choix(ligne["civilite"], _CIVILITES, "civilite")
    if "date_naissance" in ligne:
        client.date_naissance = _date(ligne["date_naissance"])
    for champ in (
        "telephone",
        "telephone_2",
        "email",
        "adresse",
        "code_postal",
        "ville",
        "societe",
        "matricule_fiscal",
        "notes",
    ):
        if champ in ligne:
            setattr(client, champ, ligne[champ])
    if "accepte_relances" in ligne:
        client.accepte_relances = _booleen(ligne["accepte_relances"])
    client.full_clean(exclude=["numero"])
    client.save()
    return client, cree


# « Madame », « Mlle », « Monsieur » : les écritures courantes en plus de Mme et M.
_CIVILITES = [
    *Client.Civilite.choices,
    (Client.Civilite.MADAME, "Madame"),
    (Client.Civilite.MADAME, "Mlle"),
    (Client.Civilite.MADAME, "Mademoiselle"),
    (Client.Civilite.MADAME, "F"),
    (Client.Civilite.MONSIEUR, "Monsieur"),
    (Client.Civilite.MONSIEUR, "Mr"),
    (Client.Civilite.MONSIEUR, "H"),
]
