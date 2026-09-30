export type EtatSante = {
  statut: "ok" | "degrade";
  base_de_donnees: string;
  cache: string;
};

export async function lireSante(): Promise<EtatSante> {
  const reponse = await fetch("/api/v1/sante/");
  // 503 renvoie aussi un corps lisible : on l'affiche plutôt que de lever une erreur.
  if (!reponse.ok && reponse.status !== 503) {
    throw new Error(`API injoignable (${reponse.status})`);
  }
  return reponse.json();
}
