import { appeler } from "./client";

export type MotifSav = "casse" | "reglage" | "defaut" | "adaptation" | "autre";
export type EtapeSav = "recu" | "atelier" | "fournisseur" | "pret" | "rendu" | "annule";

export const MOTIFS_SAV: { valeur: MotifSav; libelle: string }[] = [
  { valeur: "casse", libelle: "Casse" },
  { valeur: "reglage", libelle: "Réglage, ajustage" },
  { valeur: "defaut", libelle: "Défaut de fabrication" },
  { valeur: "adaptation", libelle: "Non-adaptation aux verres" },
  { valeur: "autre", libelle: "Autre" },
];

export const ETAPES_SAV: { valeur: EtapeSav; libelle: string }[] = [
  { valeur: "recu", libelle: "Reçu au magasin" },
  { valeur: "atelier", libelle: "À l'atelier" },
  { valeur: "fournisseur", libelle: "Envoyé au fournisseur" },
  { valeur: "pret", libelle: "Prêt à rendre" },
  { valeur: "rendu", libelle: "Rendu au client" },
  { valeur: "annule", libelle: "Annulé" },
];

export type EvenementSav = { etape: EtapeSav; etape_libelle: string; commentaire: string; le: string; par: string };

export type DossierSav = {
  id: string;
  numero: string;
  magasin: string;
  magasin_nom: string;
  client: string;
  client_nom: string;
  client_telephone: string;
  vente: string | null;
  vente_numero: string | null;
  article: string | null;
  designation: string;
  motif: MotifSav;
  motif_libelle: string;
  description: string;
  sous_garantie: boolean;
  fournisseur: string | null;
  fournisseur_nom: string | null;
  etape: EtapeSav;
  etape_libelle: string;
  est_ouvert: boolean;
  en_retard: boolean;
  retour_prevu_le: string | null;
  solution: string;
  cree_le: string;
  cree_par: string;
  evenements: EvenementSav[];
};

export type FiltresSav = { etape?: string; retard?: boolean; client?: string; q?: string };

export type OuvertureSav = {
  magasin: string;
  client: string;
  vente?: string | null;
  designation: string;
  motif: MotifSav;
  description?: string;
  sous_garantie?: boolean;
  retour_prevu_le?: string | null;
};

export type ChangementEtape = {
  etape: EtapeSav;
  commentaire?: string;
  fournisseur?: string | null;
  retour_prevu_le?: string | null;
  solution?: string;
};

export const listerDossiersSav = ({ etape, retard, client, q }: FiltresSav) => {
  const parametres = new URLSearchParams();
  if (etape) parametres.set("etape", etape);
  if (retard) parametres.set("retard", "1");
  if (client) parametres.set("client", client);
  if (q?.trim()) parametres.set("q", q.trim());
  return appeler<{ results: DossierSav[] }>(`/api/v1/sav/?${parametres}`).then((page) => page.results);
};

export const ouvrirDossierSav = (saisie: OuvertureSav) =>
  appeler<DossierSav>("/api/v1/sav/", { methode: "POST", corps: saisie });

export const changerEtapeSav = (id: string, changement: ChangementEtape) =>
  appeler<DossierSav>(`/api/v1/sav/${id}/etape/`, { methode: "POST", corps: changement });
