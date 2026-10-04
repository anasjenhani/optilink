import Refresh from "@mui/icons-material/Refresh";
import AddCircle from "@mui/icons-material/AddCircle";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TableSortLabel from "@mui/material/TableSortLabel";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { listerClients, type Client, type FiltresClients } from "../api/clients";
import { listerMagasins } from "../api/magasins";

type Colonne = {
  cle: "fiche" | "telephone" | "nom" | "solde" | "prenom" | "observation";
  titre: string;
  largeur?: number;
  tri?: "fiche" | "nom";
};

const COLONNES: Colonne[] = [
  { cle: "fiche", titre: "N° Fiche", largeur: 150, tri: "fiche" },
  { cle: "telephone", titre: "N° Téléphone", largeur: 140 },
  { cle: "nom", titre: "Nom & Prénom", tri: "nom" },
  { cle: "solde", titre: "Solde", largeur: 110 },
  { cle: "prenom", titre: "Prénom", largeur: 150 },
  { cle: "observation", titre: "Observation" },
];

const BORDEAUX = "#8b1414";
const BANDEAU = "linear-gradient(180deg, #c45a5a 0%, #9b1c1c 45%, #7a1010 100%)";
const BOUTON = {
  color: "text.primary",
  textTransform: "none",
  border: 1,
  borderColor: "grey.400",
  background: "linear-gradient(180deg, #ffffff 0%, #d6e8f8 100%)",
  "&:hover": { background: "linear-gradient(180deg, #ffffff 0%, #c2dcf3 100%)" },
} as const;

/** Attend que la saisie se calme avant d'interroger le serveur. */
function useApaise<T>(valeur: T, delai = 300) {
  const [apaisee, setApaisee] = useState(valeur);
  useEffect(() => {
    const minuterie = setTimeout(() => setApaisee(valeur), delai);
    return () => clearTimeout(minuterie);
  }, [valeur, delai]);
  return apaisee;
}

function cellule(client: Client, cle: Colonne["cle"], solde: (montant: string) => string) {
  switch (cle) {
    case "fiche":
      return client.reference_externe || String(client.numero);
    case "telephone":
      return client.telephone || client.telephone_2;
    case "nom":
      return `${client.nom} ${client.prenom}`.toUpperCase();
    case "solde":
      return client.solde == null ? "" : solde(client.solde);
    case "prenom":
      return client.prenom.toUpperCase();
    case "observation":
      return client.notes ?? "";
  }
}

/**
 * Tableau « Recherche Clients » de l'ancien logiciel : un filtre sous chaque colonne, un clic
 * sur une ligne choisit le client, et le bouton Nouveau Client ouvre une fiche vierge.
 */
export function RechercheClients({
  onChoisi,
  onNouveau,
  onPassage,
}: {
  onChoisi: (client: Client) => void;
  onNouveau?: () => void;
  onPassage?: () => void;
}) {
  const [filtres, setFiltres] = useState<Record<string, string>>({});
  const [tri, setTri] = useState<FiltresClients["tri"]>("nom");
  const [page, setPage] = useState(1);
  const recherche = useApaise(filtres);
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const decimales = magasins.data?.[0]?.pays.decimales ?? 3;
  const clients = useQuery({
    queryKey: ["clients", "tableau", recherche, tri, page],
    queryFn: () => listerClients({ ...recherche, tri }, page),
    placeholderData: keepPreviousData,
  });
  const lignes = clients.data?.results ?? [];
  const pages = Math.max(1, Math.ceil((clients.data?.count ?? 0) / 50));
  const solde = (montant: string) =>
    new Intl.NumberFormat("fr-FR", { minimumFractionDigits: decimales, maximumFractionDigits: decimales }).format(
      Number(montant),
    );

  function filtrer(cle: string, valeur: string) {
    setFiltres((f) => ({ ...f, [cle]: valeur }));
    setPage(1);
  }

  function trier(cle: "fiche" | "nom") {
    setTri(tri === cle ? `-${cle}` : cle);
    setPage(1);
  }

  return (
    <Stack spacing={1}>
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={1}
        sx={{ px: 3, py: 1, borderRadius: 1, alignItems: { sm: "center" }, background: BANDEAU }}
      >
        <Typography variant="h5" component="h3" sx={{ flex: 1, color: "common.white", fontWeight: 500 }}>
          Recherche Clients
        </Typography>
        <Button startIcon={<Refresh sx={{ color: "success.main" }} />} sx={BOUTON} onClick={() => clients.refetch()}>
          Actualiser
        </Button>
        {onNouveau && (
          <Button startIcon={<AddCircle sx={{ color: "success.main" }} />} sx={BOUTON} onClick={onNouveau}>
            Nouveau Client
          </Button>
        )}
        {onPassage && (
          <Button sx={BOUTON} onClick={onPassage}>
            Client de passage
          </Button>
        )}
      </Stack>
      {clients.isError && <Alert severity="error">{clients.error.message}</Alert>}
      <TableContainer sx={{ maxHeight: 520, border: 1, borderColor: "grey.400", borderRadius: 1 }}>
        <Table stickyHeader size="small" aria-label="Recherche clients">
          <TableHead>
            <TableRow>
              {COLONNES.map((c) => (
                <TableCell
                  key={c.cle}
                  align={c.cle === "solde" ? "right" : "left"}
                  sx={{ width: c.largeur, color: BORDEAUX, fontWeight: 700, bgcolor: "grey.100" }}
                >
                  {c.tri ? (
                    <TableSortLabel
                      active={tri?.replace("-", "") === c.tri}
                      direction={tri === `-${c.tri}` ? "desc" : "asc"}
                      onClick={() => trier(c.tri!)}
                    >
                      {c.titre}
                    </TableSortLabel>
                  ) : (
                    c.titre
                  )}
                </TableCell>
              ))}
            </TableRow>
            <TableRow>
              {COLONNES.map((c) => (
                <TableCell key={c.cle} sx={{ top: 37, p: 0.5, bgcolor: BORDEAUX }}>
                  {c.cle !== "solde" && (
                    <TextField
                      size="small"
                      fullWidth
                      autoFocus={c.cle === "nom"}
                      value={filtres[c.cle] ?? ""}
                      onChange={(e) => filtrer(c.cle, e.target.value)}
                      slotProps={{
                        htmlInput: { "aria-label": `Filtrer ${c.titre}` },
                        input: { sx: { bgcolor: "common.white", height: 28, fontSize: 14 } },
                      }}
                    />
                  )}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {lignes.map((client) => (
              <TableRow
                key={client.id}
                hover
                onClick={() => onChoisi(client)}
                sx={{ cursor: "pointer", "& td": { borderColor: "#d9a3a3", fontWeight: 600 } }}
              >
                {COLONNES.map((c) => (
                  <TableCell key={c.cle} align={c.cle === "solde" ? "right" : "left"}>
                    {cellule(client, c.cle, solde)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {clients.data?.count === 0 && (
          <Box sx={{ p: 2 }}>
            <Typography color="text.secondary">Aucun client ne correspond.</Typography>
          </Box>
        )}
      </TableContainer>
      <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
        <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
          {clients.data ? `${clients.data.count} client${clients.data.count > 1 ? "s" : ""}` : ""}
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
