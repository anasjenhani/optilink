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
    const detail = typeof donnees?.detail === "string" ? donnees.detail : `Erreur ${reponse.status}`;
    throw new ErreurApi(detail, reponse.status);
  }
  return donnees as T;
}
