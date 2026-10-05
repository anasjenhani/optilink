import { appeler } from "./client";

export type LigneTransfert = {
  article: string;
  reference: string;
  code_barres: string;
  libelle: string;
  famille: string;
  quantite: number;
};

export type TransfertResume = {
  id: string;
  numero: string;
  magasin: string;
  magasin_id: string;
  destination: string;
  destination_id: string;
  statut: "envoye" | "recu";
  statut_libelle: string;
  total_articles: number | null;
  observation: string;
  envoye_par: string;
  cree_le: string;
  recu_par: string;
  recu_le: string | null;
};

export type Transfert = TransfertResume & { lignes: LigneTransfert[] };

export type SaisieTransfert = {
  magasin: string;
  destination: string;
  observation: string;
  lignes: { article: string; quantite: number }[];
};

export type FiltresTransferts = Partial<Record<"numero" | "statut" | "magasin" | "du" | "au", string>>;

export const envoyerTransfert = (saisie: SaisieTransfert) =>
  appeler<Transfert>("/api/v1/transferts/", { methode: "POST", corps: saisie });

export const recevoirTransfert = (id: string) =>
  appeler<Transfert>(`/api/v1/transferts/${id}/recevoir/`, { methode: "POST" });

export const lireTransfert = (id: string) => appeler<Transfert>(`/api/v1/transferts/${id}/`);

export const listerTransferts = (filtres: FiltresTransferts, page = 1) => {
  const parametres = new URLSearchParams({ page: String(page) });
  Object.entries(filtres).forEach(([cle, valeur]) => {
    if (valeur?.trim()) parametres.set(cle, valeur.trim());
  });
  return appeler<{ count: number; results: TransfertResume[] }>(`/api/v1/transferts/?${parametres}`);
};
