import Print from "@mui/icons-material/Print";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
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
import { formaterTexte } from "../api/monnaie";
import {
  lireStatistique,
  type ColonneStatistique,
  type RapportStatistique,
  type Statistique,
} from "../api/statistiques";
import { imprimer } from "./FactureAchat";
import { dateDocument, echapper, enteteDocument } from "./Factures";

const jourIso = (d: Date) => d.toLocaleDateString("en-CA");
const debutDuMois = () => {
  const d = new Date();
  d.setDate(1);
  return jourIso(d);
};

function cellule(colonne: ColonneStatistique, valeur: string | number | undefined, s: Statistique) {
  if (valeur === undefined || valeur === "") return "";
  switch (colonne.type) {
    case "montant":
      return formaterTexte(String(valeur), { devise: s.devise, decimales: s.decimales });
    case "pourcent":
      return `${Number(valeur).toLocaleString("fr-FR", { maximumFractionDigits: 2 })} %`;
    case "date":
      return dateDocument(String(valeur));
    case "nombre":
      return Number(valeur).toLocaleString("fr-FR");
    default:
      return String(valeur);
  }
}

const aDroite = (colonne: ColonneStatistique) => colonne.type !== "texte" && colonne.type !== "date";

function pageStatistique(s: Statistique, magasin: string) {
  const e = echapper;
  const ligne = (valeurs: Record<string, string | number>, balise: "td" | "th") =>
    `<tr>${s.colonnes
      .map((c) => `<${balise}${aDroite(c) ? ' class="n"' : ""}>${e(cellule(c, valeurs[c.cle], s))}</${balise}>`)
      .join("")}</tr>`;
  return `${enteteDocument(`Statistiques : ${s.titre}`, undefined)}
<p>Du ${dateDocument(s.du)} au ${dateDocument(s.au)} · ${e(magasin)} · ${e(s.devise)}</p>
<table><thead><tr>${s.colonnes.map((c) => `<th>${e(c.libelle)}</th>`).join("")}</tr></thead>
<tbody>${s.lignes.map((l) => ligne(l, "td")).join("")}${s.lignes.length ? ligne({ [s.colonnes[0].cle]: "Total", ...s.totaux }, "th") : ""}</tbody></table>
</body></html>`;
}

/**
 * Statistiques des ventes sur une période : un tableau par sujet (marques, verres, remises,
 * TVA, bénéfice…), avec ses totaux, filtrable par magasin et imprimable.
 */
export function Statistiques({ rapport }: { rapport: RapportStatistique }) {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [du, setDu] = useState(debutDuMois());
  const [au, setAu] = useState(jourIso(new Date()));
  const [magasin, setMagasin] = useState("");
  const [devise, setDevise] = useState("");
  const stat = useQuery({
    queryKey: ["statistiques", rapport, du, au, magasin, devise],
    queryFn: () => lireStatistique(rapport, { du, au, magasin, devise }),
    enabled: Boolean(du && au),
    placeholderData: keepPreviousData,
  });
  const s = stat.data;
  const nomMagasin = magasins.data?.find((m) => m.id === magasin)?.nom ?? "Tous les magasins";

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Statistiques{s ? ` : ${s.titre}` : ""}
          </Typography>
          <Stack direction="row" spacing={2} sx={{ flexWrap: "wrap", rowGap: 2 }}>
            <TextField
              size="small"
              type="date"
              label="Du"
              value={du}
              onChange={(ev) => setDu(ev.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <TextField
              size="small"
              type="date"
              label="Au"
              value={au}
              onChange={(ev) => setAu(ev.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            {(magasins.data?.length ?? 0) > 1 && (
              <TextField
                select
                size="small"
                label="Magasin"
                value={magasin}
                onChange={(ev) => setMagasin(ev.target.value)}
                sx={{ minWidth: 200 }}
              >
                <MenuItem value="">Tous les magasins</MenuItem>
                {magasins.data?.map((m) => (
                  <MenuItem key={m.id} value={m.id}>
                    {m.nom}
                  </MenuItem>
                ))}
              </TextField>
            )}
            {(s?.devises.length ?? 0) > 1 && (
              <TextField
                select
                size="small"
                label="Monnaie"
                value={devise || s!.devise}
                onChange={(ev) => setDevise(ev.target.value)}
              >
                {s!.devises.map((d) => (
                  <MenuItem key={d} value={d}>
                    {d}
                  </MenuItem>
                ))}
              </TextField>
            )}
            {s && (
              <Button startIcon={<Print />} onClick={() => imprimer(pageStatistique(s, nomMagasin))}>
                Imprimer
              </Button>
            )}
          </Stack>
          {stat.isError && <Alert severity="error">{stat.error.message}</Alert>}
          {s && s.lignes.length === 0 && (
            <Typography color="text.secondary">Aucune vente concernée sur la période.</Typography>
          )}
          {s && s.lignes.length > 0 && (
            <TableContainer sx={{ maxHeight: 560 }}>
              <Table stickyHeader size="small" aria-label={s.titre}>
                <TableHead>
                  <TableRow>
                    {s.colonnes.map((c) => (
                      <TableCell key={c.cle} align={aDroite(c) ? "right" : "left"}>
                        {c.libelle}
                      </TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {s.lignes.map((ligne, i) => (
                    <TableRow key={i} hover>
                      {s.colonnes.map((c) => (
                        <TableCell key={c.cle} align={aDroite(c) ? "right" : "left"}>
                          {cellule(c, ligne[c.cle], s)}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                  <TableRow>
                    {s.colonnes.map((c, i) => (
                      <TableCell key={c.cle} align={aDroite(c) ? "right" : "left"} sx={{ fontWeight: "bold" }}>
                        {i === 0 ? "Total" : cellule(c, s.totaux[c.cle], s)}
                      </TableCell>
                    ))}
                  </TableRow>
                </TableBody>
              </Table>
            </TableContainer>
          )}
          {rapport === "benefice" && (
            <Typography variant="body2" color="text.secondary">
              Coût d'un verre commandé : celui de sa réception. Autres articles : prix d'achat net du tarif. Les
              articles sans prix d'achat sont comptés à part.
            </Typography>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
