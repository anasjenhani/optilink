import type { Famille } from "./caisse";
import { appeler } from "./client";

export type LigneInventaire = {
  article: string;
  reference: string;
  code_barres: string;
  libelle: string;
  famille: string;
  stock_theorique: number;
  quantite_comptee: number;
  /** Faux : article en stock pas encore compté (compté 0 à la validation). */
  comptee: boolean;
  ecart: number;
  observation: string;
  /** Lentilles : péremption la plus proche des boîtes comptées. */
  date_peremption: string | null;
};

export type InventaireResume = {
  id: string;
  numero: string;
  magasin: string;
  magasin_id: string;
  /** Dépôt compté (dépôt de vente, central ou casse du magasin). */
  depot?: string;
  depot_id?: string;
  famille: Famille | "";
  famille_libelle: string;
  marque: string;
  nature: NatureMonture | "";
  fournisseur: string;
  /** Ce que couvre l'inventaire : « Monture · Ray-Ban · Lunette Solaire ». */
  perimetre: string;
  /** Comptage, puis vérification (contrôle et correction des écarts), puis validation finale. */
  statut: "en_cours" | "a_verifier" | "valide" | "annule";
  statut_libelle: string;
  articles_comptes: number;
  observation: string;
  cree_par: string;
  cree_le: string;
  valide_par: string;
  valide_le: string | null;
  comptage_termine_par: string;
  comptage_termine_le: string | null;
  observation_validation: string;
};

export type Inventaire = InventaireResume & { lignes: LigneInventaire[] };

export type NatureMonture = "optique" | "solaire" | "applique";

export const NATURES: { valeur: NatureMonture; libelle: string }[] = [
  { valeur: "optique", libelle: "Lunette Optique" },
  { valeur: "solaire", libelle: "Lunette Solaire" },
  { valeur: "applique", libelle: "Lunette Applique" },
];

export type Comptage = {
  code?: string;
  article?: string;
  quantite?: number;
  remplacer?: boolean;
  observation?: string;
  date_peremption?: string | null;
};

export type OuvertureInventaire = {
  magasin: string;
  /** Vide : le dépôt de vente du magasin. */
  depot?: string;
  famille: Famille | "";
  marque: string;
  nature: NatureMonture | "";
  fournisseur: string | null;
  observation: string;
};

export const ouvrirInventaire = (saisie: OuvertureInventaire) =>
  appeler<Inventaire>("/api/v1/inventaires/", { methode: "POST", corps: saisie });

/** Marques de montures et fournisseurs proposés pour limiter un inventaire. */
export const lireChoixInventaire = () =>
  appeler<{ marques: string[]; fournisseurs: { id: string; nom: string }[] }>("/api/v1/inventaires/choix/");

export const lireInventaire = (id: string) => appeler<Inventaire>(`/api/v1/inventaires/${id}/`);

export const compterArticle = (id: string, comptage: Comptage) =>
  appeler<Inventaire>(`/api/v1/inventaires/${id}/compter/`, { methode: "POST", corps: comptage });

export const retirerArticle = (id: string, article: string) =>
  appeler<Inventaire>(`/api/v1/inventaires/${id}/retirer/`, { methode: "POST", corps: { article } });

export const terminerComptage = (id: string) =>
  appeler<Inventaire>(`/api/v1/inventaires/${id}/terminer/`, { methode: "POST" });

export const reprendreComptage = (id: string) =>
  appeler<Inventaire>(`/api/v1/inventaires/${id}/reprendre/`, { methode: "POST" });

export const validerInventaire = (id: string, observation: string) =>
  appeler<Inventaire>(`/api/v1/inventaires/${id}/valider/`, { methode: "POST", corps: { observation } });

export const annulerInventaire = (id: string) =>
  appeler<Inventaire>(`/api/v1/inventaires/${id}/annuler/`, { methode: "POST" });

export const listerInventaires = (page = 1) =>
  appeler<{ count: number; results: InventaireResume[] }>(`/api/v1/inventaires/?page=${page}`);
