import { appeler } from "./client";

/** Ligne non conforme d'un bon de réception, à renvoyer au fournisseur. */
export type NonConforme = {
  id: number;
  bon: string;
  numero_bl: string;
  date_bl: string;
  magasin: string;
  code: string;
  designation: string;
  quantite: number;
  prix_achat_ht: string;
  taux_remise: string;
  taux_tva: string;
  net_ht: string;
  montant_ttc: string;
  motif: string;
};

export type LigneRetour = {
  article: string;
  famille: string;
  code: string;
  designation: string;
  quantite: number;
  prix_achat_ht: string;
  taux_remise: string;
  taux_tva: string;
  net_ht: string;
  montant_ttc: string;
  motif: string;
  bon_reception: string;
};

export type BonRetourResume = {
  id: string;
  numero: string;
  magasin: string;
  date_retour: string;
  fournisseur: string;
  fournisseur_code: number;
  motif: string;
  etat: "non_facture" | "facture";
  etat_libelle: string;
  facture: string | null;
  total_articles: number | null;
  total_ht: string;
  total_remise: string;
  total_net_ht: string;
  total_fodec: string;
  total_tva: string;
  total_ttc: string;
  cree_par: string;
  cree_le: string;
};

export type BonRetour = BonRetourResume & { devise: string; observation: string; lignes: LigneRetour[] };

export type SaisieLigneRetour =
  | { ligne_reception: number; motif?: string }
  | {
      article: string;
      quantite: number;
      prix_achat_ht: string;
      taux_remise: string;
      taux_tva: string;
      motif?: string;
    };

export type SaisieBonRetour = {
  magasin: string;
  fournisseur: string;
  date_retour: string;
  motif: string;
  observation: string;
  lignes: SaisieLigneRetour[];
};

export type FiltresRetours = Partial<Record<"numero" | "fournisseur" | "etat" | "du" | "au", string>>;

export const nonConformesARetourner = (magasin: string, fournisseur: string) =>
  appeler<NonConforme[]>(`/api/v1/bons-retour/a-retourner/?${new URLSearchParams({ magasin, fournisseur })}`);

export const enregistrerRetour = (saisie: SaisieBonRetour) =>
  appeler<BonRetour>("/api/v1/bons-retour/", { methode: "POST", corps: saisie });

export const lireRetour = (id: string) => appeler<BonRetour>(`/api/v1/bons-retour/${id}/`);

export const listerRetours = (filtres: FiltresRetours, page = 1) => {
  const parametres = new URLSearchParams({ page: String(page) });
  Object.entries(filtres).forEach(([cle, valeur]) => {
    if (valeur?.trim()) parametres.set(cle, valeur.trim());
  });
  return appeler<{
    count: number;
    results: BonRetourResume[];
    totaux: { total_net_ht: string; total_tva: string; total_ttc: string };
  }>(`/api/v1/bons-retour/?${parametres}`);
};
