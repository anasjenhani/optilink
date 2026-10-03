import { appeler } from "./client";

export type Solde = { acquis: string; pris: string; en_attente: string; disponible: string };

export type Employe = {
  id: string;
  matricule: string;
  magasin: string;
  magasin_nom: string;
  utilisateur: string | null;
  nom: string;
  prenom: string;
  cin: string;
  telephone: string;
  poste: string;
  date_embauche: string;
  date_sortie: string | null;
  conges_par_mois: string;
  solde_conges_initial: string;
  solde: Solde;
};

export type TypeConge = "annuel" | "maladie" | "exceptionnel" | "maternite" | "sans_solde";
export type StatutConge = "demandee" | "acceptee" | "refusee" | "annulee";

export type Conge = {
  id: string;
  employe: string;
  employe_nom: string;
  magasin: string;
  type: TypeConge;
  type_libelle: string;
  debut: string;
  fin: string;
  jours: string;
  motif: string;
  statut: StatutConge;
  demandee_par: string;
  decidee_par: string | null;
  decidee_le: string | null;
  commentaire_decision: string;
};

export type StatutPointage = "present" | "retard" | "absent_justifie" | "absent";

export type LignePresence = {
  employe: string;
  matricule: string;
  nom: string;
  poste: string;
  pointage: { statut: StatutPointage; arrivee: string | null; depart: string | null; commentaire: string } | null;
  conge: string | null;
};

export type MonEspace = { employe: Employe; conges: Conge[] };

export type SaisieConge = { type: TypeConge; debut: string; fin: string; motif: string };

type Page<T> = { results: T[] };

export const lireMonEspace = () => appeler<MonEspace>("/api/v1/rh/mon-espace/");

export const demanderConge = (demande: SaisieConge) =>
  appeler<MonEspace>("/api/v1/rh/mon-espace/demander/", { methode: "POST", corps: demande });

export const annulerMonConge = (id: string) =>
  appeler<MonEspace>(`/api/v1/rh/mon-espace/${id}/annuler/`, { methode: "POST" });

export const listerEmployes = () => appeler<Employe[]>("/api/v1/rh/employes/?actifs=true");

export const creerEmploye = (employe: {
  magasin: string;
  nom: string;
  prenom: string;
  cin: string;
  telephone: string;
  poste: string;
  date_embauche: string;
  solde_conges_initial: string;
  utilisateur: string | null;
}) => appeler<Employe>("/api/v1/rh/employes/", { methode: "POST", corps: employe });

export const lirePresence = (magasin: string, date: string) =>
  appeler<LignePresence[]>(`/api/v1/rh/presence/?magasin=${magasin}&date=${date}`);

export const enregistrerPresence = (
  magasin: string,
  date: string,
  lignes: { employe: string; statut: StatutPointage; arrivee: string | null; depart: string | null; commentaire: string }[],
) => appeler<LignePresence[]>("/api/v1/rh/presence/", { methode: "POST", corps: { magasin, date, lignes } });

export const listerConges = (statut?: StatutConge) =>
  appeler<Page<Conge>>(`/api/v1/rh/conges/${statut ? `?statut=${statut}` : ""}`).then((p) => p.results);

export const saisirConge = (demande: SaisieConge & { employe: string }) =>
  appeler<Conge>("/api/v1/rh/conges/", { methode: "POST", corps: demande });

export const deciderConge = (id: string, decision: "accepter" | "refuser", commentaire: string) =>
  appeler<Conge>(`/api/v1/rh/conges/${id}/${decision}/`, { methode: "POST", corps: { commentaire } });
