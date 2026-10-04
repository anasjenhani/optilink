import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import GlobalStyles from "@mui/material/GlobalStyles";
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
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listerMagasins } from "../api/magasins";
import { listerRecus, type Recu } from "../api/visites";
import { Filtres } from "../navigation/Filtres";
import { dateHeure, useMontant } from "./FicheVisite";

const MODES = [
  { valeur: "", libelle: "Tous" },
  { valeur: "especes", libelle: "Espèces" },
  { valeur: "carte", libelle: "Carte bancaire" },
  { valeur: "cheque", libelle: "Chèque" },
];

const aujourdhui = () => new Date().toLocaleDateString("sv-SE");

// À l'impression, seul le reçu sort, à la largeur d'un ticket de caisse (80 mm).
const IMPRESSION = (
  <GlobalStyles
    styles={{
      "@media print": {
        "body *": { visibility: "hidden" },
        "#recu-a-imprimer, #recu-a-imprimer *": { visibility: "visible" },
        "#recu-a-imprimer": { position: "absolute", left: 0, top: 0, width: "72mm", padding: 0 },
      },
    }}
  />
);

/** Reçu d'un règlement, au format ticket. */
export function TicketRecu({ recu }: { recu: Recu }) {
  const montant = useMontant();
  const m = (valeur: string) => montant(valeur, recu.devise);
  const ligne = (libelle: string, valeur: string, fort = false) => (
    <Stack direction="row" spacing={1} sx={{ justifyContent: "space-between", fontWeight: fort ? 700 : 400 }}>
      <span>{libelle}</span>
      <span>{valeur}</span>
    </Stack>
  );
  return (
    <Box id="recu-a-imprimer" sx={{ fontFamily: "monospace", fontSize: 13, maxWidth: 320, mx: "auto" }}>
      <Stack spacing={0.25} sx={{ textAlign: "center", mb: 1 }}>
        <strong>{recu.magasin.societe}</strong>
        <span>{recu.magasin.nom}</span>
        {recu.magasin.adresse && <span>{recu.magasin.adresse}</span>}
        {recu.magasin.telephone && <span>Tél. {recu.magasin.telephone}</span>}
        {recu.magasin.matricule_fiscal && <span>MF {recu.magasin.matricule_fiscal}</span>}
      </Stack>
      <Box sx={{ borderTop: "1px dashed", borderBottom: "1px dashed", py: 0.5, my: 0.5, textAlign: "center" }}>
        <strong>REÇU DE RÈGLEMENT</strong>
        <div>Duplicata</div>
      </Box>
      {ligne("Visite", recu.vente_numero)}
      {ligne("Date", dateHeure(recu.recu_le))}
      {recu.client && ligne("Client", recu.client.nom)}
      {recu.client && ligne("Fiche n°", String(recu.client.numero))}
      <Box sx={{ borderTop: "1px dashed", my: 0.5 }} />
      {ligne("Total visite", m(recu.total_ttc))}
      {Number(recu.deja_regle) > 0 && ligne("Déjà réglé", m(recu.deja_regle))}
      {ligne(`Reçu (${recu.mode_libelle})`, m(recu.montant), true)}
      {ligne("Reste à payer", m(recu.reste_apres), true)}
      <Box sx={{ borderTop: "1px dashed", my: 0.5 }} />
      {recu.recu_par && <div>Encaissé par {recu.recu_par}</div>}
      <div style={{ textAlign: "center", marginTop: 8 }}>Merci de votre visite</div>
    </Box>
  );
}

/** Reçus des règlements, par jour ; chacun peut être réimprimé. */
export function Recus() {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = magasinChoisi || magasins.data?.[0]?.id || "";
  const [du, setDu] = useState(aujourdhui());
  const [au, setAu] = useState(aujourdhui());
  const [mode, setMode] = useState("");
  const [ouvert, setOuvert] = useState<Recu | null>(null);
  const montant = useMontant();
  const recus = useQuery({
    queryKey: ["recus", magasin, du, au, mode],
    queryFn: () => listerRecus({ magasin, du, au, mode }),
    enabled: Boolean(magasin),
  });
  const total = (recus.data ?? []).reduce((s, r) => s + Number(r.montant), 0);
  const devise = recus.data?.[0]?.devise ?? magasins.data?.find((m) => m.id === magasin)?.pays.devise ?? "";

  return (
    <Card>
      {IMPRESSION}
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Liste des reçus
          </Typography>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField select size="small" label="Magasin" value={magasin} onChange={(e) => setMagasin(e.target.value)} sx={{ minWidth: 180 }}>
              {magasins.data?.map((m) => (
                <MenuItem key={m.id} value={m.id}>
                  {m.nom}
                </MenuItem>
              ))}
            </TextField>
            <TextField size="small" type="date" label="Du" value={du} onChange={(e) => setDu(e.target.value)} slotProps={{ inputLabel: { shrink: true } }} />
            <TextField size="small" type="date" label="Au" value={au} onChange={(e) => setAu(e.target.value)} slotProps={{ inputLabel: { shrink: true } }} />
          </Stack>
          {recus.isError && <Alert severity="error">{recus.error.message}</Alert>}
          {recus.data && (
            <Typography variant="body2" color="text.secondary">
              {recus.data.length} reçu{recus.data.length > 1 ? "s" : ""} · {montant(String(total), devise)}
            </Typography>
          )}
          {recus.data && recus.data.length > 0 && (
            <TableContainer>
              <Table size="small" aria-label="Reçus">
                <TableHead>
                  <TableRow>
                    {["Date", "Visite", "Client", "Mode", "Montant", "Encaissé par", ""].map((t, i) => (
                      <TableCell key={i} align={t === "Montant" ? "right" : "left"}>
                        {t}
                      </TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {recus.data.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell>{dateHeure(r.recu_le)}</TableCell>
                      <TableCell>{r.vente_numero}</TableCell>
                      <TableCell>{r.client?.nom ?? "Client de passage"}</TableCell>
                      <TableCell>{r.mode_libelle}</TableCell>
                      <TableCell align="right">{montant(r.montant, r.devise)}</TableCell>
                      <TableCell>{r.recu_par}</TableCell>
                      <TableCell>
                        <Button size="small" onClick={() => setOuvert(r)}>
                          Réimprimer
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
          <Filtres libelle="Mode de paiement" options={MODES} valeur={mode} onChange={setMode} />
        </Stack>
      </CardContent>
      {ouvert && (
        <Dialog open onClose={() => setOuvert(null)} aria-labelledby="titre-recu">
          <DialogTitle id="titre-recu">Reçu · {ouvert.vente_numero}</DialogTitle>
          <DialogContent>
            <TicketRecu recu={ouvert} />
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setOuvert(null)}>Fermer</Button>
            <Button variant="contained" onClick={() => window.print()}>
              Imprimer
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </Card>
  );
}
