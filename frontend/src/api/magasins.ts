import { appeler } from "./client";

export type Magasin = { id: string; code: string; nom: string; region: string; ville: string };

export const listerMagasins = () =>
  appeler<{ results: Magasin[] }>("/api/v1/magasins/").then((page) => page.results);
