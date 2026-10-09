import type { ModePaiement, Piece } from "./caisse";
import { appeler } from "./client";

export type VenteDue = {
  id: string;
  numero: string;
  cree_le: string;
  livree_le: string | null;
  magasin: string;
  devise: string;
  total_ttc: string;
  reste_a_payer: string;
  a_credit: boolean;
  credit_echeance: string | null;
  impayes: number;
  client: string | null;
  client_id: string | null;
  client_telephone: string;
  en_retard: boolean;
};

export type PaiementSuivi = {
  id: number;
  mode: ModePaiement;
  mode_libelle: string;
  montant: string;
  recu_le: string;
  reference: string;
  banque: string;
  echeance: string | null;
  statut: "encaisse" | "impaye" | "remplace";
  statut_libelle: string;
  impaye_le: string | null;
  motif_impaye: string;
  vente: string;
  vente_numero: string;
  vente_reste: string;
  devise: string;
  magasin: string;
  client: string | null;
  client_id: string | null;
  client_telephone: string;
};

export type ClientListeNoire = {
  id: string;
  numero: number;
  nom: string;
  telephone: string;
  motif_liste_noire: string;
  liste_noire_le: string | null;
};

const URL = "/api/v1/credit-clients/";

export const listerVentesDues = () => appeler<VenteDue[]>(`${URL}ventes-dues/`);

export const listerChequesClients = (vue: "portefeuille" | "impayes" | "cheques") =>
  appeler<PaiementSuivi[]>(`${URL}paiements/?${new URLSearchParams({ vue })}`);

export const declarerImpaye = (id: number, saisie: { le: string; motif: string; liste_noire: boolean }) =>
  appeler<PaiementSuivi>(`${URL}paiements/${id}/impaye/`, { methode: "POST", corps: saisie });

export const changerCheque = (id: number, nouveau: { mode: ModePaiement } & Piece) =>
  appeler<PaiementSuivi>(`${URL}paiements/${id}/changer/`, { methode: "POST", corps: nouveau });

export const listerListeNoire = () => appeler<ClientListeNoire[]>(`${URL}liste-noire/`);

export const mettreEnListeNoire = (client: string, motif: string) =>
  appeler<ClientListeNoire>(`${URL}liste-noire/`, { methode: "POST", corps: { client, motif } });

export const retirerDeListeNoire = (client: string) =>
  appeler<void>(`${URL}liste-noire/${client}/`, { methode: "DELETE" });
