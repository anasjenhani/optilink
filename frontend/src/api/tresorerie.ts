import { appeler } from "./client";

export type Situation = {
  debut: string | null;
  fin: string;
  devise: string;
  fond_initial: string;
  encaisse_especes: string;
  encaisse_cheques: string;
  nombre_cheques: number;
  encaisse_cartes: string;
  rembourse_especes: string;
  rembourse_cheques: string;
  rembourse_cartes: string;
  depenses: string;
  alimentations: string;
  especes_attendues: string;
  cheques_attendus: string;
  cartes_attendues: string;
  cloture_rejetee: string | null;
};

export type Comptage = {
  especes_comptees: string;
  cheques_comptes: string;
  nombre_cheques_comptes: number;
  cartes_comptees: string;
  fond_conserve: string;
  commentaire_caissier?: string;
};

export type StatutCloture = "envoyee" | "validee" | "rejetee";

export type Cloture = Omit<Situation, "cloture_rejetee"> &
  Comptage & {
    id: string;
    numero: string;
    magasin: string;
    statut: StatutCloture;
    especes_a_remettre: string;
    ecart_especes: string;
    ecart_cheques: string;
    ecart_cartes: string;
    commentaire_caissier: string;
    cloturee_par: string;
    verifiee_par: string | null;
    verifiee_le: string | null;
    commentaire_finance: string;
    depot_especes: string | null;
    depot_cheques: string | null;
    encaissement_cartes: string | null;
  };

export type CategorieDepense = "fournitures" | "entretien" | "transport" | "restauration" | "divers";

export type Depense = {
  id: string;
  categorie: CategorieDepense;
  motif: string;
  beneficiaire: string;
  montant: string;
  payee_le: string;
  saisie_par: string;
  cloture: string | null;
};

type Page<T> = { results: T[] };

export const lireSituation = (magasin: string) =>
  appeler<Situation>(`/api/v1/tresorerie/clotures/situation/?magasin=${magasin}`);

export const cloturer = (magasin: string, comptage: Comptage) =>
  appeler<Cloture>("/api/v1/tresorerie/clotures/", { methode: "POST", corps: { magasin, ...comptage } });

export const corriger = (id: string, comptage: Comptage) =>
  appeler<Cloture>(`/api/v1/tresorerie/clotures/${id}/corriger/`, { methode: "POST", corps: comptage });

export const listerClotures = (filtres: { statut?: StatutCloture; magasin?: string } = {}) => {
  const parametres = new URLSearchParams();
  if (filtres.statut) parametres.set("statut", filtres.statut);
  if (filtres.magasin) parametres.set("magasin__public_id", filtres.magasin);
  const suite = parametres.toString();
  return appeler<Page<Cloture>>(`/api/v1/tresorerie/clotures/${suite ? `?${suite}` : ""}`).then((p) => p.results);
};

export const verifierCloture = (id: string, decision: "valider" | "rejeter", commentaire: string) =>
  appeler<Cloture>(`/api/v1/tresorerie/clotures/${id}/${decision}/`, { methode: "POST", corps: { commentaire } });

export const listerDepensesOuvertes = (magasin: string) =>
  appeler<Page<Depense>>(`/api/v1/tresorerie/depenses/?magasin__public_id=${magasin}&cloture__isnull=true`).then(
    (p) => p.results,
  );

export const saisirDepense = (depense: {
  magasin_id: string;
  categorie: CategorieDepense;
  motif: string;
  beneficiaire: string;
  montant: string;
}) => appeler<Depense>("/api/v1/tresorerie/depenses/", { methode: "POST", corps: depense });

/** Une dépense se corrige ou se supprime tant que la caisse n'est pas clôturée. */
export const corrigerDepense = (
  id: string,
  correction: { categorie: CategorieDepense; motif: string; beneficiaire: string; montant: string },
) => appeler<Depense>(`/api/v1/tresorerie/depenses/${id}/`, { methode: "PATCH", corps: correction });

export const supprimerDepense = (id: string) =>
  appeler<void>(`/api/v1/tresorerie/depenses/${id}/`, { methode: "DELETE" });

export type TypeCompte = "banque" | "coffre" | "caisse_centrale";

export type Compte = {
  id: string;
  societe: string;
  societe_nom: string;
  type: TypeCompte;
  nom: string;
  banque: string;
  rib: string;
  magasin: string | null;
  magasin_nom: string | null;
  devise: string;
  solde_initial: string;
  est_actif: boolean;
  solde_comptable: string | null;
  solde_banque: string | null;
};

export type TypeDepot = "depot_especes" | "depot_cheques" | "encaissement_cartes";
export type TypeOperation = TypeDepot | "transfert" | "alimentation_fond" | "operation_bancaire";
export type StatutOperation = "prevue" | "effectuee" | "rapprochee";

export type Operation = {
  id: string;
  numero: string;
  societe: string;
  type: TypeOperation;
  type_libelle: string;
  statut: StatutOperation;
  source: string | null;
  destination: string | null;
  magasin: string | null;
  montant: string;
  montant_credite: string | null;
  commission: string | null;
  date_prevue: string | null;
  date_operation: string | null;
  date_valeur: string | null;
  reference: string;
  libelle: string;
  cree_par: string;
  rapprochee_par: string | null;
};

export type ARemettre = {
  id: string;
  numero: string;
  magasin: string;
  societe: string;
  fin: string;
  devise: string;
  especes: string | null;
  cheques: string | null;
  nombre_cheques: number | null;
  cartes: string | null;
};

type Execution = { prevue: boolean; reference: string; date: string | null };

export const listerComptes = () => appeler<Compte[]>("/api/v1/tresorerie/comptes/");

export const creerCompte = (compte: {
  societe: string;
  type: TypeCompte;
  nom: string;
  banque: string;
  rib: string;
  magasin: string | null;
  solde_initial: string;
}) => appeler<Compte>("/api/v1/tresorerie/comptes/", { methode: "POST", corps: compte });

export type SaisieCompte = Partial<Pick<Compte, "nom" | "banque" | "rib" | "magasin" | "est_actif">>;

export const modifierCompte = (id: string, saisie: SaisieCompte) =>
  appeler<Compte>(`/api/v1/tresorerie/comptes/${id}/`, { methode: "PATCH", corps: saisie });

export const listerOperations = (statut?: StatutOperation) =>
  appeler<Page<Operation>>(`/api/v1/tresorerie/operations/${statut ? `?statut=${statut}` : ""}`).then((p) => p.results);

export const listerARemettre = () => appeler<ARemettre[]>("/api/v1/tresorerie/operations/a-remettre/");

export const deposer = (depot: Execution & { type: TypeDepot; clotures: string[]; destination: string }) =>
  appeler<Operation>("/api/v1/tresorerie/operations/deposer/", { methode: "POST", corps: depot });

export const creerOperation = (
  operation: Execution & {
    type: "transfert" | "alimentation_fond" | "operation_bancaire";
    societe: string;
    montant: string;
    source: string | null;
    destination: string | null;
    magasin: string | null;
    libelle: string;
  },
) => appeler<Operation>("/api/v1/tresorerie/operations/", { methode: "POST", corps: operation });

export const effectuerOperation = (id: string, reference: string) =>
  appeler<Operation>(`/api/v1/tresorerie/operations/${id}/effectuer/`, { methode: "POST", corps: { reference } });

export const annulerOperation = (id: string) =>
  appeler<void>(`/api/v1/tresorerie/operations/${id}/annuler/`, { methode: "POST" });

export const rapprocherOperation = (id: string, date_valeur: string, montant_credite: string | null) =>
  appeler<Operation>(`/api/v1/tresorerie/operations/${id}/rapprocher/`, {
    methode: "POST",
    corps: { date_valeur, montant_credite },
  });
