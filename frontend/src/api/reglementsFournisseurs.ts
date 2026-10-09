import { appeler } from "./client";

export type ModeReglementFournisseur = "especes" | "cheque" | "virement" | "traite";

export const MODES_REGLEMENT_FOURNISSEUR: { valeur: ModeReglementFournisseur; libelle: string }[] = [
  { valeur: "virement", libelle: "Virement" },
  { valeur: "cheque", libelle: "Chèque" },
  { valeur: "traite", libelle: "Traite" },
  { valeur: "especes", libelle: "Espèces" },
];

export type ImputationReglement = {
  facture: string;
  facture_numero: string;
  reference_fournisseur: string;
  date_reference: string;
  facture_total_ttc: string;
  montant: string;
  le: string;
};

export type ReglementFournisseur = {
  id: string;
  numero: string;
  magasin: string;
  magasin_nom: string;
  societe: string;
  societe_matricule: string;
  societe_adresse: string;
  devise: string;
  decimales: number;
  fournisseur: string;
  fournisseur_nom: string;
  fournisseur_matricule: string;
  fournisseur_adresse: string;
  date_reglement: string;
  mode: ModeReglementFournisseur;
  mode_libelle: string;
  reference: string;
  banque: string;
  echeance: string | null;
  statut: "a_echoir" | "debite";
  statut_libelle: string;
  debite_le: string | null;
  montant: string;
  taux_retenue: string;
  retenue: string;
  total_regle: string;
  disponible: string;
  observation: string;
  imputations: ImputationReglement[];
  cree_par: string;
  cree_le: string;
};

export type FactureARegler = {
  id: string;
  numero: string;
  reference_fournisseur: string;
  date_reference: string;
  total_ttc: string;
  regle: string;
  reste: string;
};

export type SituationFournisseur = {
  factures: FactureARegler[];
  avances: { id: string; numero: string; date_reglement: string; disponible: string }[];
  total_reste: string;
  total_avances: string;
};

export type LigneImputation = { facture: string; montant: string };

export type SaisieReglementFournisseur = {
  magasin: string;
  fournisseur: string;
  date_reglement: string;
  mode: ModeReglementFournisseur;
  montant: string;
  taux_retenue?: string;
  retenue?: string;
  reference?: string;
  banque?: string;
  echeance?: string | null;
  observation?: string;
  lignes: LigneImputation[];
};

export type FiltresReglements = Partial<Record<"fournisseur" | "magasin" | "mode" | "statut" | "du" | "au", string>>;

const URL = "/api/v1/reglements-fournisseurs/";

export const listerReglementsFournisseurs = (filtres: FiltresReglements) => {
  const parametres = new URLSearchParams();
  Object.entries(filtres).forEach(([cle, valeur]) => {
    if (valeur) parametres.set(cle, valeur);
  });
  return appeler<{ results: ReglementFournisseur[] }>(`${URL}?${parametres}`).then((page) => page.results);
};

export const situationFournisseur = (magasin: string, fournisseur: string) =>
  appeler<SituationFournisseur>(`${URL}situation/?${new URLSearchParams({ magasin, fournisseur })}`);

export const reglerFournisseur = (saisie: SaisieReglementFournisseur) =>
  appeler<ReglementFournisseur>(URL, { methode: "POST", corps: saisie });

export const imputerAvance = (id: string, le: string, lignes: LigneImputation[]) =>
  appeler<ReglementFournisseur>(`${URL}${id}/imputer/`, { methode: "POST", corps: { le, lignes } });

export const debiterReglement = (id: string, le: string) =>
  appeler<ReglementFournisseur>(`${URL}${id}/debiter/`, { methode: "POST", corps: { le } });

export const annulerReglement = (id: string) => appeler<void>(`${URL}${id}/`, { methode: "DELETE" });
