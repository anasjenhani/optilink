import { envoyerFichier } from "./client";

export type RapportImport = {
  apercu: boolean;
  lignes: number;
  crees: number;
  modifies: number;
  erreurs: { ligne: number; message: string }[];
  /** Articles déjà au catalogue ou en stock, clients déjà importés ou en double : à regarder. */
  alertes: { ligne: number; message: string }[];
  /** Rendu par une vérification sans erreur ; l'import de ce même fichier l'exige. */
  jeton: string;
};

export const COLONNES_CATALOGUE = [
  "reference",
  "libelle",
  "famille",
  "fournisseur",
  "reference_fournisseur",
  "code_barres",
  "sur_commande",
  "prix_ttc",
  "tva",
  "marque",
  "modele",
  "couleur",
  "matiere",
  "type",
  "genre",
  "calibre",
  "pont",
  "branche",
  "solaire",
  "gamme",
  "geometrie",
  "indice",
  "traitements",
  "photochromique",
  "teinte",
  "diametre",
  "renouvellement",
  "rayon",
  "puissance",
  "cylindre",
  "axe",
  "addition",
  "lentilles_par_boite",
];
export const COLONNES_STOCK = ["code_barres", "reference", "quantite"];
export const COLONNES_CLIENTS = [
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
];

/** Sans jeton : vérification. Avec le jeton de la vérification : import. */
export function importerCatalogue(fichier: File, jeton?: string) {
  const formulaire = new FormData();
  formulaire.append("fichier", fichier);
  formulaire.append("apercu", String(!jeton));
  if (jeton) formulaire.append("jeton", jeton);
  return envoyerFichier<RapportImport>("/api/v1/imports/catalogue/", formulaire);
}

export function importerStock(fichier: File, magasin: string, piece: string, jeton?: string) {
  const formulaire = new FormData();
  formulaire.append("fichier", fichier);
  formulaire.append("magasin", magasin);
  formulaire.append("piece", piece);
  formulaire.append("apercu", String(!jeton));
  if (jeton) formulaire.append("jeton", jeton);
  return envoyerFichier<RapportImport>("/api/v1/imports/stock/", formulaire);
}

/** Clients exportés d'un autre logiciel, rattachés à leur magasin d'origine. */
export function importerClients(fichier: File, magasin: string, jeton?: string) {
  const formulaire = new FormData();
  formulaire.append("fichier", fichier);
  formulaire.append("magasin", magasin);
  formulaire.append("apercu", String(!jeton));
  if (jeton) formulaire.append("jeton", jeton);
  return envoyerFichier<RapportImport>("/api/v1/imports/clients/", formulaire);
}

/** Fichier modèle (CSV, séparateur « ; » comme l'Excel français) : la ligne d'en-tête seule. */
export function urlModele(colonnes: string[]) {
  return `data:text/csv;charset=utf-8,${encodeURIComponent(`﻿${colonnes.join(";")}\n`)}`;
}
