import { envoyerFichier } from "./client";

export type RapportImport = {
  apercu: boolean;
  lignes: number;
  crees: number;
  modifies: number;
  erreurs: { ligne: number; message: string }[];
  /** Articles déjà au catalogue ou en stock, clients déjà importés ou en double : à regarder. */
  alertes: { ligne: number; message: string }[];
  /** Rendu par une vérification sans erreur ; l'import de ce même fichier l'exige. */
  jeton: string;
};

/** Imports disponibles : chacun a son modèle Excel et CSV à télécharger. */
export type TypeImport = "catalogue" | "verres" | "stock" | "clients" | "fournisseurs" | "receptions" | "utilisateurs";

/** Fichier modèle : Excel (à remplir, exemple, aide) ou CSV (ligne d'en-tête). */
export const urlModele = (type: TypeImport, extension: "xlsx" | "csv") =>
  `/api/v1/imports/modeles/${type}.${extension}`;

/** Sans jeton : vérification. Avec le jeton de la vérification : import. */
export function importer(type: TypeImport, fichier: File, champs: Record<string, string> = {}, jeton?: string) {
  const formulaire = new FormData();
  formulaire.append("fichier", fichier);
  Object.entries(champs).forEach(([cle, valeur]) => formulaire.append(cle, valeur));
  formulaire.append("apercu", String(!jeton));
  if (jeton) formulaire.append("jeton", jeton);
  return envoyerFichier<RapportImport>(`/api/v1/imports/${type}/`, formulaire);
}
