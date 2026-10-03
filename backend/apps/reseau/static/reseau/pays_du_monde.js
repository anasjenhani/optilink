// Fiche d'un pays dans l'administration : le choix dans la liste des pays du monde remplit
// codes ISO, devise, décimales, indicatif et fuseau horaire (voir PaysForm).
document.addEventListener("DOMContentLoaded", () => {
  const liste = document.getElementById("id_pays_du_monde");
  if (!liste) return;
  const pays = JSON.parse(liste.dataset.pays);
  liste.addEventListener("change", () => {
    const choisi = pays[liste.value];
    if (!choisi) return;
    for (const [champ, valeur] of Object.entries(choisi)) {
      const entree = document.getElementById(`id_${champ}`);
      if (entree) entree.value = valeur;
    }
  });
});
