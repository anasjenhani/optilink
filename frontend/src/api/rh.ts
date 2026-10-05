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
  salaire_base: string | null;
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

export type StatutAcompte = "demande" | "accorde" | "verse" | "refuse" | "annule";
export type ModeVersement = "especes" | "virement" | "cheque";

export type Acompte = {
  id: string;
  employe: string;
  employe_nom: string;
  magasin: string;
  montant: string;
  mois: string;
  motif: string;
  statut: StatutAcompte;
  demande_par: string;
  decide_par: string | null;
  decide_le: string | null;
  commentaire_decision: string;
  mode_versement: ModeVersement | "";
  verse_le: string | null;
  reference_versement: string;
};

export type TypePrime = "rendement" | "objectif" | "assiduite" | "fete" | "exceptionnelle" | "autre";
export type StatutPrime = "proposee" | "validee" | "refusee" | "annulee";

export type Prime = {
  id: string;
  employe: string;
  employe_nom: string;
  magasin: string;
  type: TypePrime;
  type_libelle: string;
  montant: string;
  mois: string;
  motif: string;
  statut: StatutPrime;
  proposee_par: string;
  validee_par: string | null;
  validee_le: string | null;
  commentaire_decision: string;
};

export type LigneRecap = {
  employe: string;
  matricule: string;
  nom: string;
  magasin: string;
  salaire_base: string | null;
  acomptes: string;
  primes: string;
};

export type MonEspace = { employe: Employe; conges: Conge[]; acomptes: Acompte[]; primes: Prime[] };

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
  salaire_base: string | null;
  utilisateur: string | null;
}) => appeler<Employe>("/api/v1/rh/employes/", { methode: "POST", corps: employe });

export const lirePresence = (magasin: string, date: string) =>
  appeler<LignePresence[]>(`/api/v1/rh/presence/?magasin=${magasin}&date=${date}`);

export const enregistrerPresence = (
  magasin: string,
  date: string,
  lignes: {
    employe: string;
    statut: StatutPointage;
    arrivee: string | null;
    depart: string | null;
    commentaire: string;
  }[],
) => appeler<LignePresence[]>("/api/v1/rh/presence/", { methode: "POST", corps: { magasin, date, lignes } });

export const listerConges = (statut?: StatutConge) =>
  appeler<Page<Conge>>(`/api/v1/rh/conges/${statut ? `?statut=${statut}` : ""}`).then((p) => p.results);

export const saisirConge = (demande: SaisieConge & { employe: string }) =>
  appeler<Conge>("/api/v1/rh/conges/", { methode: "POST", corps: demande });

export const deciderConge = (id: string, decision: "accepter" | "refuser", commentaire: string) =>
  appeler<Conge>(`/api/v1/rh/conges/${id}/${decision}/`, { methode: "POST", corps: { commentaire } });

export const demanderMonAcompte = (acompte: { montant: string; motif: string }) =>
  appeler<MonEspace>("/api/v1/rh/mon-espace/demander-acompte/", { methode: "POST", corps: acompte });

export const listerAcomptes = (statut?: StatutAcompte) =>
  appeler<Page<Acompte>>(`/api/v1/rh/acomptes/${statut ? `?statut=${statut}` : ""}`).then((p) => p.results);

export const demanderAcompte = (acompte: { employe: string; montant: string; motif: string }) =>
  appeler<Acompte>("/api/v1/rh/acomptes/", { methode: "POST", corps: acompte });

export const deciderAcompte = (id: string, decision: "accorder" | "refuser", commentaire: string) =>
  appeler<Acompte>(`/api/v1/rh/acomptes/${id}/${decision}/`, { methode: "POST", corps: { commentaire } });

export const verserAcompte = (id: string, mode: ModeVersement, reference: string) =>
  appeler<Acompte>(`/api/v1/rh/acomptes/${id}/verser/`, { methode: "POST", corps: { mode, reference } });

export const listerPrimes = (statut?: StatutPrime) =>
  appeler<Page<Prime>>(`/api/v1/rh/primes/${statut ? `?statut=${statut}` : ""}`).then((p) => p.results);

export const proposerPrime = (prime: {
  employe: string;
  type: TypePrime;
  montant: string;
  mois: string;
  motif: string;
}) => appeler<Prime>("/api/v1/rh/primes/", { methode: "POST", corps: prime });

export const deciderPrime = (id: string, decision: "valider" | "refuser", commentaire: string) =>
  appeler<Prime>(`/api/v1/rh/primes/${id}/${decision}/`, { methode: "POST", corps: { commentaire } });

export const lireRecap = (mois: string) => appeler<LigneRecap[]>(`/api/v1/rh/recap/?mois=${mois}`);
