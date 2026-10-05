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

export type Famille = "monture" | "verre" | "lentille" | "divers" | "supplement";

export const FAMILLES: { valeur: Famille; libelle: string }[] = [
  { valeur: "monture", libelle: "Montures" },
  { valeur: "verre", libelle: "Verres" },
  { valeur: "lentille", libelle: "Lentilles" },
  { valeur: "divers", libelle: "Divers" },
  { valeur: "supplement", libelle: "Suppléments verre" },
];

export type ModePaiement = "carte" | "especes" | "cheque";

export type Vente = {
  id: string;
  numero: string;
  devise: string;
  total_ttc: string;
  /** Part de la CNAM, d'une assurance ou d'une mutuelle (hors refus). */
  pris_en_charge: string;
  reste_a_payer: string;
  statut: "en_commande" | "livree" | "annulee";
  /** Bac numéroté où l'équipement d'une commande attend sa livraison. */
  peniche: number | null;
  livraison_prevue_le: string | null;
  /** Verres commandés au fournisseur ; null si la commande n'en comporte pas. */
  verres?: "a_commander" | "commandes" | "recus" | null;
  facture: string | null;
  client: { id: string; nom: string; matricule_fiscal: string; organisme?: string | null } | null;
  lignes: {
    id: number;
    libelle: string;
    quantite: number;
    quantite_reprise: number;
    total_ttc: string;
    prix_unitaire_ttc: string;
    remise_pct: string;
    taux_tva?: string;
    /** N° de la lunette ou des lentilles qui contiennent l'article, et sa place. */
    lunette?: number | null;
    lentilles?: number | null;
    role?: RoleLigne | "";
    numero_lot?: string;
    date_peremption?: string | null;
  }[];
  lunettes?: Lunette[];
  lentilles?: Lentilles[];
};

/** Lentilles droite et gauche d'une visite, liées à une ordonnance de lentilles. */
export type SaisieLentilles = { prescription: string | null; observation: string };

type LentilleOeil = {
  libelle: string;
  quantite: number;
  numero_lot: string;
  date_peremption: string | null;
  total_ttc: string;
};

export type Lentilles = SaisieLentilles & {
  numero: number;
  droite: LentilleOeil | null;
  gauche: LentilleOeil | null;
  total_ttc: string;
};

export type LentillesClient = Lentilles & {
  id: string;
  vente: string;
  vente_numero: string;
  date: string;
  peniche: number | null;
};

export const listerLentillesClient = (client: string) =>
  appeler<{ results: LentillesClient[] }>(`/api/v1/lentilles/?${new URLSearchParams({ client })}`).then(
    (page) => page.results,
  );

export type RoleLigne =
  | "monture"
  | "verre_d"
  | "verre_g"
  | "supplement_d"
  | "supplement_g"
  | "lentille_d"
  | "lentille_g";
export type Vision = "loin" | "pres" | "double_foyer" | "degressif" | "progressif";

export const VISIONS: { valeur: Vision; libelle: string }[] = [
  { valeur: "loin", libelle: "Loin" },
  { valeur: "pres", libelle: "Près" },
  { valeur: "double_foyer", libelle: "Double foyer" },
  { valeur: "degressif", libelle: "Dégressif" },
  { valeur: "progressif", libelle: "Progressif" },
];

/** Paire de lunettes : vision, ordonnance, mesures de montage (mm). */
export type SaisieLunette = {
  vision: Vision | "";
  solaire: boolean;
  inadaptation: boolean;
  prescription: string | null;
  oeil_directeur: "" | "droit" | "gauche";
  ecart_d: string | null;
  ecart_g: string | null;
  ecart_pres_d: string | null;
  ecart_pres_g: string | null;
  hauteur_d: string | null;
  hauteur_g: string | null;
  observation: string;
  client_absent: boolean;
};

export type Lunette = SaisieLunette & {
  numero: number;
  vision_libelle: string;
  monture: string | null;
  verre_d: string | null;
  verre_g: string | null;
  supplements_d: string[];
  supplements_g: string[];
};

export type LunetteClient = Lunette & {
  id: string;
  vente: string;
  vente_numero: string;
  date: string;
  magasin: string;
  peniche: number | null;
  statut: Vente["statut"];
};

export const listerLunettesClient = (client: string) =>
  appeler<{ results: LunetteClient[] }>(`/api/v1/lunettes/?${new URLSearchParams({ client })}`).then(
    (page) => page.results,
  );

export type SaisieVente = {
  magasin: string;
  client?: string;
  lignes: {
    article: string;
    quantite: number;
    remise_pct?: string;
    lunette?: number;
    lentilles?: number;
    role?: RoleLigne;
    numero_lot?: string;
    date_peremption?: string;
  }[];
  paiements: { mode: ModePaiement; montant: string }[];
  /** Paires de lunettes ; leurs articles sont dans ``lignes`` (``lunette`` = rang dans cette liste). */
  lunettes?: SaisieLunette[];
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
  { valeur: "lentille", libelle: "Lentilles", aide: "Lentilles de contact et leurs produits" },
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

export const encaisser = (saisie: SaisieVente) => appeler<Vente>("/api/v1/ventes/", { methode: "POST", corps: saisie });

export type Facture = {
  id: string;
  numero: string;
  /** Code du magasin émetteur. */
  magasin: string;
  vente: string;
  /** Tel qu'imprimé à l'émission. */
  client: { id: string; nom: string; adresse: string; matricule_fiscal: string };
  cree_le: string;
  emise_par: string;
  devise: string;
  total_ht: string;
  total_tva: string;
  total_ttc: string;
  timbre_fiscal: string;
  net_a_payer: string;
  mode_paiement_timbre: ModePaiement | "";
  lignes: Vente["lignes"];
};

export const trouverVente = (numero: string) =>
  appeler<{ results: Vente[] }>(`/api/v1/ventes/?${new URLSearchParams({ numero })}`).then(
    (page) => page.results[0] ?? null,
  );

/** La facture n'est acceptée que pour une vente entièrement payée ; le client règle le timbre. */
export const genererFacture = (saisie: { vente: string; client?: string; mode_paiement_timbre?: ModePaiement }) =>
  appeler<Facture>("/api/v1/factures/", { methode: "POST", corps: saisie });

/** Factures émises, les plus récentes d'abord ; le n° se cherche en entier. */
export const listerFactures = (numero: string, page = 1) => {
  const parametres = new URLSearchParams({ page: String(page) });
  if (numero.trim()) parametres.set("numero", numero.trim());
  return appeler<{ count: number; results: Facture[] }>(`/api/v1/factures/?${parametres}`);
};

export const lireFacture = (id: string) => appeler<Facture>(`/api/v1/factures/${id}/`);

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
