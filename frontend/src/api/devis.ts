import type { ModePaiement, Vente } from "./caisse";
import { appeler } from "./client";

export type StatutDevis = "en_cours" | "accepte" | "refuse" | "encaisse";
export type Oeil = "" | "od" | "og";

export type LigneDevis = {
  article?: string;
  libelle: string;
  oeil: Oeil;
  quantite: number;
  prix_unitaire_ttc?: string;
  remise_pct: string;
  taux_tva?: string;
  total_ttc: string;
};

export type Devis = {
  id: string;
  numero: string;
  /** Code du magasin. */
  magasin?: string;
  client: { id: string; nom: string; matricule_fiscal: string };
  prescription: { id: string; type: string; date_prescription: string } | null;
  etabli_par?: string;
  cree_le?: string;
  valable_jusqu_au: string;
  statut: StatutDevis;
  devise: string;
  total_ht?: string;
  total_tva?: string;
  total_ttc: string;
  remarques?: string;
  /** N° du ticket, une fois encaissé. */
  vente: string | null;
  lignes: LigneDevis[];
};

export type FiltresDevis = { numero?: string; statut?: StatutDevis | "" };

export type SaisieDevis = {
  magasin: string;
  client: string;
  prescription?: string;
  lignes: { article: string; quantite: number; remise_pct?: string; oeil?: Oeil }[];
};

export const listerDevis = (client: string) =>
  appeler<{ results: Devis[] }>(`/api/v1/devis/?${new URLSearchParams({ client })}`).then((page) => page.results);

/** Tous les devis du périmètre, les plus récents d'abord ; le n° se cherche en entier. */
export const chercherDevis = (filtres: FiltresDevis, page = 1) => {
  const parametres = new URLSearchParams({ page: String(page) });
  Object.entries(filtres).forEach(([cle, valeur]) => {
    if (valeur?.trim()) parametres.set(cle, valeur.trim());
  });
  return appeler<{ count: number; results: Devis[] }>(`/api/v1/devis/?${parametres}`);
};

export const lireDevis = (id: string) => appeler<Devis>(`/api/v1/devis/${id}/`);

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
