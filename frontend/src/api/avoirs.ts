import type { ModePaiement } from "./caisse";
import { appeler } from "./client";

export type Avoir = {
  id: string;
  numero: string;
  /** Code du magasin émetteur. */
  magasin: string;
  vente: string;
  facture: string | null;
  client: { id: string; nom: string; societe: string; matricule_fiscal: string } | null;
  annulation: boolean;
  motif: string;
  cree_le: string;
  emis_par: string;
  devise: string;
  total_ht: string;
  total_tva: string;
  total_ttc: string;
  montant_rembourse: string;
  mode_remboursement: ModePaiement | "";
  lignes: { libelle: string; quantite: number; taux_tva: string; total_ttc: string; remis_en_stock: boolean }[];
};

export type SaisieAvoir = {
  vente: string;
  motif: string;
  mode_remboursement?: ModePaiement;
} & (
  | { annulation: true; remis_en_stock?: boolean }
  | { annulation?: false; lignes: { ligne: number; quantite: number; remis_en_stock: boolean }[] }
);

/** Retour d'articles ou annulation : la vente n'est jamais modifiée, l'avoir la corrige. */
export const emettreAvoir = (saisie: SaisieAvoir) =>
  appeler<Avoir>("/api/v1/avoirs/", { methode: "POST", corps: saisie });

/** Avoirs émis, les plus récents d'abord ; ``annulation`` : "true" (annulations) ou "false" (reprises). */
export const listerAvoirs = (filtres: { numero?: string; annulation?: string }, page = 1) => {
  const parametres = new URLSearchParams({ page: String(page) });
  Object.entries(filtres).forEach(([cle, valeur]) => {
    if (valeur?.trim()) parametres.set(cle, valeur.trim());
  });
  return appeler<{ count: number; results: Avoir[] }>(`/api/v1/avoirs/?${parametres}`);
};

export const lireAvoir = (id: string) => appeler<Avoir>(`/api/v1/avoirs/${id}/`);
