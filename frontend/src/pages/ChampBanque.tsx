import Autocomplete, { createFilterOptions } from "@mui/material/Autocomplete";
import TextField from "@mui/material/TextField";
import { useQuery } from "@tanstack/react-query";

import { listerBanques, type Banque } from "../api/banques";

// On retrouve une banque en tapant son sigle (BIAT) aussi bien que son nom.
const filtrer = createFilterOptions<Banque | string>({
  stringify: (b) => (typeof b === "string" ? b : `${b.sigle} ${b.nom}`),
});

/**
 * Banque d'une fiche : on tape le sigle ou le nom et on choisit dans la liste des banques.
 * Le serveur refuse une banque hors de la liste et un RIB qui ne va pas avec la banque.
 */
export function ChampBanque({
  valeur,
  changer,
  lectureSeule = false,
  largeur,
}: {
  valeur: string;
  changer: (banque: string) => void;
  lectureSeule?: boolean;
  largeur?: number;
}) {
  const banques = useQuery({ queryKey: ["banques"], queryFn: listerBanques, staleTime: 5 * 60_000 });
  return (
    <Autocomplete<Banque | string, false, false, true>
      freeSolo
      size="small"
      readOnly={lectureSeule}
      options={banques.data ?? []}
      filterOptions={filtrer}
      getOptionLabel={(b) => (typeof b === "string" ? b : b.nom)}
      renderOption={({ key, ...props }, b) => (
        <li key={key} {...props}>
          {typeof b === "string" ? b : `${b.sigle} · ${b.nom}`}
        </li>
      )}
      inputValue={valeur}
      onInputChange={(_, texte) => changer(texte)}
      sx={{ width: largeur ?? 260 }}
      renderInput={(params) => <TextField {...params} label="Banque" />}
    />
  );
}
