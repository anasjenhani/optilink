import { appeler } from "./client";

export type Article = {
  id: string;
  reference: string;
  libelle: string;
  famille: string;
  prix_vente_ttc: string;
  taux_tva: string;
  stock: number | null;
};

export type ModePaiement = "carte" | "especes" | "cheque";

export type Vente = {
  id: string;
  numero: string;
  total_ttc: string;
  lignes: { libelle: string; quantite: number; total_ttc: string }[];
};

export type SaisieVente = {
  magasin: string;
  lignes: { article: string; quantite: number }[];
  paiements: { mode: ModePaiement; montant: string }[];
};

export const chercherArticles = (magasin: string, recherche: string) =>
  appeler<{ results: Article[] }>(
    `/api/v1/articles/?${new URLSearchParams({ magasin, recherche })}`,
  ).then((page) => page.results);

export const encaisser = (saisie: SaisieVente) =>
  appeler<Vente>("/api/v1/ventes/", { methode: "POST", corps: saisie });

/** Montants en centimes pour éviter les erreurs d'arrondi des nombres à virgule. */
export const enCentimes = (montant: string) => Math.round(Number(montant) * 100);
export const enEuros = (centimes: number) => (centimes / 100).toFixed(2);
