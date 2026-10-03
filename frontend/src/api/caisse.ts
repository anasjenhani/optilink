import { appeler } from "./client";

export type Article = {
  id: string;
  reference: string;
  libelle: string;
  famille: Famille;
  code_barres: string;
  fournisseur: string | null;
  /** Caractéristiques de la famille sur une ligne (« Ray-Ban RB5154 · écaille · 51□21-145 »). */
  description: string;
  caracteristiques: Record<string, string | number | boolean | null> | null;
  /** Commandé au fournisseur pour chaque client (verres…) : pas de stock, vente en commande. */
  sur_commande: boolean;
  prix_vente_ttc: string;
  taux_tva: string;
  devise: string;
  stock: number | null;
};

export type Famille = "monture" | "verre" | "lentille" | "divers";

export const FAMILLES: { valeur: Famille; libelle: string }[] = [
  { valeur: "monture", libelle: "Montures" },
  { valeur: "verre", libelle: "Verres" },
  { valeur: "lentille", libelle: "Lentilles" },
  { valeur: "divers", libelle: "Divers" },
];

export type ModePaiement = "carte" | "especes" | "cheque";

export type Vente = {
  id: string;
  numero: string;
  devise: string;
  total_ttc: string;
  reste_a_payer: string;
  statut: "en_commande" | "livree" | "annulee";
  /** Bac numéroté où l'équipement d'une commande attend sa livraison. */
  peniche: number | null;
  livraison_prevue_le: string | null;
  /** Verres commandés au fournisseur ; null si la commande n'en comporte pas. */
  verres?: "a_commander" | "commandes" | "recus" | null;
  facture: string | null;
  client: { id: string; nom: string; matricule_fiscal: string } | null;
  lignes: { id: number; libelle: string; quantite: number; quantite_reprise: number; total_ttc: string }[];
};

export type SaisieVente = {
  magasin: string;
  client?: string;
  lignes: { article: string; quantite: number }[];
  paiements: { mode: ModePaiement; montant: string }[];
  /** Commande : acompte maintenant (paiements, éventuellement vides), solde à la livraison. */
  commande?: boolean;
  livraison_prevue_le?: string;
  /** Commande : n° de péniche ; sans lui, la plus petite libre du magasin. */
  peniche?: number;
};

export type Reglement = { mode: ModePaiement; montant: string };

/** Ce que le vendeur vend au comptoir ; chaque type regroupe des familles d'articles. */
export type TypeVente = "optique" | "solaire" | "lentille" | "produit";

export const TYPES_VENTE: { valeur: TypeVente; libelle: string; aide: string }[] = [
  { valeur: "optique", libelle: "Lunettes optiques", aide: "Monture et verres correcteurs" },
  { valeur: "solaire", libelle: "Lunettes solaires", aide: "Montures solaires" },
  { valeur: "lentille", libelle: "Lentilles", aide: "Lentilles de contact" },
  { valeur: "produit", libelle: "Produits et accessoires", aide: "Produits lentilles, étuis, sprays…" },
];

export const chercherArticles = (
  magasin: string,
  recherche: string,
  famille: Famille | "" = "",
  typeVente: TypeVente | "" = "",
) =>
  appeler<{ results: Article[] }>(
    `/api/v1/articles/?${new URLSearchParams({
      magasin,
      recherche,
      ...(famille && { famille }),
      ...(typeVente && { type_vente: typeVente }),
    })}`,
  ).then((page) => page.results);

export const encaisser = (saisie: SaisieVente) =>
  appeler<Vente>("/api/v1/ventes/", { methode: "POST", corps: saisie });

export type Facture = {
  id: string;
  numero: string;
  vente: string;
  client: { id: string; nom: string; matricule_fiscal: string };
  devise: string;
  total_ttc: string;
  timbre_fiscal: string;
  net_a_payer: string;
};

export const trouverVente = (numero: string) =>
  appeler<{ results: Vente[] }>(`/api/v1/ventes/?${new URLSearchParams({ numero })}`).then(
    (page) => page.results[0] ?? null,
  );

/** La facture n'est acceptée que pour une vente entièrement payée ; le client règle le timbre. */
export const genererFacture = (saisie: { vente: string; client?: string; mode_paiement_timbre?: ModePaiement }) =>
  appeler<Facture>("/api/v1/factures/", { methode: "POST", corps: saisie });

export const listerCommandes = (magasin: string) =>
  appeler<{ results: Vente[] }>(
    `/api/v1/ventes/?${new URLSearchParams({ statut: "en_commande", magasin__public_id: magasin })}`,
  ).then((page) => page.results);

export const reglerCommande = (vente: string, reglement: Reglement) =>
  appeler<Vente>(`/api/v1/ventes/${vente}/reglement/`, { methode: "POST", corps: { paiements: [reglement] } });

/** Livre la commande ; le solde éventuel est encaissé en même temps. */
export const livrerCommande = (vente: string, solde: Reglement | null) =>
  appeler<Vente>(`/api/v1/ventes/${vente}/livrer/`, {
    methode: "POST",
    corps: solde ? { paiements: [solde] } : {},
  });
