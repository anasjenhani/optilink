import type { ModePaiement } from "./caisse";
import { appeler } from "./client";

export type Avoir = {
  id: string;
  numero: string;
  vente: string;
  facture: string | null;
  annulation: boolean;
  motif: string;
  devise: string;
  total_ttc: string;
  montant_rembourse: string;
  mode_remboursement: string;
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
