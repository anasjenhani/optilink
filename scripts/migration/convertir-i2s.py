"""Convertit les exports de l'ancien logiciel (I2S) au format d'import d'OptiLink.

Usage : python3 scripts/migration/convertir-i2s.py <dossier source> <dossier sortie>
Produit fournisseurs.csv, utilisateurs-brouillon.csv, et rapport.json (contrôles).
"""

import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

SOURCE, SORTIE = Path(sys.argv[1]), Path(sys.argv[2])
SORTIE.mkdir(parents=True, exist_ok=True)


def lire(nom, sep):
    texte = (SOURCE / nom).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    lignes = texte.split("\n")
    entete = lignes[0].split(sep)
    enregistrements, courant = [], None
    for brute in lignes[1:]:
        # Une adresse sur plusieurs lignes coupe l'enregistrement (pas de guillemets) : on recolle.
        if courant is not None:
            courant = courant + ", " + brute
        else:
            courant = brute
        if courant.count(sep) + 1 >= len(entete):
            enregistrements.append(dict(zip(entete, [c.strip() for c in courant.split(sep)])))
            courant = None
    return entete, enregistrements


def cle(texte):
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()
    texte = re.sub(r"\b(ste|societe|sté|s\.t\.e)\b", "", texte)
    return re.sub(r"[^a-z0-9]", "", texte)


def cle_mf(texte):
    return re.sub(r"[^A-Z0-9]", "", texte.upper())[:8]


def propre(texte):
    return re.sub(r"\s+", " ", texte.replace("NULL", "")).strip(" ,")


rapport = {}

# --- Banques ---------------------------------------------------------------------------
_, banques = lire("Banque.csv", ";")
noms_banques = {b["CodeBanque"]: propre(b["RaisonSociale"]) for b in banques}
rapport["banques"] = {
    "lignes": len(banques),
    "banque_de_la_societe": [b["RaisonSociale"] for b in banques if b["BanqueSoc"] == "1"],
}

# --- Fournisseurs ----------------------------------------------------------------------
_, fournisseurs = lire("FOURNISSEUR.csv", ";")
NON_FOURNISSEURS = {"****", "correction inventaire", "caisse depenses", "recap stock jribi tunis", "logiciel 1"}
COLONNES = [
    "code", "raison_sociale", "notre_code", "responsable", "fournisseur_verres", "matricule_fiscal",
    "registre_commerce", "code_douane", "forme_juridique", "capital_social", "timbre_fiscal",
    "assujetti", "fodec", "regime_tva", "numero_exoneration", "exoneration_du", "exoneration_au",
    "adresse", "code_postal", "ville", "pays", "telephone", "telephone_2", "fax", "email",
    "site_web", "banque", "rib", "observation",
]
sortie, ecartes, doublons_nom, doublons_mf, corrections = [], [], [], [], []
par_nom, par_mf = {}, {}
for f in sorted(fournisseurs, key=lambda f: (not f["CodeFournisseur"].isdigit(), int(f["CodeFournisseur"]) if f["CodeFournisseur"].isdigit() else 0)):
    nom = propre(f["RaisonSociale"])
    ancien = f["CodeFournisseur"]
    if nom.lower() in NON_FOURNISSEURS or not cle(nom):
        ecartes.append(f"{ancien} {nom}")
        continue
    if cle(nom) in par_nom:
        doublons_nom.append(f"{ancien} {nom} = {par_nom[cle(nom)]}")
        continue
    par_nom[cle(nom)] = f"{ancien} {nom}"
    mf = propre(f["MatriculeFiscale"])
    if mf.upper() in {"XX", "000", "0"}:
        corrections.append(f"{ancien} {nom} : matricule « {mf} » vidé")
        mf = ""
    if mf and cle_mf(mf) in par_mf:
        doublons_mf.append(f"{ancien} {nom} : matricule {mf} déjà sur {par_mf[cle_mf(mf)]} (matricule vidé, à vérifier)")
        mf = ""
    if mf:
        par_mf[cle_mf(mf)] = f"{ancien} {nom}"
    tels = [t.strip() for t in re.split(r"/", f["Tel1"]) if t.strip()] + ([f["Tel2"]] if f["Tel2"] else [])
    ville = propre(f["Ville1"])
    if ville.isdigit():
        corrections.append(f"{ancien} {nom} : ville « {ville} » (code de l'ancien logiciel) vidée")
        ville = ""
    site = propre(f["SiteWeb"]).lower()
    if site and not site.startswith("http"):
        site = "https://" + site
    if site and "." not in site:
        site = ""
    email = propre(f["Email"])
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}", email):
        corrections.append(f"{ancien} {nom} : e-mail « {email} » invalide vidé")
        email = ""
    adresse = propre(f["Adresse1"])
    if adresse.strip("* ") == "":
        adresse = ""
    exo = f["Exoneration"] == "1"
    regime = "Export" if f["Export"] == "1" else "Exonération" if exo else "Payer TVA"
    observation = "; ".join(x for x in [
        propre(f["Observation"]),
        f"Ancien code fournisseur : {ancien}",
        f"Famille ancienne : {f['CodeFamille']}" if f["CodeFamille"] else "",
    ] if x)
    capital = f["CapitalSocial"].replace(",", ".")
    sortie.append({
        "code": "",
        "raison_sociale": nom,
        "notre_code": "",
        "responsable": propre(f["Responsable"]),
        "fournisseur_verres": "oui" if f["FournisseurVerre"] == "1" else "non",
        "matricule_fiscal": mf,
        "registre_commerce": propre(f["RegistreCommerce"]),
        "code_douane": propre(f["CodeDouane"]),
        "forme_juridique": "",
        "capital_social": capital if capital not in ("", "0.00", "0") else "",
        "timbre_fiscal": "oui" if f["TimbreFiscal"] == "1" else "non",
        "assujetti": "oui" if f["Assujetti"] == "1" else "non",
        "fodec": "oui" if f["Fodec"] == "1" else "non",
        "regime_tva": regime,
        "numero_exoneration": propre(f["NumeroExoneration"]) if exo else "",
        "exoneration_du": f["DateDebutExoneration"][:10] if exo else "",
        "exoneration_au": f["DateFinExoneration"][:10] if exo else "",
        "adresse": adresse,
        "code_postal": propre(f["CodePostal1"]),
        "ville": ville,
        "pays": "TN",
        "telephone": tels[0] if tels else "",
        "telephone_2": tels[1] if len(tels) > 1 else "",
        "fax": propre(f["Fax1"]).strip("*"),
        "email": email,
        "site_web": site,
        "banque": noms_banques.get(f["CodeBanque"], ""),
        "rib": propre(f["RibBancaire"]),
        "observation": observation,
    })
with open(SORTIE / "fournisseurs.csv", "w", encoding="utf-8-sig", newline="") as fichier:
    ecrivain = csv.DictWriter(fichier, COLONNES, delimiter=";")
    ecrivain.writeheader()
    ecrivain.writerows(sortie)
rapport["fournisseurs"] = {
    "lignes_source": len(fournisseurs),
    "a_importer": len(sortie),
    "ecartes_non_fournisseurs": ecartes,
    "doublons_raison_sociale_fusionnes": doublons_nom,
    "matricules_en_double": doublons_mf,
    "corrections": corrections,
    "fournisseurs_verres": sum(1 for s in sortie if s["fournisseur_verres"] == "oui"),
}

# --- Magasins --------------------------------------------------------------------------
_, magasins = lire("Magasin.csv", ";")
rapport["magasins"] = [
    {"code": m["CodeMagasin"], "libelle": m["Libelle"], "depot": m["CodeDepot"],
     "matricule_fiscal": m["MatriculeFiscale"], "telephone": m["TelMagasin"],
     "prefixe_pieces": m["PrefixePieces"]}
    for m in magasins
]

# --- Utilisateurs ----------------------------------------------------------------------
_, utilisateurs = lire("Utilisateur.csv", "\t")
lignes_u, inactifs, renommes = [], [], []
vus = {}
for u in utilisateurs:
    brut = u["NomUtilisateur"]
    identifiant = re.sub(r"\s+", ".", brut.strip()).lower()
    if identifiant != brut:
        renommes.append(f"« {brut} » → {identifiant}")
    if u["Actif"] != "1":
        inactifs.append(brut.strip())
        continue
    if identifiant in vus:
        renommes.append(f"« {brut} » en double avec {vus[identifiant]}")
        continue
    vus[identifiant] = brut
    base = {
        "identifiant": identifiant,
        "prenom": propre(u["Prenom"]).title(),
        "nom": propre(u["Nom"]).title(),
        "email": "",
        "mot_de_passe": "",
        "magasin": u["CodeMagasin"],
        "societe": "",
        "ancienne_fonction": u["CodeFonction"],
        "ancien_service": u["CodeService"],
        "seuil_remise": u["SeuilRemise"],
    }
    lignes_u.append({**base, "profil": "?" + u["CodeFonction"]})
    if u["Caissier"] == "1":
        lignes_u.append({**base, "profil": "Caissier"})
with open(SORTIE / "utilisateurs-brouillon.csv", "w", encoding="utf-8-sig", newline="") as fichier:
    ecrivain = csv.DictWriter(fichier, ["identifiant", "prenom", "nom", "email", "mot_de_passe", "profil",
                                        "magasin", "societe", "ancienne_fonction", "ancien_service", "seuil_remise"], delimiter=";")
    ecrivain.writeheader()
    ecrivain.writerows(lignes_u)
fonctions = {}
for u in utilisateurs:
    if u["Actif"] == "1":
        fonctions.setdefault(u["CodeFonction"], []).append(u["NomUtilisateur"].strip())
rapport["utilisateurs"] = {
    "lignes_source": len(utilisateurs),
    "actifs": len(vus),
    "inactifs_non_importes": inactifs,
    "identifiants_adaptes": renommes,
    "fonctions": fonctions,
    "magasins_utilises": sorted({u["CodeMagasin"] for u in utilisateurs}),
}
(SORTIE / "rapport.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=1))
print(json.dumps(rapport, ensure_ascii=False, indent=1))
