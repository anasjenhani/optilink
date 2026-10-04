import { appeler } from "./client";

export type Etat =
  | "a_commander"
  | "commandee"
  | "montage"
  | "controle"
  | "contact_client"
  | "livree"
  | "instance";

/** Étapes du suivi qualité, dans l'ordre de l'atelier. */
export const ETATS: { valeur: Etat; libelle: string }[] = [
  { valeur: "a_commander", libelle: "Visite créée à commander" },
  { valeur: "commandee", libelle: "Commandée, en attente du BL" },
  { valeur: "montage", libelle: "Montage en cours" },
  { valeur: "controle", libelle: "Contrôle qualité" },
  { valeur: "contact_client", libelle: "Client prévenu" },
  { valeur: "livree", libelle: "Livrée" },
  { valeur: "instance", libelle: "En instance" },
];

type ClientLigne = { numero: number; nom: string; telephone: string } | null;

export type LigneSuivi = {
  id: string;
  numero: string;
  magasin: string;
  cree_le: string;
  client: ClientLigne;
  peniche: number | null;
  monture: { reference: string; code_barres: string } | null;
  type: "verre" | "lentille" | "autre";
  stockable: boolean;
  etat: Etat;
  etat_libelle: string;
  observation: string;
  livraison_prevue_le: string | null;
  reste_a_payer: string;
};

export type FiltresSuivi = { magasin?: string; annee?: number; mois?: number; etat?: Etat; type?: string };

export function listerSuivi(filtres: FiltresSuivi) {
  const parametres = new URLSearchParams();
  for (const [cle, valeur] of Object.entries(filtres)) {
    if (valeur !== undefined && valeur !== "") parametres.set(cle, String(valeur));
  }
  return appeler<LigneSuivi[]>(`/api/v1/ventes/suivi/?${parametres}`);
}

export const changerEtape = (vente: string, etape: Etat, observation: string) =>
  appeler(`/api/v1/ventes/${vente}/etape/`, { methode: "POST", corps: { etape, observation } });

export type LigneJournee = {
  id: string;
  numero: string;
  cree_le: string;
  client: ClientLigne;
  vendeur: string;
  total_ttc: string;
  regle: string;
  /** Organisme de prise en charge du client (CNAM, assurance, mutuelle). */
  pec_client: string | null;
  /** Part prise en charge sur cette visite. */
  pec_visite: string;
  reste: string;
  soldee: boolean;
  livree: boolean;
  commande: boolean;
  facture: string | null;
};

export type Journee = {
  date: string;
  magasin: string;
  devise: string;
  nombre_ventes: number;
  total_ventes: string;
  regle_sur_ventes: string;
  pris_en_charge: string;
  reste_sur_ventes: string;
  encaisse: string;
  encaisse_par_mode: { mode: string; montant: string }[];
  ventes: LigneJournee[];
};

export const lireJournee = (magasin: string, date: string) =>
  appeler<Journee>(`/api/v1/ventes/journee/?${new URLSearchParams({ magasin, date })}`);
