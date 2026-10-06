import { appeler } from "./client";

export type Ville = { id: number; nom: string; pays: string };

/** Villes proposées sur les fiches, tenues dans /admin/ (Réseau › Villes). */
export const listerVilles = () =>
  appeler<Ville[]>("/api/v1/villes/").then((villes) =>
    [...villes].sort((a, b) => a.nom.localeCompare(b.nom, "fr", { sensitivity: "base" })),
  );
