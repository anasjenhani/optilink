import { appeler } from "./client";

export type TypeFactureGroupee = "client" | "mensuelle";

export type VenteAFacturer = {
  id: string;
  numero: string;
  livree_le: string | null;
  client: string | null;
  client_id: string | null;
  total_ht: string;
  total_tva: string;
  total_ttc: string;
  reste_a_payer: string;
};

export type DetailTva = {
  taux: string;
  total_ht: string;
  total_tva: string;
  total_ttc: string;
};

export type FactureGroupee = {
  id: string;
  numero: string;
  type: TypeFactureGroupee;
  type_libelle: string;
  magasin: string;
  magasin_nom: string;
  client: string | null;
  client_nom: string;
  client_adresse: string;
  client_matricule_fiscal: string;
  du: string;
  au: string;
  cree_le: string;
  emise_par: string;
  devise: string;
  total_ht: string;
  total_tva: string;
  total_ttc: string;
  timbre_fiscal: string;
  net_a_payer: string;
  mode_paiement_timbre: string;
  nombre_ventes: number;
};

export type FactureGroupeeDetail = FactureGroupee & {
  ventes: { numero: string; livree_le: string | null; total_ttc: string }[];
  detail_tva: DetailTva[];
  lignes: {
    vente: string;
    libelle: string;
    quantite: number;
    prix_unitaire_ttc: string;
    remise_pct: string;
    taux_tva: string;
    total_ttc: string;
  }[];
};

export type ClotureMois = {
  id: string;
  magasin: string;
  magasin_nom: string;
  annee: number;
  mois: number;
  cree_le: string;
  cloture_par: string;
  facture: string | null;
  facture_numero: string | null;
  total_ttc: string;
};

export type PreparationCloture = {
  annee: number;
  mois: number;
  cloture: ClotureMois | null;
  ventes: VenteAFacturer[];
  detail_tva: DetailTva[];
  total_ht: string;
  total_tva: string;
  total_ttc: string;
};

export type SaisieFactureGroupee = {
  magasin: string;
  ventes: string[];
  client?: string | null;
  client_nom?: string;
  client_adresse?: string;
  client_matricule_fiscal?: string;
  mode_paiement_timbre?: string;
};

const URL = "/api/v1/factures-groupees/";

export const ventesAFacturer = (filtres: {
  magasin: string;
  client?: string;
  comptoir?: boolean;
  du?: string;
  au?: string;
}) => {
  const params = new URLSearchParams({ magasin: filtres.magasin });
  if (filtres.client) params.set("client", filtres.client);
  if (filtres.comptoir !== undefined) params.set("comptoir", String(filtres.comptoir));
  if (filtres.du) params.set("du", filtres.du);
  if (filtres.au) params.set("au", filtres.au);
  return appeler<VenteAFacturer[]>(`${URL}a-facturer/?${params}`);
};

export const facturerEnsemble = (saisie: SaisieFactureGroupee) =>
  appeler<FactureGroupeeDetail>(URL, { methode: "POST", corps: saisie });

export const listerFacturesGroupees = (filtres: { type?: TypeFactureGroupee; numero?: string } = {}) => {
  const params = new URLSearchParams();
  if (filtres.type) params.set("type", filtres.type);
  if (filtres.numero) params.set("numero", filtres.numero);
  return appeler<{ results: FactureGroupee[] }>(`${URL}?${params}`).then((page) => page.results);
};

export const lireFactureGroupee = (id: string) => appeler<FactureGroupeeDetail>(`${URL}${id}/`);

export const listerClotures = () => appeler<ClotureMois[]>("/api/v1/clotures-mois/");

export const preparerCloture = (magasin: string, annee: number, mois: number) =>
  appeler<PreparationCloture>(
    `/api/v1/clotures-mois/preparation/?${new URLSearchParams({ magasin, annee: String(annee), mois: String(mois) })}`,
  );

export const cloturerMois = (magasin: string, annee: number, mois: number) =>
  appeler<ClotureMois>("/api/v1/clotures-mois/", {
    methode: "POST",
    corps: { magasin, annee, mois },
  });
