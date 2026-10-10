import { appeler } from "./client";

export const CATEGORIES = [
  { valeur: "optique", libelle: "Lunette Optique" },
  { valeur: "solaire", libelle: "Lunette Solaire" },
  { valeur: "applique", libelle: "Lunette Applique" },
] as const;

export const MATIERES = [
  { valeur: "acetate", libelle: "Acétate" },
  { valeur: "titane", libelle: "Titane" },
  { valeur: "acier", libelle: "Acier" },
  { valeur: "tr90", libelle: "TR90" },
  { valeur: "corne", libelle: "Corne" },
  { valeur: "bois", libelle: "Bois" },
  { valeur: "metal", libelle: "Métal" },
] as const;

export const TYPES_MONTURE = [
  { valeur: "", libelle: "Aucun" },
  { valeur: "cerclee", libelle: "Cerclée" },
  { valeur: "semi_cerclee", libelle: "Semi-cerclée (nylor)" },
  { valeur: "percee", libelle: "Percée" },
] as const;

export const TRANCHES_AGE = [
  { valeur: "", libelle: "—" },
  { valeur: "adulte", libelle: "Adulte" },
  { valeur: "junior", libelle: "Junior" },
  { valeur: "enfant", libelle: "Enfant" },
  { valeur: "bebe", libelle: "Bébé" },
] as const;

export const GENRES = [
  { valeur: "", libelle: "—" },
  { valeur: "homme", libelle: "Homme" },
  { valeur: "femme", libelle: "Femme" },
  { valeur: "mixte", libelle: "Mixte" },
  { valeur: "enfant", libelle: "Enfant" },
] as const;

export type FicheMonture = {
  categorie: string;
  marque: string;
  modele: string;
  couleur: string;
  couleur_verres: string;
  matiere: string;
  type: string;
  forme: string;
  genre: string;
  tranche_age: string;
  calibre: number | null;
  pont: number | null;
  branche: number | null;
};

export const GEOMETRIES = [
  { valeur: "unifocal", libelle: "Unifocal" },
  { valeur: "progressif", libelle: "Progressif" },
  { valeur: "degressif", libelle: "Dégressif" },
  { valeur: "bifocal", libelle: "Bifocal" },
] as const;

export const MATIERES_VERRE = [
  { valeur: "", libelle: "—" },
  { valeur: "organique", libelle: "Organique" },
  { valeur: "polycarbonate", libelle: "Polycarbonate" },
  { valeur: "mineral", libelle: "Minéral" },
] as const;

export const RENOUVELLEMENTS = [
  { valeur: "journaliere", libelle: "Journalière" },
  { valeur: "bimensuelle", libelle: "Bimensuelle" },
  { valeur: "mensuelle", libelle: "Mensuelle" },
  { valeur: "trimestrielle", libelle: "Trimestrielle" },
  { valeur: "annuelle", libelle: "Annuelle" },
] as const;

export const FABRICATIONS_VERRE = [
  { valeur: "prescription", libelle: "Prescription (RX, importation)" },
  { valeur: "stock", libelle: "Stock fournisseur" },
] as const;

export const CATEGORIES_LENTILLE = [
  { valeur: "optique", libelle: "Lentille optique" },
  { valeur: "solaire", libelle: "Lentille solaire" },
] as const;

export const TYPES_LENTILLE = [
  { valeur: "spherique", libelle: "Sphérique" },
  { valeur: "torique", libelle: "Torique" },
  { valeur: "multifocale", libelle: "Multifocale" },
] as const;

/** Décimaux en texte (« 1.600 », « -3.25 »), comme l'API les rend. */
export type FicheVerre = {
  marque: string;
  gamme: string;
  geometrie: string;
  indice: string | null;
  matiere: string;
  traitements: string;
  photochromique: boolean;
  teinte: string;
  diametre: number | null;
  diametre_commercial: string;
  fabrication: "stock" | "prescription";
};

export type FicheLentille = {
  categorie: string;
  marque: string;
  modele: string;
  couleur: string;
  renouvellement: string;
  type: string;
  rayon: string | null;
  diametre: string | null;
  puissance: string | null;
  cylindre: string | null;
  axe: number | null;
  addition: string | null;
  lentilles_par_boite: number | null;
};

export type Prix = {
  prix_achat_ht: string | null;
  taux_remise_achat: string;
  taux_tva: string;
  prix_vente_ttc: string;
};

export type FicheArticle = {
  id: string;
  reference: string;
  libelle: string;
  famille: "monture" | "verre" | "lentille" | "divers" | "supplement";
  code_barres: string;
  fournisseur: string;
  fournisseur_nom: string;
  fournisseur_code: number | null;
  reference_fournisseur: string;
  est_actif: boolean;
  stockable: boolean;
  suivi_numero_serie: boolean;
  promotion: boolean;
  etui_special: boolean;
  fodec: boolean;
  observation: string;
  monture: FicheMonture | null;
  verre: FicheVerre | null;
  lentille: FicheLentille | null;
  prix: Prix | null;
  dernier_achat: {
    prix_achat_ht: string;
    taux_remise: string;
    net_ht: string;
    date_bl: string;
    numero_bl: string;
  } | null;
  /** Une ligne par dépôt de chaque magasin. */
  stocks: { magasin: string; depot?: string; stock: number }[];
  cree_par: string | null;
  cree_le: string;
};

export type SaisieFiche = Partial<
  Omit<FicheArticle, "id" | "prix" | "dernier_achat" | "stocks" | "cree_par" | "cree_le" | "fournisseur_nom">
> & { nouveau_prix?: Prix };

export type Mouvement = {
  horodatage: string;
  magasin: string;
  depot?: string;
  type: string;
  quantite: number;
  reference: string;
  utilisateur: string;
};

export type Suggestions = Record<"marque" | "modele" | "forme" | "couleur" | "couleur_verres", string[]>;

const parametre = (magasin: string) => `?${new URLSearchParams({ magasin })}`;

export const lireFiche = (id: string, magasin: string) =>
  appeler<FicheArticle>(`/api/v1/fiches-articles/${id}/${parametre(magasin)}`);

export const enregistrerFiche = (id: string | null, magasin: string, saisie: SaisieFiche) =>
  id
    ? appeler<FicheArticle>(`/api/v1/fiches-articles/${id}/${parametre(magasin)}`, { methode: "PATCH", corps: saisie })
    : appeler<FicheArticle>(`/api/v1/fiches-articles/${parametre(magasin)}`, { methode: "POST", corps: saisie });

export const lireMouvements = (id: string) => appeler<Mouvement[]>(`/api/v1/fiches-articles/${id}/mouvements/`);

export const lireSuggestions = () => appeler<Suggestions>("/api/v1/fiches-articles/suggestions/");

/** Calculs de l'onglet « Détail prix », comme l'ancien logiciel. */
export function calculerPrix(p: { achatHT: number; remise: number; tva: number; venteTTC: number; fodec: boolean }) {
  const netHT = p.achatHT * (1 - p.remise / 100);
  const achatNetTTC = netHT * (p.fodec ? 1.01 : 1) * (1 + p.tva / 100);
  const venteHT = p.venteTTC / (1 + p.tva / 100);
  const marge = p.achatHT > 0 ? ((venteHT - p.achatHT) / p.achatHT) * 100 : null;
  return { netHT, achatNetTTC, venteHT, marge };
}

/** Prix de vente TTC pour une marge (en % du prix d'achat HT) ou un prix HT donnés. */
export const venteTTCDepuisMarge = (achatHT: number, marge: number, tva: number) =>
  achatHT * (1 + marge / 100) * (1 + tva / 100);
export const venteTTCDepuisHT = (venteHT: number, tva: number) => venteHT * (1 + tva / 100);
