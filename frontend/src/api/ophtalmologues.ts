import { appeler } from "./client";

export type Ophtalmologue = { id: number; nom: string; telephone: string; ville: string; est_actif: boolean };

export const chercherOphtalmologues = (recherche: string) =>
  appeler<Ophtalmologue[]>(`/api/v1/ophtalmologues/?${new URLSearchParams({ recherche })}`);

/** Ajoute un médecin à la liste ; refusé s'il y est déjà (même nom sans « Dr », accents ni casse). */
export const ajouterOphtalmologue = (nom: string) =>
  appeler<Ophtalmologue>("/api/v1/ophtalmologues/", { methode: "POST", corps: { nom } });
