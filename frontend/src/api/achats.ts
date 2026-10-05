import { appeler } from "./client";

export type Fournisseur = {
  id: string;
  /** Attribué à la création : 1, 2, 3… */
  code: number;
  /** Raison sociale. */
  nom: string;
  notre_code: string;
  responsable: string;
  fournisseur_verres: boolean;
  pays: string;
  matricule_fiscal: string;
  registre_commerce: string;
  code_douane: string;
  forme_juridique: "" | "SARL" | "SUARL" | "SA" | "SNC" | "PP";
  capital_social: string | null;
  timbre_fiscal: boolean;
  assujetti: boolean;
  fodec: boolean;
  regime_tva: "assujetti" | "export" | "exoneration";
  numero_exoneration: string;
  exoneration_du: string | null;
  exoneration_au: string | null;
  adresse: string;
  code_postal: string;
  ville: string;
  telephone: string;
  telephone_2: string;
  fax: string;
  email: string;
  site_web: string;
  banque: string;
  rib: string;
  observation: string;
  est_actif: boolean;
};

export type SaisieFournisseur = Omit<Fournisseur, "id" | "code" | "pays"> & { pays?: string };

export const FORMES_JURIDIQUES = [
  { valeur: "SARL", libelle: "SARL" },
  { valeur: "SUARL", libelle: "SUARL" },
  { valeur: "SA", libelle: "SA" },
  { valeur: "SNC", libelle: "SNC" },
  { valeur: "PP", libelle: "Personne physique" },
] as const;

export type FiltresFournisseurs = Partial<Record<"code" | "nom" | "adresse" | "ville" | "telephone", string>>;

export const chercherFournisseurs = (filtres: FiltresFournisseurs, page = 1) => {
  const parametres = new URLSearchParams({ page: String(page) });
  Object.entries(filtres).forEach(([cle, valeur]) => {
    if (valeur?.trim()) parametres.set(cle, valeur.trim());
  });
  return appeler<{ count: number; results: Fournisseur[] }>(`/api/v1/fournisseurs/?${parametres}`);
};

export const creerFournisseur = (saisie: Partial<SaisieFournisseur>) =>
  appeler<Fournisseur>("/api/v1/fournisseurs/", { methode: "POST", corps: saisie });

export const modifierFournisseur = (id: string, saisie: Partial<SaisieFournisseur>) =>
  appeler<Fournisseur>(`/api/v1/fournisseurs/${id}/`, { methode: "PATCH", corps: saisie });

export type VerreACommander = {
  ligne: number;
  commande_client: string;
  client: { id: string; nom: string } | null;
  livraison_prevue_le: string | null;
  peniche: number | null;
  article: string;
  libelle: string;
  quantite: number;
  /** Fournisseur habituel de l'article, proposé d'office. */
  fournisseur: string | null;
  reference_fournisseur: string;
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
  appeler<VerreACommander[]>(`/api/v1/commandes-fournisseurs/a-commander/?${new URLSearchParams({ magasin })}`);

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

/* Bons de réception achat */

export type ArticleResume = { id: string; reference: string; libelle: string; famille: string; code_barres: string };

export type LigneARecevoir = {
  ligne_commande: number;
  commande: string;
  commande_client: string;
  client: string | null;
  oeil: "" | "D" | "G";
  article: ArticleResume;
  designation: string;
  quantite: number;
  dernier_prix_achat: string | null;
  taux_tva: string;
};

export type SaisieLigneReception = {
  article: string;
  ligne_commande?: number | null;
  oeil?: "" | "D" | "G";
  quantite: number;
  prix_achat_ht: string;
  taux_remise: string;
  taux_tva: string;
  non_conforme: boolean;
  motif?: string;
  numero_serie?: string;
  numero_lot?: string;
  date_peremption?: string | null;
};

export type SaisieBonReception = {
  magasin: string;
  fournisseur: string;
  numero_bl: string;
  date_bl: string;
  date_saisie?: string;
  taux_remise_ex: string;
  observation?: string;
  lignes: SaisieLigneReception[];
};

export type LigneReception = {
  article: ArticleResume;
  commande: string | null;
  oeil: "" | "D" | "G";
  designation: string;
  quantite: number;
  prix_achat_ht: string;
  taux_remise: string;
  taux_tva: string;
  net_ht: string;
  montant_ttc: string;
  non_conforme: boolean;
  motif: string;
  numero_serie: string;
  numero_lot: string;
  date_peremption: string | null;
};

export type BonReceptionResume = {
  id: string;
  numero: string;
  magasin: string;
  date_saisie: string;
  fournisseur: string;
  fournisseur_code: number;
  numero_bl: string;
  date_bl: string;
  etat: "non_facture" | "facture";
  etat_libelle: string;
  numero_facture: string;
  observation: string;
  total_ht: string;
  total_net_ht: string;
  total_ttc: string;
  type_bl: string;
  total_articles: number | null;
  cree_par: string;
};

export type BonReception = BonReceptionResume & {
  taux_remise_ex: string;
  total_remise: string;
  remise_ex: string;
  total_fodec: string;
  total_tva: string;
  detail_tva: { taux: string; base_ht: string; montant_tva: string }[];
  lignes: LigneReception[];
};

export type FiltresReceptions = Partial<
  Record<"numero" | "fournisseur" | "numero_bl" | "etat" | "numero_facture" | "observation" | "du" | "au", string>
>;

export type TotauxReceptions = { total_ht: string; total_net_ht: string; total_ttc: string; total_articles: number };

export const listerReceptions = (filtres: FiltresReceptions, page = 1) => {
  const parametres = new URLSearchParams({ page: String(page) });
  Object.entries(filtres).forEach(([cle, valeur]) => {
    if (valeur?.trim()) parametres.set(cle, valeur.trim());
  });
  return appeler<{ count: number; results: BonReceptionResume[]; totaux: TotauxReceptions }>(
    `/api/v1/bons-reception/?${parametres}`,
  );
};

export const lireReception = (id: string) => appeler<BonReception>(`/api/v1/bons-reception/${id}/`);

export const listerARecevoir = (magasin: string, fournisseur: string) =>
  appeler<LigneARecevoir[]>(`/api/v1/bons-reception/a-recevoir/?${new URLSearchParams({ magasin, fournisseur })}`);

export const derniersPrix = (magasin: string, articles: string[]) =>
  appeler<Record<string, { dernier_prix_achat: string | null; taux_tva: string }>>(
    `/api/v1/bons-reception/derniers-prix/?${new URLSearchParams({ magasin, articles: articles.join(",") })}`,
  );

export const enregistrerReception = (saisie: SaisieBonReception) =>
  appeler<BonReception>("/api/v1/bons-reception/", { methode: "POST", corps: saisie });
