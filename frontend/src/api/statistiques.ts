import { appeler } from "./client";

export type RapportStatistique =
  | "montures"
  | "verres"
  | "lentilles"
  | "remises"
  | "gratuits"
  | "ophtalmologues"
  | "tva"
  | "benefice";

export type ColonneStatistique = {
  cle: string;
  libelle: string;
  type: "texte" | "nombre" | "montant" | "pourcent" | "date";
};

export type Statistique = {
  titre: string;
  devise: string;
  decimales: number;
  devises: string[];
  du: string;
  au: string;
  colonnes: ColonneStatistique[];
  lignes: Record<string, string | number>[];
  totaux: Record<string, string | number>;
};

export const lireStatistique = (
  rapport: RapportStatistique,
  filtres: { du?: string; au?: string; magasin?: string; devise?: string },
) => {
  const params = new URLSearchParams();
  for (const [cle, valeur] of Object.entries(filtres)) if (valeur) params.set(cle, valeur);
  return appeler<Statistique>(`/api/v1/statistiques/${rapport}/?${params}`);
};
