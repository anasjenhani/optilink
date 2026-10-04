import { appeler } from "./client";

/** CNAM, assurance ou mutuelle qui prend en charge une partie des lunettes. */
export type Organisme = {
  id: string;
  nom: string;
  type: "caisse" | "assurance" | "mutuelle";
  type_libelle: string;
  pays: string;
};

export type StatutPec = "demandee" | "accordee" | "reglee" | "refusee";

export const STATUTS_PEC: { valeur: StatutPec; libelle: string }[] = [
  { valeur: "demandee", libelle: "Demandée" },
  { valeur: "accordee", libelle: "Accordée" },
  { valeur: "reglee", libelle: "Réglée par l'organisme" },
  { valeur: "refusee", libelle: "Refusée" },
];

export type PriseEnCharge = {
  id: string;
  vente: string;
  vente_numero: string;
  magasin: string;
  devise: string;
  client: string | null;
  organisme: string;
  organisme_nom: string;
  montant: string;
  numero_dossier: string;
  statut: StatutPec;
  statut_libelle: string;
  cree_le: string;
};

export type SaisiePec = { vente: string; organisme: string; montant: string; numero_dossier?: string };

export const listerOrganismes = () => appeler<Organisme[]>("/api/v1/organismes/");

export const listerPrisesEnCharge = (statut = "") =>
  appeler<{ results: PriseEnCharge[] }>(
    `/api/v1/prises-en-charge/${statut ? `?${new URLSearchParams({ statut })}` : ""}`,
  ).then((page) => page.results);

export const saisirPriseEnCharge = (saisie: SaisiePec) =>
  appeler<PriseEnCharge>("/api/v1/prises-en-charge/", { methode: "POST", corps: saisie });

export const changerStatutPec = (id: string, statut: StatutPec) =>
  appeler<PriseEnCharge>(`/api/v1/prises-en-charge/${id}/`, { methode: "PATCH", corps: { statut } });
