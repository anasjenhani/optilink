import { appeler } from "./client";

export type Client = {
  id: string;
  /** N° de fiche, attribué par le serveur à la création. */
  numero: number;
  civilite: "" | "mme" | "m";
  nom: string;
  prenom: string;
  date_naissance: string | null;
  telephone: string;
  telephone_2: string;
  email: string;
  adresse: string;
  code_postal: string;
  ville: string;
  societe: string;
  matricule_fiscal: string;
  magasin_origine: string;
  accepte_relances: boolean;
};

export type SaisieClient = Omit<Client, "id" | "numero">;

export type MesureOeil = { sphere: string; cylindre?: string; axe?: number | null; addition?: string | null };

export type Prescription = {
  id: string;
  type: "lunettes" | "lentilles";
  date_prescription: string;
  prescripteur: string;
  mesures: { od: MesureOeil; og: MesureOeil; ecart_pupillaire?: string | null; remarques?: string };
  saisie_par: string;
};

export type SaisiePrescription = Omit<Prescription, "id" | "saisie_par"> & {
  client: string;
  magasin_saisie: string;
  prescripteur_identifiant: string;
};

export const chercherClients = (recherche: string) =>
  appeler<{ results: Client[] }>(`/api/v1/clients/?${new URLSearchParams({ recherche })}`).then(
    (page) => page.results,
  );

export const creerClient = (saisie: SaisieClient) =>
  appeler<Client>("/api/v1/clients/", { methode: "POST", corps: saisie });

export const modifierClient = (id: string, saisie: Partial<SaisieClient>) =>
  appeler<Client>(`/api/v1/clients/${id}/`, { methode: "PATCH", corps: saisie });

/** Chaque appel est journalisé côté serveur comme une consultation du dossier. */
export const listerPrescriptions = (client: string) =>
  appeler<{ results: Prescription[] }>(
    `/api/v1/prescriptions/?${new URLSearchParams({ client })}`,
  ).then((page) => page.results);

export const saisirPrescription = (saisie: SaisiePrescription) =>
  appeler<Prescription>("/api/v1/prescriptions/", { methode: "POST", corps: saisie });

/** « DUPONT Marie · fiche n° 12 » */
export const nomClient = (client: Pick<Client, "nom" | "prenom" | "numero">) =>
  `${client.nom.toUpperCase()} ${client.prenom} · fiche n° ${client.numero}`;

/** « -2.25 (-0.50 à 90°) add +2.00 » : notation habituelle d'une ordonnance. */
export function formaterOeil(oeil: MesureOeil) {
  const signe = (valeur: string) => (Number(valeur) > 0 ? `+${valeur}` : valeur);
  let texte = signe(oeil.sphere);
  if (oeil.cylindre && Number(oeil.cylindre) !== 0) texte += ` (${signe(oeil.cylindre)} à ${oeil.axe}°)`;
  if (oeil.addition && Number(oeil.addition) !== 0) texte += ` add ${signe(oeil.addition)}`;
  return texte;
}
