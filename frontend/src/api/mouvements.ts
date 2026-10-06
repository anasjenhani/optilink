import { appeler } from "./client";

export type TypeMouvement =
  | "reception"
  | "vente"
  | "retour"
  | "ajustement"
  | "retour_fournisseur"
  | "transfert_sortie"
  | "transfert_entree";

/** Libellés des types, dans l'ordre du modèle MouvementStock. */
export const TYPES_MOUVEMENT: Record<TypeMouvement, string> = {
  reception: "Réception",
  vente: "Vente",
  retour: "Retour client",
  ajustement: "Ajustement d'inventaire",
  retour_fournisseur: "Retour au fournisseur",
  transfert_sortie: "Transfert envoyé",
  transfert_entree: "Transfert reçu",
};

/** Entrée (positive) ou sortie (négative) d'un article ; jamais modifiée ni supprimée. */
export type MouvementStock = {
  id: number;
  magasin: string;
  magasin_nom: string;
  article: string;
  article_reference: string;
  article_libelle: string;
  quantite: number;
  type: TypeMouvement;
  type_libelle: string;
  reference: string;
  utilisateur: string;
  horodatage: string;
};

export type FiltresMouvements = {
  magasin?: string;
  /** Référence de l'article (contient) ou code-barres exact. */
  article?: string;
  type?: string;
  du?: string;
  au?: string;
};

export const listerMouvements = (filtres: FiltresMouvements, page = 1) => {
  const parametres = new URLSearchParams({ page: String(page) });
  Object.entries(filtres).forEach(([cle, valeur]) => {
    if (valeur?.trim()) parametres.set(cle, valeur.trim());
  });
  return appeler<{ count: number; results: MouvementStock[] }>(`/api/v1/mouvements-stock/?${parametres}`);
};
