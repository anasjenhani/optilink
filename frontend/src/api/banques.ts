import { appeler } from "./client";

export type Banque = { id: number; code: string; nom: string; sigle: string; pays: string };

/** Banques proposées sur les fiches, tenues dans /admin/ (Réseau › Banques). */
export const listerBanques = () =>
  appeler<Banque[]>("/api/v1/banques/").then((banques) =>
    [...banques].sort((a, b) => a.nom.localeCompare(b.nom, "fr", { sensitivity: "base" })),
  );
