import type { Vente } from "./caisse";
import { appeler } from "./client";

export type FiltresVisites = {
  magasin?: string;
  du?: string;
  au?: string;
  recherche?: string;
  client?: string;
  statut?: string;
  facturee?: "true" | "false" | "";
  page?: number;
};

export type LigneVisite = Vente & { cree_le: string; vendeur: string; magasin: string };
export type PageVisites = { count: number; results: LigneVisite[] };

const parametres = (filtres: Record<string, string | number | undefined>) =>
  new URLSearchParams(
    Object.entries(filtres)
      .filter(([, v]) => v !== undefined && v !== "")
      .map(([k, v]) => [k, String(v)]),
  ).toString();

export const listerVisites = (filtres: FiltresVisites) =>
  appeler<PageVisites>(`/api/v1/ventes/?${parametres(filtres)}`);

export type VerreCommande = {
  id: number;
  ligne: number;
  libelle: string;
  commande_fournisseur: string;
  fournisseur: string;
  statut: "envoyee" | "recue" | "annulee";
  recu_le: string | null;
  casse: string | null;
};

export type FicheVisite = Vente & {
  cree_le: string;
  vendeur: string;
  magasin: string;
  magasin_nom: string;
  vendeur_nom: string;
  pris_en_charge: string;
  client_fiche: {
    id: string;
    numero: number;
    nom: string;
    telephone: string;
    organisme: string | null;
    numero_affilie: string;
  } | null;
  etat: string | null;
  etat_libelle: string | null;
  reglements: {
    mode: string;
    mode_libelle: string;
    montant: string;
    recu_le: string;
    recu_par: string;
    reference?: string;
    statut?: "encaisse" | "impaye" | "remplace";
    statut_libelle?: string;
  }[];
  prises_en_charge: { organisme: string; montant: string; numero_dossier: string; statut_libelle: string }[];
  etapes: { etape: string; etape_libelle: string; observation: string; le: string; par: string }[];
  verres_commandes: VerreCommande[];
  avoirs: {
    numero: string;
    cree_le: string;
    annulation: boolean;
    motif: string;
    total_ttc: string;
    montant_rembourse: string;
  }[];
};

export const ficheVisite = (id: string) => appeler<FicheVisite>(`/api/v1/ventes/${id}/fiche/`);

export type Recu = {
  id: number;
  recu_le: string;
  mode: string;
  mode_libelle: string;
  montant: string;
  recu_par: string;
  vente: string;
  vente_numero: string;
  devise: string;
  total_ttc: string;
  deja_regle: string;
  reste_apres: string;
  client: { numero: number; nom: string; telephone: string } | null;
  magasin: { nom: string; adresse: string; telephone: string; societe: string; matricule_fiscal: string };
};

export const listerRecus = (filtres: { magasin?: string; du?: string; au?: string; mode?: string }) =>
  appeler<Recu[]>(`/api/v1/ventes/recus/?${parametres(filtres)}`);

export type ResteVendeur = {
  vendeur: string;
  vendeur_nom: string;
  nombre: number;
  total_ttc: string;
  reste: string;
  commandes: {
    id: string;
    numero: string;
    cree_le: string;
    client: string | null;
    telephone: string;
    total_ttc: string;
    reste: string;
  }[];
};

export const resteParVendeur = (magasin: string) =>
  appeler<ResteVendeur[]>(`/api/v1/ventes/reste-par-vendeur/?${parametres({ magasin })}`);

export type CauseCasse = "atelier" | "fournisseur" | "client";

export const CAUSES_CASSE: { valeur: CauseCasse; libelle: string }[] = [
  { valeur: "atelier", libelle: "Casse à l'atelier (montage)" },
  { valeur: "fournisseur", libelle: "Défaut du fournisseur" },
  { valeur: "client", libelle: "Casse par le client" },
];

export type Casse = {
  id: string;
  vente: string;
  vente_numero: string;
  magasin: string;
  client: string | null;
  verre: string;
  commande_fournisseur: string;
  fournisseur: string;
  cause: CauseCasse;
  cause_libelle: string;
  observation: string;
  declaree_par: string;
  cree_le: string;
};

export const listerCasses = (cause = "") =>
  appeler<{ results: Casse[] }>(`/api/v1/casses-verres/?${parametres({ cause })}`).then((p) => p.results);

export const declarerCasse = (saisie: { ligne_commande: number; cause: CauseCasse; observation: string }) =>
  appeler<Casse>("/api/v1/casses-verres/", { methode: "POST", corps: saisie });

export const corrigerCasse = (id: string, correction: { cause: CauseCasse; observation: string }) =>
  appeler<Casse>(`/api/v1/casses-verres/${id}/`, { methode: "PATCH", corps: correction });

/** Casse déclarée par erreur : le verre reçu compte de nouveau (tant qu'il n'est pas recommandé). */
export const annulerCasse = (id: string) => appeler<void>(`/api/v1/casses-verres/${id}/`, { methode: "DELETE" });
