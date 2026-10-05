/**
 * Montants en unités entières de la monnaie (centimes d'euro, millimes de dinar…) pour éviter
 * les erreurs d'arrondi des nombres à virgule. Le nombre de décimales vient du pays du magasin.
 */
export type Monnaie = { devise: string; decimales: number };

export const enUnites = (montant: string, decimales: number) =>
  Math.round(Number(montant) * 10 ** decimales);

export const versTexte = (unites: number, decimales: number) =>
  (unites / 10 ** decimales).toFixed(decimales);

/** « 289,500 DT », « 149,00 € » : affichage selon la monnaie. */
export function formater(unites: number, { devise, decimales }: Monnaie) {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: devise,
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales,
  }).format(unites / 10 ** decimales);
}

export const formaterTexte = (montant: string, monnaie: Monnaie) =>
  formater(enUnites(montant, monnaie.decimales), monnaie);
