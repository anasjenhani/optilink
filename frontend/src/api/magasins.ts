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

/** Lieu de stockage d'un magasin : dépôt de vente, dépôt central ou dépôt casse. */
export type Depot = {
  id: string;
  code: string;
  nom: string;
  type: "vente" | "central" | "casse";
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
  /** « depot » : site sans dépôt de vente (le dépôt central seul). */
  type?: "magasin" | "depot";
  /** Le magasin abrite le dépôt central : les achats de la société s'y saisissent. */
  depot_central?: boolean;
  /** Dépôts actifs du magasin ; le stock se compte par dépôt. */
  depots?: Depot[];
};

/** Le magasin abrite le dépôt central de sa société. */
export const abriteLeCentral = (m: Magasin) => m.depot_central ?? m.type === "depot";

/** Le magasin du dépôt central d'abord : c'est là que se saisissent les achats quand il existe. */
export const depotDabord = (magasins: Magasin[]) =>
  [...magasins].sort((a, b) => Number(abriteLeCentral(b)) - Number(abriteLeCentral(a)));

export type DepotDuMagasin = Depot & { magasin: Magasin };

const ORDRE_DEPOTS = { central: 0, vente: 1, casse: 2 };

/** Tous les dépôts des magasins, le dépôt central d'abord. */
export const depotsDe = (magasins: Magasin[]): DepotDuMagasin[] =>
  magasins
    .flatMap((m) => (m.depots ?? []).map((d) => ({ ...d, magasin: m })))
    .sort((a, b) => ORDRE_DEPOTS[a.type] - ORDRE_DEPOTS[b.type] || a.magasin.nom.localeCompare(b.magasin.nom));

/** « Dépôt central (L'Aouina) » : le dépôt et son magasin. */
export const libelleDepot = (d: DepotDuMagasin) => `${d.nom} (${d.magasin.nom})`;

export const listerMagasins = () => appeler<{ results: Magasin[] }>("/api/v1/magasins/").then((page) => page.results);
