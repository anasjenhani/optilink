import { appeler } from "./client";

export type Pays = {
  code: string;
  nom: string;
  devise: string;
  decimales: number;
  indicatif_telephonique: string;
  timbre_fiscal: string;
  libelle_identifiant_prescripteur: string;
  /** Taux de TVA du pays (« 19.00 »…). */
  taux_tva?: string[];
};

export type Magasin = {
  id: string;
  code: string;
  nom: string;
  societe: string;
  societe_id: string;
  ville: string;
  pays: Pays;
  nombre_peniches: number;
};

export const listerMagasins = () => appeler<{ results: Magasin[] }>("/api/v1/magasins/").then((page) => page.results);
