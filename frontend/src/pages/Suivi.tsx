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

import { listerMagasins } from "../api/magasins";
import { changerEtape, ETATS, listerSuivi, type Etat, type LigneSuivi } from "../api/suivi";
import { Filtres } from "../navigation/Filtres";

const MOIS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"];
const aujourdhui = new Date();
const ANNEES = [0, 1, 2].map((n) => aujourdhui.getFullYear() - n);
// La livraison se fait depuis « Commandes en cours », contre le solde : pas d'ici.
const ETAPES_SAISIES = ETATS.filter((e) => e.valeur !== "livree");

function ChangerEtape({ ligne, onFermer }: { ligne: LigneSuivi; onFermer: () => void }) {
  const queryClient = useQueryClient();
  const [etape, setEtape] = useState<Etat>(ligne.etat === "livree" ? "contact_client" : ligne.etat);
  const [observation, setObservation] = useState("");
  const envoi = useMutation({
    mutationFn: () => changerEtape(ligne.id, etape, observation),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["suivi"] });
      onFermer();
    },
  });
  return (
    <Dialog open onClose={onFermer} fullWidth maxWidth="xs">
      <DialogTitle>Visite {ligne.numero}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <TextField select label="Étape" value={etape} onChange={(e) => setEtape(e.target.value as Etat)}>
            {ETAPES_SAISIES.map((e) => (
              <MenuItem key={e.valeur} value={e.valeur}>
                {e.libelle}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Observation"
            value={observation}
            onChange={(e) => setObservation(e.target.value)}
            multiline
            slotProps={{ htmlInput: { maxLength: 300 } }}
          />
          {envoi.isError && <Alert severity="error">{envoi.error.message}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onFermer}>Annuler</Button>
        <Button variant="contained" disabled={envoi.isPending} onClick={() => envoi.mutate()}>
          Enregistrer
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/** Suivi qualité des lunettes et lentilles commandées : où en est chaque visite. */
export function Suivi({ modifier }: { modifier: boolean }) {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [magasin, setMagasin] = useState("");
  const [etat, setEtat] = useState<Etat | "">("a_commander");
  const [type, setType] = useState<"" | "verre" | "lentille">("");
  const [stock, setStock] = useState<"" | "non" | "oui">("");
  const [mois, setMois] = useState(aujourdhui.getMonth() + 1);
  const [annee, setAnnee] = useState(aujourdhui.getFullYear());
  const [ouverte, setOuverte] = useState<LigneSuivi | null>(null);

  const filtres = { magasin, etat: etat || undefined, type, mois: mois || undefined, annee: annee || undefined };
  const suivi = useQuery({ queryKey: ["suivi", filtres], queryFn: () => listerSuivi(filtres) });
  const lignes = (suivi.data ?? []).filter((l) => stock === "" || l.stockable === (stock === "oui"));

  return (
    <Card>
      <CardContent>
        <Stack spacing={1}>
          <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
            <Typography variant="h6" component="h2" sx={{ flexGrow: 1 }}>
              Suivi des visites
            </Typography>
            <TextField
              select
              size="small"
              label="Magasin"
              value={magasin}
              onChange={(e) => setMagasin(e.target.value)}
              sx={{ minWidth: 200 }}
            >
              <MenuItem value="">Tous</MenuItem>
              {magasins.data?.map((m) => (
                <MenuItem key={m.id} value={m.id}>
                  {m.nom}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
          {suivi.isError && <Alert severity="error">{suivi.error.message}</Alert>}
          <TableContainer sx={{ maxHeight: 460 }}>
            <Table size="small" stickyHeader aria-label="Visites" sx={{ "& td, & th": { whiteSpace: "nowrap" } }}>
              <TableHead>
                <TableRow>
                  {["N° fiche", "N° visite", "Date", "Client", "Péniche", "Code monture", "Référence", "Observation", "État", ""].map(
                    (titre) => (
                      <TableCell key={titre} sx={{ fontWeight: 700, color: "primary.main" }}>
                        {titre}
                      </TableCell>
                    ),
                  )}
                </TableRow>
              </TableHead>
              <TableBody>
                {lignes.map((l) => (
                  <TableRow key={l.id} hover>
                    <TableCell>{l.client?.numero ?? ""}</TableCell>
                    <TableCell>{l.numero}</TableCell>
                    <TableCell>{new Date(l.cree_le).toLocaleDateString("fr-FR")}</TableCell>
                    <TableCell>{l.client?.nom ?? "Client de passage"}</TableCell>
                    <TableCell>{l.peniche ?? ""}</TableCell>
                    <TableCell>{l.monture?.code_barres ?? ""}</TableCell>
                    <TableCell>{l.monture?.reference ?? ""}</TableCell>
                    <TableCell>{l.observation}</TableCell>
                    <TableCell>{l.etat_libelle}</TableCell>
                    <TableCell>
                      {modifier && l.etat !== "livree" && (
                        <Button size="small" onClick={() => setOuverte(l)}>
                          Étape
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          {suivi.isSuccess && lignes.length === 0 && (
            <Typography color="text.secondary">Aucune visite pour ces filtres.</Typography>
          )}
          <Filtres
            libelle="État"
            options={[{ valeur: "" as const, libelle: "Tous" }, ...ETATS]}
            valeur={etat}
            onChange={setEtat}
          />
          <Filtres
            libelle="Type"
            options={[
              { valeur: "" as const, libelle: "Tous" },
              { valeur: "verre" as const, libelle: "Verre" },
              { valeur: "lentille" as const, libelle: "Lentille" },
            ]}
            valeur={type}
            onChange={setType}
          />
          <Filtres
            libelle="Stock"
            options={[
              { valeur: "" as const, libelle: "Tous" },
              { valeur: "non" as const, libelle: "Non stockable" },
              { valeur: "oui" as const, libelle: "Stockable" },
            ]}
            valeur={stock}
            onChange={setStock}
          />
          <Filtres
            libelle="Mois"
            options={[{ valeur: 0, libelle: "Tous" }, ...MOIS.map((m, i) => ({ valeur: i + 1, libelle: m }))]}
            valeur={mois}
            onChange={setMois}
          />
          <Filtres
            libelle="Année"
            options={[{ valeur: 0, libelle: "Tous" }, ...ANNEES.map((a) => ({ valeur: a, libelle: String(a) }))]}
            valeur={annee}
            onChange={setAnnee}
          />
        </Stack>
      </CardContent>
      {ouverte && <ChangerEtape ligne={ouverte} onFermer={() => setOuverte(null)} />}
    </Card>
  );
}
