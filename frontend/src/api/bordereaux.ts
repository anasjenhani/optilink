import { appeler } from "./client";

export type StatutBordereau = "preparation" | "envoye" | "regle";
export type ModeReglementBordereau = "virement" | "cheque";

export type PecBordereau = {
  id: string;
  vente_numero: string;
  vente_date: string;
  vente_total_ttc: string;
  client: string | null;
  numero_affilie: string;
  numero_dossier: string;
  montant: string;
  montant_regle: string | null;
  motif_rejet: string;
  statut: string;
  statut_libelle: string;
  lignes: { libelle: string; quantite: number; total_ttc: string }[];
};

export type Bordereau = {
  id: string;
  numero: string;
  magasin: string;
  magasin_nom: string;
  devise: string;
  decimales: number;
  organisme: string;
  organisme_nom: string;
  organisme_type: string;
  statut: StatutBordereau;
  statut_libelle: string;
  envoye_le: string | null;
  regle_le: string | null;
  mode_reglement: ModeReglementBordereau | "";
  mode_reglement_libelle: string;
  reference_reglement: string;
  observation: string;
  total: string;
  total_regle: string | null;
  cree_le: string;
  cree_par: string;
  prises_en_charge: PecBordereau[];
};

export type LigneReglement = { prise_en_charge: string; montant_regle: string; motif_rejet: string };

export const listerBordereaux = (statut = "") =>
  appeler<{ results: Bordereau[] }>(
    `/api/v1/bordereaux-pec/${statut ? `?${new URLSearchParams({ statut })}` : ""}`,
  ).then((page) => page.results);

export const pecAEnvoyer = (magasin: string, organisme: string) =>
  appeler<PecBordereau[]>(`/api/v1/bordereaux-pec/a-envoyer/?${new URLSearchParams({ magasin, organisme })}`);

export const preparerBordereau = (saisie: {
  magasin: string;
  organisme: string;
  prises_en_charge: string[];
  observation?: string;
}) => appeler<Bordereau>("/api/v1/bordereaux-pec/", { methode: "POST", corps: saisie });

export const modifierBordereau = (id: string, prises_en_charge: string[]) =>
  appeler<Bordereau>(`/api/v1/bordereaux-pec/${id}/`, { methode: "PATCH", corps: { prises_en_charge } });

export const supprimerBordereau = (id: string) => appeler<void>(`/api/v1/bordereaux-pec/${id}/`, { methode: "DELETE" });

export const envoyerBordereau = (id: string, le: string) =>
  appeler<Bordereau>(`/api/v1/bordereaux-pec/${id}/envoyer/`, { methode: "POST", corps: { le } });

export const reglerBordereau = (
  id: string,
  reglement: { le: string; mode: ModeReglementBordereau; reference: string; lignes: LigneReglement[] },
) => appeler<Bordereau>(`/api/v1/bordereaux-pec/${id}/regler/`, { methode: "POST", corps: reglement });
