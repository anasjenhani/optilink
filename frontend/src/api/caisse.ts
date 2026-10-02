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
  reste_a_payer: string;
  facture: string | null;
  client: { id: string; nom: string; matricule_fiscal: string } | null;
  lignes: { libelle: string; quantite: number; total_ttc: string }[];
};

export type SaisieVente = {
  magasin: string;
  client?: string;
  lignes: { article: string; quantite: number }[];
  paiements: { mode: ModePaiement; montant: string }[];
};

export const chercherArticles = (magasin: string, recherche: string) =>
  appeler<{ results: Article[] }>(
    `/api/v1/articles/?${new URLSearchParams({ magasin, recherche })}`,
  ).then((page) => page.results);

export const encaisser = (saisie: SaisieVente) =>
  appeler<Vente>("/api/v1/ventes/", { methode: "POST", corps: saisie });

export type Facture = {
  id: string;
  numero: string;
  vente: string;
  client: { id: string; nom: string; matricule_fiscal: string };
  devise: string;
  total_ttc: string;
  timbre_fiscal: string;
  net_a_payer: string;
};

export const trouverVente = (numero: string) =>
  appeler<{ results: Vente[] }>(`/api/v1/ventes/?${new URLSearchParams({ numero })}`).then(
    (page) => page.results[0] ?? null,
  );

/** La facture n'est acceptée que pour une vente entièrement payée ; le client règle le timbre. */
export const genererFacture = (saisie: { vente: string; client?: string; mode_paiement_timbre?: ModePaiement }) =>
  appeler<Facture>("/api/v1/factures/", { methode: "POST", corps: saisie });
