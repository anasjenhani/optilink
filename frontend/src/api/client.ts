export class ErreurApi extends Error {
  constructor(
    message: string,
    readonly statut: number,
  ) {
    super(message);
  }
}

function lireCookie(nom: string): string | undefined {
  return document.cookie
    .split("; ")
    .find((ligne) => ligne.startsWith(`${nom}=`))
    ?.slice(nom.length + 1);
}

/** Appel JSON vers l'API, avec le cookie de session et le jeton CSRF de Django. */
export async function appeler<T>(url: string, options: { methode?: string; corps?: unknown } = {}): Promise<T> {
  const methode = options.methode ?? "GET";
  const entetes: Record<string, string> = { Accept: "application/json" };
  if (methode !== "GET") {
    entetes["Content-Type"] = "application/json";
    entetes["X-CSRFToken"] = decodeURIComponent(lireCookie("csrftoken") ?? "");
  }
  const reponse = await fetch(url, {
    method: methode,
    headers: entetes,
    credentials: "same-origin",
    body: options.corps === undefined ? undefined : JSON.stringify(options.corps),
  });
  if (reponse.status === 204) {
    return undefined as T;
  }
  const donnees = await reponse.json().catch(() => ({}));
  if (!reponse.ok) {
    throw new ErreurApi(messageErreur(donnees) ?? `Erreur ${reponse.status}`, reponse.status);
  }
  return donnees as T;
}

/**
 * Envoi d'un fichier (multipart). Rend la réponse même en erreur 400 : un import refusé
 * renvoie son rapport, ligne par ligne, que l'écran affiche.
 */
export async function envoyerFichier<T>(url: string, formulaire: FormData): Promise<T> {
  const reponse = await fetch(url, {
    method: "POST",
    headers: { Accept: "application/json", "X-CSRFToken": decodeURIComponent(lireCookie("csrftoken") ?? "") },
    credentials: "same-origin",
    body: formulaire,
  });
  const donnees = await reponse.json().catch(() => ({}));
  if (!reponse.ok && !(reponse.status === 400 && "erreurs" in donnees)) {
    throw new ErreurApi(messageErreur(donnees) ?? `Erreur ${reponse.status}`, reponse.status);
  }
  return donnees as T;
}

/** Premier message lisible d'une réponse d'erreur DRF (``detail`` ou erreurs par champ). */
function messageErreur(donnees: unknown): string | undefined {
  if (typeof donnees === "string") return donnees;
  if (Array.isArray(donnees)) return messageErreur(donnees[0]);
  if (donnees && typeof donnees === "object") {
    const objet = donnees as Record<string, unknown>;
    return messageErreur(objet.detail ?? Object.values(objet)[0]);
  }
  return undefined;
}
