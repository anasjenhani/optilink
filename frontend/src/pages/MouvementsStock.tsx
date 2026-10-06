import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listerMagasins } from "../api/magasins";
import { listerMouvements, TYPES_MOUVEMENT, type FiltresMouvements } from "../api/mouvements";
import { BANDEAU, BORDEAUX, useApaise } from "./RechercheClients";

const dateHeure = (iso: string) => new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });

const COLONNES = ["Date", "Magasin", "Code article", "Libellé", "Type", "Quantité", "Référence", "Utilisateur"];

/**
 * « Mouvements de Stock » : consultation des entrées et sorties des magasins du périmètre.
 * Lecture seule : un mouvement ne se modifie pas, on corrige par un nouveau mouvement.
 */
export function MouvementsStock() {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [filtres, setFiltres] = useState<FiltresMouvements>({});
  const [page, setPage] = useState(1);
  const recherche = useApaise(filtres);
  const mouvements = useQuery({
    queryKey: ["mouvements-stock", recherche, page],
    queryFn: () => listerMouvements(recherche, page),
    placeholderData: keepPreviousData,
  });
  const pages = Math.max(1, Math.ceil((mouvements.data?.count ?? 0) / 50));
  const filtrer = (cle: keyof FiltresMouvements, valeur: string) => {
    setFiltres((f) => ({ ...f, [cle]: valeur }));
    setPage(1);
  };
  const date = (cle: "du" | "au", label: string) => (
    <TextField
      size="small"
      type="date"
      label={label}
      value={filtres[cle] ?? ""}
      onChange={(e) => filtrer(cle, e.target.value)}
      slotProps={{ inputLabel: { shrink: true } }}
    />
  );

  return (
    <Stack spacing={1}>
      <Box sx={{ px: 3, py: 1, borderRadius: 1, background: BANDEAU }}>
        <Typography variant="h5" component="h3" sx={{ color: "common.white", fontWeight: 500 }}>
          Mouvements de Stock
        </Typography>
      </Box>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ flexWrap: "wrap", rowGap: 1 }}>
        <TextField
          select
          size="small"
          label="Magasin"
          value={filtres.magasin ?? ""}
          onChange={(e) => filtrer("magasin", e.target.value)}
          sx={{ minWidth: 180 }}
        >
          <MenuItem value="">Tous les magasins</MenuItem>
          {magasins.data?.map((m) => (
            <MenuItem key={m.id} value={m.id}>
              {m.nom}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          size="small"
          label="Article"
          helperText="Code article ou code-barres"
          value={filtres.article ?? ""}
          onChange={(e) => filtrer("article", e.target.value)}
        />
        <TextField
          select
          size="small"
          label="Type"
          value={filtres.type ?? ""}
          onChange={(e) => filtrer("type", e.target.value)}
          sx={{ minWidth: 200 }}
        >
          <MenuItem value="">Tous les types</MenuItem>
          {Object.entries(TYPES_MOUVEMENT).map(([valeur, libelle]) => (
            <MenuItem key={valeur} value={valeur}>
              {libelle}
            </MenuItem>
          ))}
        </TextField>
        {date("du", "Du")}
        {date("au", "Au")}
      </Stack>
      {mouvements.isError && <Alert severity="error">{mouvements.error.message}</Alert>}
      <TableContainer sx={{ maxHeight: 560, border: 1, borderColor: "grey.400", borderRadius: 1 }}>
        <Table stickyHeader size="small" aria-label="Mouvements de stock">
          <TableHead>
            <TableRow>
              {COLONNES.map((titre) => (
                <TableCell
                  key={titre}
                  align={titre === "Quantité" ? "right" : "left"}
                  sx={{ color: BORDEAUX, fontWeight: 700, bgcolor: "grey.100", whiteSpace: "nowrap" }}
                >
                  {titre}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {mouvements.data?.results.map((m) => (
              <TableRow key={m.id} sx={{ "& td": { borderColor: "#d9a3a3", whiteSpace: "nowrap" } }}>
                <TableCell>{dateHeure(m.horodatage)}</TableCell>
                <TableCell>{m.magasin_nom}</TableCell>
                <TableCell>{m.article_reference}</TableCell>
                <TableCell>{m.article_libelle}</TableCell>
                <TableCell>{m.type_libelle}</TableCell>
                <TableCell
                  align="right"
                  sx={{ fontWeight: 700, color: m.quantite > 0 ? "success.main" : "error.main" }}
                >
                  {m.quantite > 0 ? `+${m.quantite}` : m.quantite}
                </TableCell>
                <TableCell>{m.reference}</TableCell>
                <TableCell>{m.utilisateur}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {mouvements.data?.count === 0 && (
          <Box sx={{ p: 2 }}>
            <Typography color="text.secondary">Aucun mouvement.</Typography>
          </Box>
        )}
      </TableContainer>
      <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
        <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
          {mouvements.data ? `${mouvements.data.count} mouvement${mouvements.data.count > 1 ? "s" : ""}` : ""}
        </Typography>
        {pages > 1 && (
          <>
            <Button size="small" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Précédente
            </Button>
            <Typography variant="body2">
              Page {page} / {pages}
            </Typography>
            <Button size="small" disabled={page >= pages} onClick={() => setPage(page + 1)}>
              Suivante
            </Button>
          </>
        )}
      </Stack>
    </Stack>
  );
}
