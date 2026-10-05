import { appeler } from "./client";

export type Portee = "magasin" | "societe" | "reseau";

export type Affectation = {
  id?: number;
  profil: number;
  profil_nom?: string;
  portee: Portee;
  magasin: string | null;
  societe: string | null;
  perimetre?: string;
  debut?: string;
  fin?: string | null;
};

export type Utilisateur = {
  id: number;
  identifiant: string;
  prenom: string;
  nom: string;
  email: string;
  actif: boolean;
  derniere_connexion: string | null;
  mfa_active: boolean;
  administrateur_technique: boolean;
  affectations: Affectation[];
};

export type SaisieUtilisateur = {
  identifiant?: string;
  prenom: string;
  nom: string;
  email: string;
  actif?: boolean;
  mot_de_passe?: string;
  affectations: Affectation[];
};

export type Profil = { id: number; nom: string; privileges: string[]; utilisateurs: number };
export type ModulePrivileges = { module: string; privileges: { code: string; libelle: string }[] };
export type Societe = { id: string; code: string; raison_sociale: string };

type Page<T> = { results: T[] };

export const listerUtilisateurs = () => appeler<Utilisateur[]>("/api/v1/securite/utilisateurs/");

export const creerUtilisateur = (saisie: SaisieUtilisateur) =>
  appeler<Utilisateur>("/api/v1/securite/utilisateurs/", { methode: "POST", corps: saisie });

export const modifierUtilisateur = (id: number, saisie: Partial<SaisieUtilisateur>) =>
  appeler<Utilisateur>(`/api/v1/securite/utilisateurs/${id}/`, { methode: "PATCH", corps: saisie });

export const reinitialiserMfa = (id: number) =>
  appeler<void>(`/api/v1/securite/utilisateurs/${id}/reinitialiser-mfa/`, { methode: "POST" });

export const listerProfils = () => appeler<Profil[]>("/api/v1/securite/profils/");

export const creerProfil = (nom: string) =>
  appeler<Profil>("/api/v1/securite/profils/", { methode: "POST", corps: { nom, privileges: [] } });

export const modifierProfil = (id: number, privileges: string[]) =>
  appeler<Profil>(`/api/v1/securite/profils/${id}/`, { methode: "PATCH", corps: { privileges } });

export const supprimerProfil = (id: number) =>
  appeler<void>(`/api/v1/securite/profils/${id}/`, { methode: "DELETE" });

export const listerPrivileges = () => appeler<ModulePrivileges[]>("/api/v1/securite/privileges/");

export const listerSocietes = () => appeler<Page<Societe>>("/api/v1/societes/").then((p) => p.results);
