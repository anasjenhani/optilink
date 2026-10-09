import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
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
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  annulerCasse,
  type Casse,
  CAUSES_CASSE,
  type CauseCasse,
  corrigerCasse,
  listerCasses,
  listerVisites,
} from "../api/visites";
import { Filtres } from "../navigation/Filtres";
import { dateHeure, FicheVisite } from "./FicheVisite";

const CAUSES = [{ valeur: "", libelle: "Toutes" }, ...CAUSES_CASSE];

/** Corriger la cause ou l'observation d'une casse, ou l'annuler si elle a été déclarée par erreur. */
function CorrectionCasse({ casse, onFermer }: { casse: Casse; onFermer: () => void }) {
  const queryClient = useQueryClient();
  const [cause, setCause] = useState<CauseCasse>(casse.cause);
  const [observation, setObservation] = useState(casse.observation);
  const [confirmer, setConfirmer] = useState(false);
  const fini = () => {
    for (const cle of ["casses", "visites"]) void queryClient.invalidateQueries({ queryKey: [cle] });
    onFermer();
  };
  const correction = useMutation({
    mutationFn: () => corrigerCasse(casse.id, { cause, observation }),
    onSuccess: fini,
  });
  const annulation = useMutation({ mutationFn: () => annulerCasse(casse.id), onSuccess: fini });
  const erreur = correction.error ?? annulation.error;
  return (
    <Dialog open onClose={onFermer} maxWidth="sm" fullWidth>
      <DialogTitle>
        Casse du verre {casse.verre} ({casse.vente_numero})
      </DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <TextField select label="Cause" value={cause} onChange={(e) => setCause(e.target.value as CauseCasse)}>
            {CAUSES_CASSE.map((c) => (
              <MenuItem key={c.valeur} value={c.valeur}>
                {c.libelle}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Observation"
            value={observation}
            onChange={(e) => setObservation(e.target.value)}
            slotProps={{ htmlInput: { maxLength: 300 } }}
          />
          {confirmer && (
            <Alert severity="warning">
              Annuler cette casse ? Le verre reçu compte de nouveau et la commande n'est plus à recommander. Ce n'est
              possible que si le verre n'a pas encore été recommandé au fournisseur.
            </Alert>
          )}
          {erreur && <Alert severity="error">{erreur.message}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        {confirmer ? (
          <>
            <Button onClick={() => setConfirmer(false)}>Non</Button>
            <Button
              color="error"
              variant="contained"
              disabled={annulation.isPending}
              onClick={() => annulation.mutate()}
            >
              Oui, annuler la casse
            </Button>
          </>
        ) : (
          <>
            <Button color="error" onClick={() => setConfirmer(true)}>
              Annuler la casse
            </Button>
            <Button onClick={onFermer}>Fermer</Button>
            <Button variant="contained" disabled={correction.isPending} onClick={() => correction.mutate()}>
              Enregistrer
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  );
}

/** Casses de verres : on les déclare depuis la visite, le verre repasse à commander. */
export function CassesVerres({ declarer }: { declarer: boolean }) {
  const [cause, setCause] = useState("");
  const [numero, setNumero] = useState("");
  const [visite, setVisite] = useState<string | null>(null);
  const [aCorriger, setACorriger] = useState<Casse | null>(null);
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
                    {["Date", "Visite", "Client", "Verre", "Fournisseur", "Cause", "Observation", "Déclarée par"].map(
                      (t) => (
                        <TableCell key={t}>{t}</TableCell>
                      ),
                    )}
                    {declarer && <TableCell />}
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
                      {declarer && (
                        <TableCell>
                          <Button
                            size="small"
                            onClick={(e) => {
                              e.stopPropagation();
                              setACorriger(c);
                            }}
                          >
                            Modifier
                          </Button>
                        </TableCell>
                      )}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
          <Filtres libelle="Cause" options={CAUSES} valeur={cause} onChange={setCause} />
        </Stack>
      </CardContent>
      {aCorriger && <CorrectionCasse casse={aCorriger} onFermer={() => setACorriger(null)} />}
      {visite && <FicheVisite id={visite} casse={declarer} onFermer={() => setVisite(null)} />}
    </Card>
  );
}
