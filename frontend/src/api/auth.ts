import { appeler } from "./client";

export type EtatMfa = "verifiee" | "a_verifier" | "a_activer" | "non_requise";

export type EtatSession = {
  authentifie: boolean;
  mfa: EtatMfa | null;
  utilisateur: { identifiant: string; nom_complet: string; permissions: string[] } | null;
};

export type ActivationMfa = { uri: string; cle: string; qr_svg: string };

export const lireSession = () => appeler<EtatSession>("/api/v1/auth/session/");

export const connecter = (identifiant: string, mot_de_passe: string) =>
  appeler<EtatSession>("/api/v1/auth/connexion/", {
    methode: "POST",
    corps: { identifiant, mot_de_passe },
  });

export const verifierCode = (code: string) =>
  appeler<EtatSession>("/api/v1/auth/mfa/verification/", { methode: "POST", corps: { code } });

export const demarrerActivation = () =>
  appeler<ActivationMfa>("/api/v1/auth/mfa/activation/", { methode: "POST" });

export const confirmerActivation = (code: string) =>
  appeler<{ codes_secours: string[]; session: EtatSession }>(
    "/api/v1/auth/mfa/activation/confirmation/",
    { methode: "POST", corps: { code } },
  );

export const deconnecter = () => appeler<void>("/api/v1/auth/deconnexion/", { methode: "POST" });

/** Affichage seulement : l'API revérifie toujours la permission. */
export function peut(session: EtatSession | undefined, permission: string) {
  return session?.utilisateur?.permissions.includes(permission) ?? false;
}
