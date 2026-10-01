import { appeler } from "./client";

export type Pays = {
  code: string;
  nom: string;
  devise: string;
  decimales: number;
  indicatif_telephonique: string;
  timbre_fiscal: string;
  libelle_identifiant_prescripteur: string;
};

export type Magasin = { id: string; code: string; nom: string; region: string; ville: string; pays: Pays };

export const listerMagasins = () =>
  appeler<{ results: Magasin[] }>("/api/v1/magasins/").then((page) => page.results);
