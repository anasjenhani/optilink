import MenuItem from "@mui/material/MenuItem";
import TextField from "@mui/material/TextField";

import { MODES_PAIEMENT, type ModePaiement, type Piece } from "../api/caisse";

/** Chèque et traite passent à la banque plus tard : ils ont une échéance et peuvent revenir impayés. */
export const aEcheance = (mode: ModePaiement) => mode === "cheque" || mode === "traite";
export const avecPiece = (mode: ModePaiement) => aEcheance(mode) || mode === "virement";

/** Ce qu'il faut envoyer à l'API pour la pièce du mode choisi. */
export function piece(mode: ModePaiement, saisie: Piece): Piece {
  if (!avecPiece(mode)) return {};
  return {
    reference: saisie.reference?.trim() ?? "",
    banque: saisie.banque?.trim() ?? "",
    ...(aEcheance(mode) && saisie.echeance ? { echeance: saisie.echeance } : {}),
  };
}

/** Liste des modes de paiement. */
export function ChoixMode({
  valeur,
  onChange,
  label = "Paiement",
  modes = MODES_PAIEMENT,
}: {
  valeur: ModePaiement;
  onChange: (mode: ModePaiement) => void;
  label?: string;
  modes?: typeof MODES_PAIEMENT;
}) {
  return (
    <TextField
      select
      size="small"
      label={label}
      value={valeur}
      onChange={(e) => onChange(e.target.value as ModePaiement)}
      sx={{ minWidth: 150 }}
    >
      {modes.map((m) => (
        <MenuItem key={m.valeur} value={m.valeur}>
          {m.libelle}
        </MenuItem>
      ))}
    </TextField>
  );
}

/** N° de pièce, banque et échéance, selon le mode. Rien pour les espèces et la carte. */
export function ChampsPiece({
  mode,
  valeur,
  onChange,
}: {
  mode: ModePaiement;
  valeur: Piece;
  onChange: (piece: Piece) => void;
}) {
  if (!avecPiece(mode)) return null;
  return (
    <>
      <TextField
        size="small"
        label={mode === "cheque" ? "N° chèque" : mode === "traite" ? "N° traite" : "N° virement"}
        value={valeur.reference ?? ""}
        onChange={(e) => onChange({ ...valeur, reference: e.target.value })}
        required={aEcheance(mode)}
        sx={{ width: 150 }}
      />
      <TextField
        size="small"
        label="Banque"
        value={valeur.banque ?? ""}
        onChange={(e) => onChange({ ...valeur, banque: e.target.value })}
        sx={{ width: 150 }}
      />
      {aEcheance(mode) && (
        <TextField
          size="small"
          type="date"
          label="Échéance"
          value={valeur.echeance ?? ""}
          onChange={(e) => onChange({ ...valeur, echeance: e.target.value })}
          slotProps={{ inputLabel: { shrink: true } }}
        />
      )}
    </>
  );
}
