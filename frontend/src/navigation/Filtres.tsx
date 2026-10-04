import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";

/** Rangée de boutons de filtre, comme en bas des listes de l'ancien logiciel ; le choix est vert. */
export function Filtres<T extends string | number>({
  libelle,
  options,
  valeur,
  onChange,
}: {
  libelle: string;
  options: { valeur: T; libelle: string }[];
  valeur: T;
  onChange: (valeur: T) => void;
}) {
  return (
    <Stack
      role="group"
      aria-label={libelle}
      direction="row"
      sx={{ flexWrap: "wrap", gap: 0.5, py: 0.5, borderTop: 1, borderColor: "divider" }}
    >
      {options.map((o) => {
        const actif = o.valeur === valeur;
        return (
          <Button
            key={String(o.valeur)}
            size="small"
            variant="outlined"
            aria-pressed={actif}
            onClick={() => onChange(o.valeur)}
            sx={{
              textTransform: "none",
              color: "text.primary",
              borderColor: actif ? "#5aa83c" : "#9cc3e6",
              background: actif
                ? "linear-gradient(180deg, #c8f0b0 0%, #8fd26c 100%)"
                : "linear-gradient(180deg, #f4f9fe 0%, #d6e8f8 100%)",
            }}
          >
            {o.libelle}
          </Button>
        );
      })}
    </Stack>
  );
}
