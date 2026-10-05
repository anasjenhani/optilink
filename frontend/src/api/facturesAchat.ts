import type { BonReceptionResume } from "./achats";
import { appeler } from "./client";
import type { BonRetourResume } from "./retours";

export type BonFacture = BonReceptionResume & {
  total_remise: string;
  remise_ex: string;
  total_fodec: string;
  total_tva: string;
};

export type LigneFacture = {
  bon: string;
  article: string;
  famille: string;
  code: string;
  designation: string;
  etui: boolean;
  quantite: number;
  prix_achat_ht: string;
  montant_ht: string;
  taux_remise: string;
  montant_remise: string;
  net_ht: string;
  taux_tva: string;
  montant_ttc: string;
  numero_serie: string;
  non_conforme: boolean;
};

/** Ligne d'un bon retour : elle se déduit de la facture. */
export type LigneRetourFacture = {
  bon: string;
  article: string;
  famille: string;
  code: string;
  designation: string;
  quantite: number;
  prix_achat_ht: string;
  montant_ht: string;
  taux_remise: string;
  montant_remise: string;
  net_ht: string;
  taux_tva: string;
  montant_ttc: string;
  motif: string;
};

export type LigneTva = { taux: string; base_ht: string; montant_tva: string };

export type Totaux = {
  total_ht: string;
  total_remise: string;
  remise_ex: string;
  total_net_ht: string;
  total_fodec: string;
  total_tva: string;
  total_ttc: string;
};

export type FactureAchatResume = {
  id: string;
  numero: string;
  magasin: string;
  date_entree: string;
  fournisseur: string;
  fournisseur_code: number;
  reference_fournisseur: string;
  date_reference: string;
  total_net_ht: string;
  total_tva: string;
  total_ttc: string;
  paiement: "non_paye" | "partiel" | "paye";
  paiement_libelle: string;
  nombre_bons: number;
  cree_par: string;
  cree_le: string;
};

export type FactureAchat = FactureAchatResume &
  Totaux & {
    devise: string;
    taux_remise_ex: string;
    frais_supplementaires: string;
    timbre_fiscal: string;
    ajustement: string;
    observation: string;
    bons: BonFacture[];
    retours: BonRetourResume[];
    lignes: LigneFacture[];
    lignes_retour: LigneRetourFacture[];
    detail_tva: LigneTva[];
  };

export type SaisieFactureAchat = {
  magasin: string;
  fournisseur: string;
  reference_fournisseur: string;
  date_reference: string;
  bons: string[];
  retours: string[];
  taux_remise_ex: string;
  frais_supplementaires: string;
  timbre_fiscal: string | null;
  ajustement: string;
  observation: string;
};

export type Apercu = Totaux & {
  detail_tva: LigneTva[];
  lignes: LigneFacture[];
  lignes_retour: LigneRetourFacture[];
};

export type FiltresFactures = Partial<
  Record<"numero" | "fournisseur" | "reference_fournisseur" | "paiement" | "du" | "au", string>
>;

export const bonsAFacturer = (magasin: string, fournisseur: string) =>
  appeler<{ timbre_fiscal: string; bons: BonFacture[]; retours: BonRetourResume[] }>(
    `/api/v1/factures-achat/a-facturer/?${new URLSearchParams({ magasin, fournisseur })}`,
  );

export const apercuFacture = (saisie: SaisieFactureAchat) =>
  appeler<Apercu>("/api/v1/factures-achat/apercu/", { methode: "POST", corps: saisie });

export const enregistrerFacture = (saisie: SaisieFactureAchat) =>
  appeler<FactureAchat>("/api/v1/factures-achat/", { methode: "POST", corps: saisie });

export const lireFacture = (id: string) => appeler<FactureAchat>(`/api/v1/factures-achat/${id}/`);

export const listerFactures = (filtres: FiltresFactures, page = 1) => {
  const parametres = new URLSearchParams({ page: String(page) });
  Object.entries(filtres).forEach(([cle, valeur]) => {
    if (valeur?.trim()) parametres.set(cle, valeur.trim());
  });
  return appeler<{
    count: number;
    results: FactureAchatResume[];
    totaux: { total_net_ht: string; total_tva: string; total_ttc: string };
  }>(`/api/v1/factures-achat/?${parametres}`);
};
