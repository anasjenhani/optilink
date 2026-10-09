import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import FormControlLabel from "@mui/material/FormControlLabel";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemText from "@mui/material/ListItemText";
import Stack from "@mui/material/Stack";
import Tab from "@mui/material/Tab";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Tabs from "@mui/material/Tabs";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { reglerCommande, type ModePaiement, type Piece } from "../api/caisse";
import { chercherClients, nomClient, type Client } from "../api/clients";
import {
  changerCheque,
  declarerImpaye,
  listerChequesClients,
  listerListeNoire,
  listerVentesDues,
  mettreEnListeNoire,
  retirerDeListeNoire,
  type PaiementSuivi,
} from "../api/creditClients";
import { formaterTexte } from "../api/monnaie";
import { ChampsPiece, ChoixMode, piece } from "./ChampsPaiement";
import { dateCourte } from "./FactureAchat";

export type OngletCredit = "ventes" | "impayes" | "portefeuille" | "cheques" | "liste-noire";
type Droits = { regler: boolean; gerer: boolean };

const aujourdhui = () => new Date().toLocaleDateString("sv-SE");
const montant = (valeur: string, devise: string) => formaterTexte(valeur, { devise, decimales: 3 });

/**
 * Crédit client et impayés : ventes remises sans être soldées, chèques et traites à remettre
 * à la banque, chèques revenus impayés, changements de chèque et liste noire.
 */
export function CreditClients({ droits, ongletInitial = "ventes" }: { droits: Droits; ongletInitial?: OngletCredit }) {
  const [onglet, setOnglet] = useState<OngletCredit>(ongletInitial);
  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Crédit client et impayés
          </Typography>
          <Tabs value={onglet} onChange={(_, valeur: OngletCredit) => setOnglet(valeur)} variant="scrollable">
            <Tab value="ventes" label="Ventes à crédit" />
            <Tab value="impayes" label="Chèques impayés" />
            <Tab value="portefeuille" label="Échéancier chèques" />
            <Tab value="cheques" label="Changement chèques" />
            {droits.gerer && <Tab value="liste-noire" label="Liste noire" />}
          </Tabs>
          {onglet === "ventes" && <VentesDues droits={droits} />}
          {onglet !== "ventes" && onglet !== "liste-noire" && <Cheques vue={onglet} droits={droits} />}
          {onglet === "liste-noire" && <ListeNoire />}
        </Stack>
      </CardContent>
    </Card>
  );
}

function Reglement({
  vente,
  numero,
  reste,
  devise,
  onFermer,
}: {
  vente: string;
  numero: string;
  reste: string;
  devise: string;
  onFermer: () => void;
}) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<ModePaiement>("especes");
  const [valeur, setValeur] = useState(reste);
  const [pieceSaisie, setPiece] = useState<Piece>({});
  const reglement = useMutation({
    mutationFn: () => reglerCommande(vente, { mode, montant: valeur.replace(",", "."), ...piece(mode, pieceSaisie) }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["credit-clients"] });
      onFermer();
    },
  });
  return (
    <Dialog open onClose={onFermer} fullWidth maxWidth="sm">
      <DialogTitle>
        Régler la visite {numero} · reste {montant(reste, devise)}
      </DialogTitle>
      <DialogContent>
        <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap", pt: 1 }}>
          <TextField
            size="small"
            label="Montant"
            value={valeur}
            onChange={(e) => setValeur(e.target.value)}
            sx={{ width: 140 }}
          />
          <ChoixMode valeur={mode} onChange={setMode} />
          <ChampsPiece mode={mode} valeur={pieceSaisie} onChange={setPiece} />
        </Stack>
        {reglement.isError && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {reglement.error.message}
          </Alert>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onFermer}>Annuler</Button>
        <Button
          variant="contained"
          disabled={reglement.isPending || !Number(valeur)}
          onClick={() => reglement.mutate()}
        >
          Encaisser
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function VentesDues({ droits }: { droits: Droits }) {
  const liste = useQuery({ queryKey: ["credit-clients", "ventes"], queryFn: listerVentesDues });
  const [aRegler, setARegler] = useState<{ id: string; numero: string; reste: string; devise: string } | null>(null);
  const total = (liste.data ?? []).reduce((s, v) => s + Number(v.reste_a_payer), 0);
  return (
    <Stack spacing={2}>
      {liste.isError && <Alert severity="error">{liste.error.message}</Alert>}
      {liste.data?.length === 0 && <Typography color="text.secondary">Aucune vente à crédit ni impayé.</Typography>}
      {liste.data && liste.data.length > 0 && (
        <>
          <Typography>
            {liste.data.length} visite(s), reste dû : <strong>{montant(total.toFixed(3), liste.data[0].devise)}</strong>
          </Typography>
          <Table size="small" aria-label="Ventes à crédit">
            <TableHead>
              <TableRow>
                <TableCell>Visite</TableCell>
                <TableCell>Client</TableCell>
                <TableCell>Magasin</TableCell>
                <TableCell align="right">Total</TableCell>
                <TableCell align="right">Reste dû</TableCell>
                <TableCell>À régler le</TableCell>
                {droits.regler && <TableCell />}
              </TableRow>
            </TableHead>
            <TableBody>
              {liste.data.map((v) => (
                <TableRow key={v.id}>
                  <TableCell>
                    {v.numero}
                    <Typography variant="caption" sx={{ display: "block" }} color="text.secondary">
                      {dateCourte(v.cree_le)}
                      {v.impayes > 0 && " · chèque impayé"}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {v.client ?? "—"}
                    {v.client_telephone && (
                      <Typography variant="caption" sx={{ display: "block" }} color="text.secondary">
                        {v.client_telephone}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>{v.magasin}</TableCell>
                  <TableCell align="right">{montant(v.total_ttc, v.devise)}</TableCell>
                  <TableCell align="right">{montant(v.reste_a_payer, v.devise)}</TableCell>
                  <TableCell>
                    {v.credit_echeance ? (
                      v.en_retard ? (
                        <Chip size="small" color="error" label={dateCourte(v.credit_echeance)} />
                      ) : (
                        dateCourte(v.credit_echeance)
                      )
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  {droits.regler && (
                    <TableCell>
                      <Button
                        size="small"
                        onClick={() =>
                          setARegler({ id: v.id, numero: v.numero, reste: v.reste_a_payer, devise: v.devise })
                        }
                      >
                        Régler
                      </Button>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </>
      )}
      {aRegler && (
        <Reglement
          vente={aRegler.id}
          numero={aRegler.numero}
          reste={aRegler.reste}
          devise={aRegler.devise}
          onFermer={() => setARegler(null)}
        />
      )}
    </Stack>
  );
}

function Impaye({ paiement, onFermer }: { paiement: PaiementSuivi; onFermer: () => void }) {
  const queryClient = useQueryClient();
  const [le, setLe] = useState(aujourdhui());
  const [motif, setMotif] = useState("");
  const [listeNoire, setListeNoire] = useState(true);
  const declaration = useMutation({
    mutationFn: () => declarerImpaye(paiement.id, { le, motif, liste_noire: listeNoire }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["credit-clients"] });
      onFermer();
    },
  });
  return (
    <Dialog open onClose={onFermer} fullWidth maxWidth="sm">
      <DialogTitle>
        {paiement.mode_libelle} n° {paiement.reference} impayé · {montant(paiement.montant, paiement.devise)}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <Typography variant="body2" color="text.secondary">
            Le montant redevient dû par {paiement.client ?? "le client"} sur la visite {paiement.vente_numero}.
          </Typography>
          <Stack direction="row" spacing={2}>
            <TextField
              size="small"
              type="date"
              label="Rejeté le"
              value={le}
              onChange={(e) => setLe(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <TextField
              size="small"
              label="Motif du rejet"
              placeholder="Sans provision, signature…"
              value={motif}
              onChange={(e) => setMotif(e.target.value)}
              sx={{ flexGrow: 1 }}
            />
          </Stack>
          <FormControlLabel
            control={<Checkbox checked={listeNoire} onChange={(e) => setListeNoire(e.target.checked)} />}
            label="Mettre le client en liste noire (plus de chèque, de traite ni de crédit)"
          />
          {declaration.isError && <Alert severity="error">{declaration.error.message}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onFermer}>Annuler</Button>
        <Button
          variant="contained"
          color="error"
          disabled={declaration.isPending || !motif.trim()}
          onClick={() => declaration.mutate()}
        >
          Déclarer impayé
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function Changement({ paiement, onFermer }: { paiement: PaiementSuivi; onFermer: () => void }) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<ModePaiement>("especes");
  const [pieceSaisie, setPiece] = useState<Piece>({});
  const changement = useMutation({
    mutationFn: () => changerCheque(paiement.id, { mode, ...piece(mode, pieceSaisie) }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["credit-clients"] });
      onFermer();
    },
  });
  return (
    <Dialog open onClose={onFermer} fullWidth maxWidth="sm">
      <DialogTitle>
        Changer le {paiement.mode_libelle.toLowerCase()} n° {paiement.reference} ·{" "}
        {montant(paiement.montant, paiement.devise)}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <Typography variant="body2" color="text.secondary">
            Le client reprend sa pièce et règle le même montant autrement.
          </Typography>
          <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap" }}>
            <ChoixMode valeur={mode} onChange={setMode} label="Nouveau paiement" />
            <ChampsPiece mode={mode} valeur={pieceSaisie} onChange={setPiece} />
          </Stack>
          {changement.isError && <Alert severity="error">{changement.error.message}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onFermer}>Annuler</Button>
        <Button variant="contained" disabled={changement.isPending} onClick={() => changement.mutate()}>
          Enregistrer le changement
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function Cheques({ vue, droits }: { vue: "impayes" | "portefeuille" | "cheques"; droits: Droits }) {
  const liste = useQuery({ queryKey: ["credit-clients", vue], queryFn: () => listerChequesClients(vue) });
  const [impaye, setImpaye] = useState<PaiementSuivi | null>(null);
  const [change, setChange] = useState<PaiementSuivi | null>(null);
  const [aRegler, setARegler] = useState<PaiementSuivi | null>(null);
  const textes = {
    impayes: "Chèques et traites revenus impayés : leur montant est dû par le client.",
    portefeuille: "Chèques et traites des clients à remettre à la banque, par date d'échéance.",
    cheques: "Chèques et traites reçus des clients : un client peut reprendre le sien et payer autrement.",
  };
  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        {textes[vue]}
      </Typography>
      {liste.isError && <Alert severity="error">{liste.error.message}</Alert>}
      {liste.data?.length === 0 && <Typography color="text.secondary">Aucun chèque ni traite.</Typography>}
      {liste.data && liste.data.length > 0 && (
        <Table size="small" aria-label="Chèques et traites">
          <TableHead>
            <TableRow>
              <TableCell>{vue === "impayes" ? "Rejeté le" : "Échéance"}</TableCell>
              <TableCell>Pièce</TableCell>
              <TableCell>Client</TableCell>
              <TableCell>Visite</TableCell>
              <TableCell align="right">Montant</TableCell>
              <TableCell>Statut</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {liste.data.map((p) => (
              <TableRow key={p.id}>
                <TableCell>
                  {vue === "impayes" ? dateCourte(p.impaye_le ?? "") : p.echeance ? dateCourte(p.echeance) : "—"}
                </TableCell>
                <TableCell>
                  {p.mode_libelle} n° {p.reference}
                  {p.banque && (
                    <Typography variant="caption" sx={{ display: "block" }} color="text.secondary">
                      {p.banque}
                    </Typography>
                  )}
                </TableCell>
                <TableCell>
                  {p.client ?? "—"}
                  {p.client_telephone && (
                    <Typography variant="caption" sx={{ display: "block" }} color="text.secondary">
                      {p.client_telephone}
                    </Typography>
                  )}
                </TableCell>
                <TableCell>{p.vente_numero}</TableCell>
                <TableCell align="right">{montant(p.montant, p.devise)}</TableCell>
                <TableCell>
                  {p.statut_libelle}
                  {p.motif_impaye && ` · ${p.motif_impaye}`}
                  {p.statut === "impaye" && Number(p.vente_reste) <= 0 && " · régularisé"}
                </TableCell>
                <TableCell>
                  <Stack direction="row" spacing={1}>
                    {droits.gerer && p.statut === "encaisse" && (
                      <Button size="small" color="error" onClick={() => setImpaye(p)}>
                        Impayé
                      </Button>
                    )}
                    {droits.gerer &&
                      p.statut !== "remplace" &&
                      (Number(p.vente_reste) > 0 || p.statut === "encaisse") && (
                        <Button size="small" onClick={() => setChange(p)}>
                          Changer
                        </Button>
                      )}
                    {droits.regler && p.statut === "impaye" && Number(p.vente_reste) > 0 && (
                      <Button size="small" onClick={() => setARegler(p)}>
                        Régler
                      </Button>
                    )}
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      {impaye && <Impaye paiement={impaye} onFermer={() => setImpaye(null)} />}
      {change && <Changement paiement={change} onFermer={() => setChange(null)} />}
      {aRegler && (
        <Reglement
          vente={aRegler.vente}
          numero={aRegler.vente_numero}
          reste={aRegler.vente_reste}
          devise={aRegler.devise}
          onFermer={() => setARegler(null)}
        />
      )}
    </Stack>
  );
}

function ListeNoire() {
  const queryClient = useQueryClient();
  const liste = useQuery({ queryKey: ["credit-clients", "liste-noire"], queryFn: listerListeNoire });
  const [recherche, setRecherche] = useState("");
  const [client, setClient] = useState<Client | null>(null);
  const [motif, setMotif] = useState("");
  const clients = useQuery({
    queryKey: ["clients", recherche],
    queryFn: () => chercherClients(recherche),
    enabled: !client && recherche.trim().length >= 2,
  });
  const rafraichir = () => void queryClient.invalidateQueries({ queryKey: ["credit-clients", "liste-noire"] });
  const ajout = useMutation({
    mutationFn: () => mettreEnListeNoire(client!.id, motif),
    onSuccess: () => {
      setClient(null);
      setRecherche("");
      setMotif("");
      rafraichir();
    },
  });
  const retrait = useMutation({ mutationFn: retirerDeListeNoire, onSuccess: rafraichir });
  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        Un client en liste noire ne paie plus par chèque ni par traite, et n'a plus de crédit. Un chèque déclaré impayé
        l'y met d'office.
      </Typography>
      <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap", alignItems: "center" }}>
        {client ? (
          <>
            <Typography>{nomClient(client)}</Typography>
            <Button size="small" onClick={() => setClient(null)}>
              Changer
            </Button>
          </>
        ) : (
          <TextField
            size="small"
            label="Ajouter un client (nom, téléphone)"
            value={recherche}
            onChange={(e) => setRecherche(e.target.value)}
            sx={{ minWidth: 280 }}
          />
        )}
        <TextField size="small" label="Motif" value={motif} onChange={(e) => setMotif(e.target.value)} />
        <Button
          variant="contained"
          disabled={!client || !motif.trim() || ajout.isPending}
          onClick={() => ajout.mutate()}
        >
          Mettre en liste noire
        </Button>
      </Stack>
      {!client && clients.data && (
        <List dense aria-label="Clients trouvés" sx={{ maxHeight: 200, overflow: "auto" }}>
          {clients.data.map((c) => (
            <ListItemButton key={c.id} onClick={() => setClient(c)}>
              <ListItemText primary={nomClient(c)} secondary={c.telephone} />
            </ListItemButton>
          ))}
        </List>
      )}
      {ajout.isError && <Alert severity="error">{ajout.error.message}</Alert>}
      {retrait.isError && <Alert severity="error">{retrait.error.message}</Alert>}
      {liste.data?.length === 0 && <Typography color="text.secondary">Aucun client en liste noire.</Typography>}
      {liste.data && liste.data.length > 0 && (
        <Table size="small" aria-label="Liste noire">
          <TableHead>
            <TableRow>
              <TableCell>Client</TableCell>
              <TableCell>Téléphone</TableCell>
              <TableCell>Motif</TableCell>
              <TableCell>Depuis</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {liste.data.map((c) => (
              <TableRow key={c.id}>
                <TableCell>
                  {c.nom} · fiche n° {c.numero}
                </TableCell>
                <TableCell>{c.telephone || "—"}</TableCell>
                <TableCell>{c.motif_liste_noire}</TableCell>
                <TableCell>{c.liste_noire_le ? dateCourte(c.liste_noire_le) : "—"}</TableCell>
                <TableCell>
                  <Button size="small" disabled={retrait.isPending} onClick={() => retrait.mutate(c.id)}>
                    Retirer
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Stack>
  );
}
