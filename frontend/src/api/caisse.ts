import { appeler } from "./client";

export type Article = {
  id: string;
  reference: string;
  libelle: string;
  famille: string;
  prix_vente_ttc: string;
  taux_tva: string;
  devise: string;
  stock: number | null;
};

export type ModePaiement = "carte" | "especes" | "cheque";

export type Vente = {
  id: string;
  numero: string;
  devise: string;
  total_ttc: string;
  timbre_fiscal: string;
  net_a_payer: string;
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
