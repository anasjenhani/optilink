import { appeler } from "./client";

/** Élément supprimé, restaurable jusqu'à ``expire_le`` (après, il est effacé la nuit). */
export type ElementCorbeille = {
  id: number;
  type_libelle: string;
  libelle: string;
  /** L'élément et ce qui a été supprimé avec lui (lignes, fiche liée…). */
  nombre_objets: number;
  supprime_par: string;
  supprime_le: string;
  expire_le: string;
  jours_de_grace: number;
};

export const listerCorbeille = (recherche = "") =>
  appeler<{ results: ElementCorbeille[] }>(
    `/api/v1/corbeille/?${new URLSearchParams(recherche.trim() ? { recherche: recherche.trim() } : {})}`,
  ).then((p) => p.results);

export const restaurerElement = (id: number) =>
  appeler<void>(`/api/v1/corbeille/${id}/restaurer/`, { methode: "POST" });

/** Efface tout de suite, sans attendre la fin du délai de grâce. */
export const supprimerDefinitivement = (id: number) => appeler<void>(`/api/v1/corbeille/${id}/`, { methode: "DELETE" });
