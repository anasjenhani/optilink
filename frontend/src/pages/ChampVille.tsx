import Autocomplete from "@mui/material/Autocomplete";
import TextField from "@mui/material/TextField";
import { useQuery } from "@tanstack/react-query";

import { listerVilles } from "../api/villes";

/**
 * Ville d'une fiche : on tape les premières lettres et on choisit dans la liste des villes.
 * Le serveur refuse une ville hors de la liste (sauf dans un pays qui n'a pas encore de liste).
 */
export function ChampVille({
  valeur,
  changer,
  lectureSeule = false,
  largeur,
}: {
  valeur: string;
  changer: (ville: string) => void;
  lectureSeule?: boolean;
  largeur?: number;
}) {
  const villes = useQuery({ queryKey: ["villes"], queryFn: listerVilles, staleTime: 5 * 60_000 });
  return (
    <Autocomplete
      freeSolo
      size="small"
      readOnly={lectureSeule}
      options={villes.data?.map((v) => v.nom) ?? []}
      inputValue={valeur}
      onInputChange={(_, texte) => changer(texte)}
      sx={{ width: largeur ?? 260 }}
      renderInput={(params) => <TextField {...params} label="Ville" />}
    />
  );
}
