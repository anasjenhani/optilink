import type { ModePaiement, Vente } from "./caisse";
import { appeler } from "./client";

export type StatutDevis = "en_cours" | "accepte" | "refuse" | "encaisse";
export type Oeil = "" | "od" | "og";

export type Devis = {
  id: string;
  numero: string;
  client: { id: string; nom: string; matricule_fiscal: string };
  prescription: { id: string; type: string; date_prescription: string } | null;
  valable_jusqu_au: string;
  statut: StatutDevis;
  devise: string;
  total_ttc: string;
  vente: string | null;
  lignes: { libelle: string; oeil: Oeil; quantite: number; remise_pct: string; total_ttc: string }[];
};

export type SaisieDevis = {
  magasin: string;
  client: string;
  prescription?: string;
  lignes: { article: string; quantite: number; remise_pct?: string; oeil?: Oeil }[];
};

export const listerDevis = (client: string) =>
  appeler<{ results: Devis[] }>(`/api/v1/devis/?${new URLSearchParams({ client })}`).then((page) => page.results);

export const etablirDevis = (saisie: SaisieDevis) =>
  appeler<Devis>("/api/v1/devis/", { methode: "POST", corps: saisie });

export const accepterDevis = (id: string) => appeler<Devis>(`/api/v1/devis/${id}/accepter/`, { methode: "POST" });

export const refuserDevis = (id: string) => appeler<Devis>(`/api/v1/devis/${id}/refuser/`, { methode: "POST" });

/** Encaisse au prix du devis ; renvoie le ticket. En commande, le paiement est l'acompte. */
export const encaisserDevis = (
  id: string,
  paiement: { mode: ModePaiement; montant: string },
  commande = false,
  peniche?: number,
) =>
  appeler<Vente>(`/api/v1/devis/${id}/encaisser/`, {
    methode: "POST",
    corps: {
      paiements: Number(paiement.montant) > 0 ? [paiement] : [],
      commande,
      ...(commande ? { peniche } : {}),
    },
  });
