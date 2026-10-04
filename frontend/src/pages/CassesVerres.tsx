import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { CAUSES_CASSE, listerCasses, listerVisites } from "../api/visites";
import { Filtres } from "../navigation/Filtres";
import { dateHeure, FicheVisite } from "./FicheVisite";

const CAUSES = [{ valeur: "", libelle: "Toutes" }, ...CAUSES_CASSE];

/** Casses de verres : on les déclare depuis la visite, le verre repasse à commander. */
export function CassesVerres({ declarer }: { declarer: boolean }) {
  const [cause, setCause] = useState("");
  const [numero, setNumero] = useState("");
  const [visite, setVisite] = useState<string | null>(null);
  const casses = useQuery({ queryKey: ["casses", cause], queryFn: () => listerCasses(cause) });
  const recherche = useMutation({
    mutationFn: () => listerVisites({ recherche: numero.trim() }),
    onSuccess: (page) => {
      if (page.count === 1) setVisite(page.results[0].id);
    },
  });

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Casses de verres
          </Typography>
          {declarer && (
            <Stack
              component="form"
              direction={{ xs: "column", sm: "row" }}
              spacing={2}
              onSubmit={(e) => {
                e.preventDefault();
                recherche.mutate();
              }}
            >
              <TextField
                size="small"
                label="N° de la visite"
                helperText="Ouvre la visite : choisissez le verre cassé et sa cause."
                value={numero}
                onChange={(e) => setNumero(e.target.value)}
              />
              <Button type="submit" variant="contained" sx={{ alignSelf: "flex-start" }} disabled={!numero.trim()}>
                Déclarer une casse
              </Button>
            </Stack>
          )}
          {recherche.data && recherche.data.count !== 1 && (
            <Alert severity="warning">
              {recherche.data.count === 0
                ? "Aucune visite avec ce numéro."
                : `${recherche.data.count} visites correspondent : donnez le numéro complet.`}
            </Alert>
          )}
          {casses.isError && <Alert severity="error">{casses.error.message}</Alert>}
          {casses.data?.length === 0 && <Typography color="text.secondary">Aucune casse déclarée.</Typography>}
          {casses.data && casses.data.length > 0 && (
            <TableContainer>
              <Table size="small" aria-label="Casses de verres">
                <TableHead>
                  <TableRow>
                    {["Date", "Visite", "Client", "Verre", "Fournisseur", "Cause", "Observation", "Déclarée par"].map((t) => (
                      <TableCell key={t}>{t}</TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {casses.data.map((c) => (
                    <TableRow key={c.id} hover onClick={() => setVisite(c.vente)} sx={{ cursor: "pointer" }}>
                      <TableCell>{dateHeure(c.cree_le)}</TableCell>
                      <TableCell>{c.vente_numero}</TableCell>
                      <TableCell>{c.client ?? "—"}</TableCell>
                      <TableCell>{c.verre}</TableCell>
                      <TableCell>{c.fournisseur}</TableCell>
                      <TableCell>{c.cause_libelle}</TableCell>
                      <TableCell>{c.observation}</TableCell>
                      <TableCell>{c.declaree_par}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
          <Filtres libelle="Cause" options={CAUSES} valeur={cause} onChange={setCause} />
        </Stack>
      </CardContent>
      {visite && <FicheVisite id={visite} casse={declarer} onFermer={() => setVisite(null)} />}
    </Card>
  );
}
