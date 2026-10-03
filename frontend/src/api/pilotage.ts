import { appeler } from "./client";

export type Gravite = "haute" | "moyenne" | "info";

export type Alerte = {
  code: string;
  gravite: Gravite;
  titre: string;
  detail: string;
  /** Vide pour une alerte de toute la société. */
  magasin: string;
  nombre: number;
  /** Onglet et bouton de l'application où traiter l'alerte. */
  module: string;
  ecran: string;
};

export const listerAlertes = () => appeler<Alerte[]>("/api/v1/pilotage/alertes/");

export type SectionReporting = {
  devise: string;
  ca_ttc: string;
  ca_ht: string;
  avoirs_ttc: string;
  ca_net_ttc: string;
  nombre_ventes: number;
  panier_moyen: string;
  par_magasin: { magasin: string; ca_ttc: string; nombre: number }[];
  par_jour: { jour: string; ca_ttc: string; nombre: number }[];
  par_vendeur: { vendeur: string; ca_ttc: string; nombre: number }[];
  par_famille: { famille: string; ca_ttc: string; quantite: number }[];
  encaissements: { mode: string; montant: string }[];
};

export const lireReporting = (filtre: { du: string; au: string; magasin: string }) =>
  appeler<SectionReporting[]>(
    `/api/v1/pilotage/reporting/?${new URLSearchParams(
      Object.fromEntries(Object.entries(filtre).filter(([, valeur]) => valeur)),
    )}`,
  );
