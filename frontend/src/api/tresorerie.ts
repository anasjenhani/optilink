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
