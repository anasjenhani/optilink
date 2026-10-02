import { envoyerFichier } from "./client";

export type RapportImport = {
  apercu: boolean;
  lignes: number;
  crees: number;
  modifies: number;
  erreurs: { ligne: number; message: string }[];
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

export function importerCatalogue(fichier: File, apercu: boolean) {
  const formulaire = new FormData();
  formulaire.append("fichier", fichier);
  formulaire.append("apercu", String(apercu));
  return envoyerFichier<RapportImport>("/api/v1/imports/catalogue/", formulaire);
}

export function importerStock(fichier: File, magasin: string, piece: string, apercu: boolean) {
  const formulaire = new FormData();
  formulaire.append("fichier", fichier);
  formulaire.append("magasin", magasin);
  formulaire.append("piece", piece);
  formulaire.append("apercu", String(apercu));
  return envoyerFichier<RapportImport>("/api/v1/imports/stock/", formulaire);
}

/** Fichier modèle (CSV, séparateur « ; » comme l'Excel français) : la ligne d'en-tête seule. */
export function urlModele(colonnes: string[]) {
  return `data:text/csv;charset=utf-8,${encodeURIComponent(`﻿${colonnes.join(";")}\n`)}`;
}
