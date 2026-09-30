import TextField from "@mui/material/TextField";

export function ChampCode(props: { valeur: string; onChange: (valeur: string) => void; aide?: string }) {
  return (
    <TextField
      label="Code"
      autoComplete="one-time-code"
      helperText={props.aide}
      value={props.valeur}
      onChange={(e) => props.onChange(e.target.value.trim())}
      slotProps={{ htmlInput: { inputMode: "numeric", maxLength: 16 } }}
      autoFocus
      required
    />
  );
}
