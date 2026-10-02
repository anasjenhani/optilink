import { appeler } from "./client";

export type Fournisseur = { id: string; nom: string; pays: string; telephone: string; email: string };

export type VerreACommander = {
  ligne: number;
  commande_client: string;
  client: { id: string; nom: string } | null;
  livraison_prevue_le: string | null;
  article: string;
  libelle: string;
  quantite: number;
};

export type CommandeFournisseur = {
  id: string;
  numero: string;
  fournisseur: string;
  reference_fournisseur: string;
  statut: "envoyee" | "recue" | "annulee";
  cree_le: string;
  lignes: { commande_client: string; libelle: string; quantite: number; details: string }[];
};

export const listerFournisseurs = () =>
  appeler<{ results: Fournisseur[] }>("/api/v1/fournisseurs/").then((page) => page.results);

export const listerVerresACommander = (magasin: string) =>
  appeler<VerreACommander[]>(
    `/api/v1/commandes-fournisseurs/a-commander/?${new URLSearchParams({ magasin })}`,
  );

export const listerCommandesEnvoyees = (magasin: string) =>
  appeler<{ results: CommandeFournisseur[] }>(
    `/api/v1/commandes-fournisseurs/?${new URLSearchParams({ statut: "envoyee", magasin__public_id: magasin })}`,
  ).then((page) => page.results);

export const passerCommande = (saisie: {
  magasin: string;
  fournisseur: string;
  reference_fournisseur?: string;
  lignes: { ligne: number; details?: string }[];
}) => appeler<CommandeFournisseur>("/api/v1/commandes-fournisseurs/", { methode: "POST", corps: saisie });

export const receptionner = (id: string) =>
  appeler<CommandeFournisseur>(`/api/v1/commandes-fournisseurs/${id}/receptionner/`, { methode: "POST" });

export const annulerCommandeFournisseur = (id: string) =>
  appeler<CommandeFournisseur>(`/api/v1/commandes-fournisseurs/${id}/annuler/`, { methode: "POST" });
