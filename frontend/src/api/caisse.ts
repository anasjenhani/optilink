import { appeler } from "./client";

export type Article = {
  id: string;
  reference: string;
  libelle: string;
  famille: string;
  /** Commandé au fournisseur pour chaque client (verres…) : pas de stock, vente en commande. */
  sur_commande: boolean;
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
  statut: "en_commande" | "livree" | "annulee";
  livraison_prevue_le: string | null;
  facture: string | null;
  client: { id: string; nom: string; matricule_fiscal: string } | null;
  lignes: { id: number; libelle: string; quantite: number; quantite_reprise: number; total_ttc: string }[];
};

export type SaisieVente = {
  magasin: string;
  client?: string;
  lignes: { article: string; quantite: number }[];
  paiements: { mode: ModePaiement; montant: string }[];
  /** Commande : acompte maintenant (paiements, éventuellement vides), solde à la livraison. */
  commande?: boolean;
  livraison_prevue_le?: string;
};

export type Reglement = { mode: ModePaiement; montant: string };

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

export const listerCommandes = (magasin: string) =>
  appeler<{ results: Vente[] }>(
    `/api/v1/ventes/?${new URLSearchParams({ statut: "en_commande", magasin__public_id: magasin })}`,
  ).then((page) => page.results);

export const reglerCommande = (vente: string, reglement: Reglement) =>
  appeler<Vente>(`/api/v1/ventes/${vente}/reglement/`, { methode: "POST", corps: { paiements: [reglement] } });

/** Livre la commande ; le solde éventuel est encaissé en même temps. */
export const livrerCommande = (vente: string, solde: Reglement | null) =>
  appeler<Vente>(`/api/v1/ventes/${vente}/livrer/`, {
    methode: "POST",
    corps: solde ? { paiements: [solde] } : {},
  });
