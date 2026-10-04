import Alert from "@mui/material/Alert";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Collapse from "@mui/material/Collapse";
import IconButton from "@mui/material/IconButton";
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
import ExpandLess from "@mui/icons-material/ExpandLess";
import ExpandMore from "@mui/icons-material/ExpandMore";
import { useQuery } from "@tanstack/react-query";
import { Fragment, useState } from "react";

import { listerMagasins } from "../api/magasins";
import { resteParVendeur } from "../api/visites";
import { dateHeure, FicheVisite, useMontant } from "./FicheVisite";

/** Reste dû sur les commandes en cours, par vendeur ; on déplie pour voir ses commandes. */
export function ResteVendeur() {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = magasinChoisi || magasins.data?.[0]?.id || "";
  const choisi = magasins.data?.find((m) => m.id === magasin);
  const [ouvert, setOuvert] = useState<string | null>(null);
  const [visite, setVisite] = useState<string | null>(null);
  const montant = useMontant();
  const m = (valeur: string | number) => montant(String(valeur), choisi?.pays.devise ?? "", choisi?.code);
  const restes = useQuery({
    queryKey: ["reste-vendeur", magasin],
    queryFn: () => resteParVendeur(magasin),
    enabled: Boolean(magasin),
  });
  const total = (restes.data ?? []).reduce((s, r) => s + Number(r.reste), 0);

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Reste par vendeur
          </Typography>
          <TextField select size="small" label="Magasin" value={magasin} onChange={(e) => setMagasin(e.target.value)} sx={{ maxWidth: 220 }}>
            {magasins.data?.map((mg) => (
              <MenuItem key={mg.id} value={mg.id}>
                {mg.nom}
              </MenuItem>
            ))}
          </TextField>
          {restes.isError && <Alert severity="error">{restes.error.message}</Alert>}
          {restes.data?.length === 0 && <Typography color="text.secondary">Aucune commande en cours avec un reste dû.</Typography>}
          {restes.data && restes.data.length > 0 && (
            <TableContainer>
              <Table size="small" aria-label="Reste par vendeur">
                <TableHead>
                  <TableRow>
                    <TableCell />
                    <TableCell>Vendeur</TableCell>
                    <TableCell align="right">Commandes</TableCell>
                    <TableCell align="right">Total</TableCell>
                    <TableCell align="right">Reste dû</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {restes.data.map((r) => (
                    <Fragment key={r.vendeur}>
                      <TableRow hover>
                        <TableCell padding="checkbox">
                          <IconButton
                            size="small"
                            aria-label={`Commandes de ${r.vendeur_nom}`}
                            aria-expanded={ouvert === r.vendeur}
                            onClick={() => setOuvert(ouvert === r.vendeur ? null : r.vendeur)}
                          >
                            {ouvert === r.vendeur ? <ExpandLess /> : <ExpandMore />}
                          </IconButton>
                        </TableCell>
                        <TableCell>{r.vendeur_nom}</TableCell>
                        <TableCell align="right">{r.nombre}</TableCell>
                        <TableCell align="right">{m(r.total_ttc)}</TableCell>
                        <TableCell align="right">
                          <strong>{m(r.reste)}</strong>
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell colSpan={5} sx={{ py: 0, borderBottom: ouvert === r.vendeur ? undefined : "none" }}>
                          <Collapse in={ouvert === r.vendeur} unmountOnExit>
                            <Table size="small" aria-label={`Commandes non soldées de ${r.vendeur_nom}`}>
                              <TableBody>
                                {r.commandes.map((c) => (
                                  <TableRow key={c.id} hover onClick={() => setVisite(c.id)} sx={{ cursor: "pointer" }}>
                                    <TableCell>{c.numero}</TableCell>
                                    <TableCell>{dateHeure(c.cree_le)}</TableCell>
                                    <TableCell>{c.client ?? "Client de passage"}</TableCell>
                                    <TableCell>{c.telephone}</TableCell>
                                    <TableCell align="right">{m(c.total_ttc)}</TableCell>
                                    <TableCell align="right">{m(c.reste)}</TableCell>
                                  </TableRow>
                                ))}
                              </TableBody>
                            </Table>
                          </Collapse>
                        </TableCell>
                      </TableRow>
                    </Fragment>
                  ))}
                  <TableRow>
                    <TableCell colSpan={4} align="right">
                      <strong>Total dû</strong>
                    </TableCell>
                    <TableCell align="right">
                      <strong>{m(total)}</strong>
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Stack>
      </CardContent>
      {visite && <FicheVisite id={visite} onFermer={() => setVisite(null)} />}
    </Card>
  );
}
