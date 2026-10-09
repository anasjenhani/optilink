import type { Famille } from "./caisse";
import { appeler } from "./client";

export type LigneArticle = { article: string; reference: string; libelle: string; famille: string; quantite: number };
export type LigneSaisie = { article: string; quantite: number };

export type TypeSortie = "sortie" | "casse";

export type BonSortie = {
  id: string;
  numero: string;
  magasin: string;
  type: TypeSortie;
  type_libelle: string;
  motif: string;
  observation: string;
  cree_le: string;
  cree_par: string;
  total_articles: number;
  lignes: LigneArticle[];
};

export const sortirDuStock = (saisie: {
  magasin: string;
  type: TypeSortie;
  motif: string;
  observation: string;
  lignes: LigneSaisie[];
}) => appeler<BonSortie>("/api/v1/bons-sortie/", { methode: "POST", corps: saisie });

export const listerBonsSortie = (type: TypeSortie) =>
  appeler<{ results: BonSortie[] }>(`/api/v1/bons-sortie/?${new URLSearchParams({ type })}`).then((p) => p.results);

export type StatutDemande = "en_attente" | "servie" | "refusee" | "annulee";

export type DemandeTransfert = {
  id: string;
  numero: string;
  magasin: string;
  magasin_id: string;
  aupres_de: string;
  aupres_de_id: string;
  statut: StatutDemande;
  statut_libelle: string;
  observation: string;
  cree_le: string;
  demandee_par: string;
  traitee_par: string;
  traitee_le: string | null;
  motif_refus: string;
  transfert: string | null;
  lignes: (LigneArticle & { quantite_servie: number })[];
};

export const demanderTransfert = (saisie: {
  magasin: string;
  aupres_de: string;
  observation: string;
  lignes: LigneSaisie[];
}) => appeler<DemandeTransfert>("/api/v1/demandes-transfert/", { methode: "POST", corps: saisie });

export const listerDemandes = (sens: "recues" | "envoyees") =>
  appeler<{ results: DemandeTransfert[] }>(`/api/v1/demandes-transfert/?${new URLSearchParams({ sens })}`).then(
    (p) => p.results,
  );

export const servirDemande = (id: string, lignes: LigneSaisie[]) =>
  appeler<DemandeTransfert>(`/api/v1/demandes-transfert/${id}/servir/`, { methode: "POST", corps: { lignes } });

export const refuserDemande = (id: string, motif: string) =>
  appeler<DemandeTransfert>(`/api/v1/demandes-transfert/${id}/refuser/`, { methode: "POST", corps: { motif } });

export const annulerDemande = (id: string) =>
  appeler<DemandeTransfert>(`/api/v1/demandes-transfert/${id}/annuler/`, { methode: "POST" });

export type LigneReassort = {
  article: string;
  reference: string;
  libelle: string;
  famille: string;
  vendu: number;
  stock: number;
  stock_depot: number | null;
  propose: number;
};

export const proposerReassort = (filtres: { magasin: string; du: string; au: string; famille: Famille | "" }) => {
  const params = new URLSearchParams({ magasin: filtres.magasin, du: filtres.du, au: filtres.au });
  if (filtres.famille) params.set("famille", filtres.famille);
  return appeler<LigneReassort[]>(`/api/v1/demandes-transfert/reassort/?${params}`);
};

export type StockADate = {
  date: string;
  magasin: string;
  articles: number;
  quantite: number;
  valeur_achat: string;
  lignes: {
    article: string;
    reference: string;
    libelle: string;
    famille: string;
    quantite: number;
    valeur_achat: string | null;
  }[];
};

export const lireStockADate = (filtres: {
  magasin: string;
  date: string;
  famille: Famille | "";
  recherche: string;
}) => {
  const params = new URLSearchParams({ magasin: filtres.magasin, date: filtres.date });
  if (filtres.famille) params.set("famille", filtres.famille);
  if (filtres.recherche.trim()) params.set("recherche", filtres.recherche.trim());
  return appeler<StockADate>(`/api/v1/stock-a-date/?${params}`);
};
