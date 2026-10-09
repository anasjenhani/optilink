import Autocomplete from "@mui/material/Autocomplete";
import TextField from "@mui/material/TextField";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ajouterOphtalmologue, chercherOphtalmologues } from "../api/ophtalmologues";
import { useApaise } from "./RechercheClients";

type Choix = { nom: string; ajout?: boolean };

/**
 * Ophtalmologiste d'une ordonnance : on le cherche dans la liste, ou on l'ajoute. L'ajout est refusé si
 * le médecin y est déjà (« Dr Ben Salah » = « BEN-SALAH ») : on le choisit alors dans la liste.
 */
export function ChampOphtalmo({
  valeur,
  changer,
  label = "Ophtalmologiste",
  largeur,
}: {
  valeur: string;
  changer: (nom: string) => void;
  label?: string;
  largeur?: number;
}) {
  const [saisie, setSaisie] = useState(valeur);
  const [erreur, setErreur] = useState("");
  const recherche = useApaise(saisie);
  const client = useQueryClient();
  const medecins = useQuery({
    queryKey: ["ophtalmologues", recherche],
    queryFn: () => chercherOphtalmologues(recherche),
    // Pendant la nouvelle recherche, la liste précédente reste affichée (pas de clignotement).
    placeholderData: keepPreviousData,
  });
  const ajout = useMutation({
    mutationFn: ajouterOphtalmologue,
    onSuccess: (medecin) => {
      void client.invalidateQueries({ queryKey: ["ophtalmologues"] });
      changer(medecin.nom);
      setSaisie(medecin.nom);
    },
    onError: (e) => setErreur(e instanceof Error ? e.message : String(e)),
  });

  const noms = medecins.data?.map((m) => m.nom) ?? [];
  const texte = saisie.trim();
  const options: Choix[] = [
    ...noms.map((nom) => ({ nom })),
    ...(texte && !noms.some((n) => n.toLowerCase() === texte.toLowerCase()) ? [{ nom: texte, ajout: true }] : []),
  ];

  return (
    <Autocomplete<Choix>
      size="small"
      options={options}
      value={valeur ? { nom: valeur } : null}
      inputValue={saisie}
      onInputChange={(_, t, raison) => {
        if (raison === "reset" && !t && saisie) return;
        setSaisie(t);
        setErreur("");
        if (raison === "input" && valeur) changer("");
      }}
      onChange={(_, choix) => {
        if (!choix) return changer("");
        if (choix.ajout) return ajout.mutate(choix.nom);
        changer(choix.nom);
      }}
      filterOptions={(o) => o}
      getOptionLabel={(o) => o.nom}
      isOptionEqualToValue={(a, b) => a.nom === b.nom && !a.ajout}
      renderOption={({ key, ...props }, o) => (
        <li key={`${key}-${o.ajout ? "ajout" : ""}`} {...props}>
          {o.ajout ? `Ajouter « ${o.nom} » à la liste` : o.nom}
        </li>
      )}
      noOptionsText="Tapez le nom du médecin"
      sx={{ flex: largeur ? undefined : 1, width: largeur, minWidth: 220 }}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          error={Boolean(erreur)}
          helperText={erreur || (ajout.isPending ? "Ajout…" : undefined)}
        />
      )}
    />
  );
}
