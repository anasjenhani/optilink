// Affectations d'un utilisateur dans l'administration : en portée « Magasin », la société se
// remplit d'après le magasin choisi (voir AffectationForm).
document.addEventListener("change", (evenement) => {
  const champ = evenement.target;
  const nom = champ.name || "";
  const prefixe = nom.replace(/(magasin|portee)$/, "");
  if (prefixe === nom || !prefixe.startsWith("affectations-")) return;
  const magasin = document.querySelector(`select[name="${prefixe}magasin"]`);
  const portee = document.querySelector(`select[name="${prefixe}portee"]`);
  const societe = document.querySelector(`select[name="${prefixe}societe"]`);
  if (!magasin || !societe || !portee || portee.value !== "magasin") return;
  const societes = JSON.parse(magasin.dataset.societes || "{}");
  societe.value = societes[magasin.value] || "";
});
