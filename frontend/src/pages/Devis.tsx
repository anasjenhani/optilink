import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import Checkbox from "@mui/material/Checkbox";
import FormControlLabel from "@mui/material/FormControlLabel";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import IconButton from "@mui/material/IconButton";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemText from "@mui/material/ListItemText";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Tab from "@mui/material/Tab";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Tabs from "@mui/material/Tabs";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { chercherArticles, type Article, type ModePaiement } from "../api/caisse";
import { chercherClients, listerPrescriptions, type Client } from "../api/clients";
import {
  accepterDevis,
  chercherDevis,
  encaisserDevis,
  etablirDevis,
  lireDevis,
  listerDevis,
  refuserDevis,
  type Devis as DevisType,
  type FiltresDevis,
  type Oeil,
  type StatutDevis,
} from "../api/devis";
import { listerMagasins } from "../api/magasins";
import { enUnites, formater, formaterTexte, type Monnaie } from "../api/monnaie";
import { useApaise } from "./RechercheClients";

export type DroitsDevis = {
  remise: boolean;
  voirOrdonnances: boolean;
  changerStatut: boolean;
  encaisser: boolean;
  /** Consulter les devis du périmètre : liste de tous les devis et détail d'un devis. */
  consulter: boolean;
};

type Ligne = { cle: number; article: Article; quantite: number; remise: string; oeil: Oeil };

const STATUTS: Record<StatutDevis, { libelle: string; couleur: "default" | "info" | "success" | "error" }> = {
  en_cours: { libelle: "En cours", couleur: "info" },
  accepte: { libelle: "Accepté", couleur: "success" },
  refuse: { libelle: "Refusé", couleur: "error" },
  encaisse: { libelle: "Encaissé", couleur: "default" },
};

const MODES: { valeur: ModePaiement; libelle: string }[] = [
  { valeur: "carte", libelle: "Carte bancaire" },
  { valeur: "especes", libelle: "Espèces" },
  { valeur: "cheque", libelle: "Chèque" },
];

const dateCourte = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString("fr-FR");

/** Date du jour au format AAAA-MM-JJ, heure locale, pour comparer aux dates de validité. */
function aujourdHui() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Statut affiché : un devis ni encaissé ni refusé dont la validité est passée est « Expiré ». */
function statutAffiche(devis: DevisType) {
  const expire = devis.valable_jusqu_au < aujourdHui();
  return expire && !devis.vente && devis.statut !== "refuse"
    ? { libelle: "Expiré", couleur: "default" as const }
    : STATUTS[devis.statut];
}

function ChipStatut({ devis }: { devis: DevisType }) {
  const statut = statutAffiche(devis);
  return <Chip size="small" label={statut.libelle} color={statut.couleur} />;
}

const OEILS: Record<Oeil, string> = { "": "", od: "Droit", og: "Gauche" };

/** Détail d'un devis lu sur le serveur : lignes, totaux et statut. */
function DetailDevis({ id, decimales, onFerme }: { id: string; decimales: number; onFerme: () => void }) {
  const devis = useQuery({ queryKey: ["devis", "detail", id], queryFn: () => lireDevis(id) });
  const d = devis.data;
  const m = (montant?: string) => (montant == null ? "" : formaterTexte(montant, { devise: d!.devise, decimales }));
  return (
    <Dialog open onClose={onFerme} maxWidth="md" fullWidth>
      <DialogTitle>{d ? `Devis ${d.numero}` : "Devis"}</DialogTitle>
      <DialogContent>
        {devis.isError && <Alert severity="error">{devis.error.message}</Alert>}
        {d && (
          <Stack spacing={2}>
            <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
              <ChipStatut devis={d} />
              <Typography>
                {[
                  `Client : ${d.client.nom}`,
                  d.magasin && `Magasin ${d.magasin}`,
                  d.cree_le && `établi le ${new Date(d.cree_le).toLocaleDateString("fr-FR")}`,
                  d.etabli_par && `par ${d.etabli_par}`,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </Typography>
            </Stack>
            <Typography color="text.secondary">
              {d.vente ? `Encaissé : ticket ${d.vente}` : `Valable jusqu'au ${dateCourte(d.valable_jusqu_au)}`}
              {d.prescription &&
                ` · Ordonnance ${d.prescription.type === "lentilles" ? "lentilles" : "lunettes"} du ${dateCourte(d.prescription.date_prescription)}`}
            </Typography>
            <Table size="small" aria-label="Détail des lignes">
              <TableHead>
                <TableRow>
                  <TableCell>Article</TableCell>
                  <TableCell>Œil</TableCell>
                  <TableCell align="right">Qté</TableCell>
                  <TableCell align="right">Prix unitaire TTC</TableCell>
                  <TableCell align="right">Remise %</TableCell>
                  <TableCell align="right">TVA %</TableCell>
                  <TableCell align="right">Total TTC</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {d.lignes.map((l, i) => (
                  <TableRow key={i}>
                    <TableCell>{l.libelle}</TableCell>
                    <TableCell>{OEILS[l.oeil]}</TableCell>
                    <TableCell align="right">{l.quantite}</TableCell>
                    <TableCell align="right">{m(l.prix_unitaire_ttc)}</TableCell>
                    <TableCell align="right">{Number(l.remise_pct) ? Number(l.remise_pct) : ""}</TableCell>
                    <TableCell align="right">{l.taux_tva == null ? "" : Number(l.taux_tva)}</TableCell>
                    <TableCell align="right">{m(l.total_ttc)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Typography>
              Total HT {m(d.total_ht)} · TVA {m(d.total_tva)} · <strong>Total TTC {m(d.total_ttc)}</strong>
            </Typography>
            {d.remarques && <Typography color="text.secondary">Remarques : {d.remarques}</Typography>}
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onFerme}>Fermer</Button>
      </DialogActions>
    </Dialog>
  );
}

/** Tous les devis du périmètre, filtrés par n° ou statut ; un clic ouvre le détail. */
function ListeDevis({ decimales, onDetail }: { decimales: number; onDetail: (id: string) => void }) {
  const [filtres, setFiltres] = useState<FiltresDevis>({});
  const [page, setPage] = useState(1);
  const recherche = useApaise(filtres);
  const devis = useQuery({
    queryKey: ["devis", "liste", recherche, page],
    queryFn: () => chercherDevis(recherche, page),
    placeholderData: keepPreviousData,
  });
  const pages = Math.max(1, Math.ceil((devis.data?.count ?? 0) / 50));
  const filtrer = (changement: FiltresDevis) => {
    setFiltres((f) => ({ ...f, ...changement }));
    setPage(1);
  };
  return (
    <Stack spacing={1}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <TextField
          size="small"
          label="N° de devis"
          helperText="Numéro complet, ex. T01-D2026-000001"
          value={filtres.numero ?? ""}
          onChange={(e) => filtrer({ numero: e.target.value })}
        />
        <TextField
          select
          size="small"
          label="Statut"
          value={filtres.statut ?? ""}
          onChange={(e) => filtrer({ statut: e.target.value as StatutDevis | "" })}
          sx={{ minWidth: 160 }}
        >
          <MenuItem value="">Tous</MenuItem>
          {Object.entries(STATUTS).map(([valeur, s]) => (
            <MenuItem key={valeur} value={valeur}>
              {s.libelle}
            </MenuItem>
          ))}
        </TextField>
      </Stack>
      {devis.isError && <Alert severity="error">{devis.error.message}</Alert>}
      <TableContainer>
        <Table size="small" aria-label="Liste des devis">
          <TableHead>
            <TableRow>
              <TableCell>N°</TableCell>
              <TableCell>Date</TableCell>
              <TableCell>Client</TableCell>
              <TableCell>Magasin</TableCell>
              <TableCell align="right">Total TTC</TableCell>
              <TableCell>Validité</TableCell>
              <TableCell>Statut</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {devis.data?.results.map((d) => (
              <TableRow key={d.id} hover onClick={() => onDetail(d.id)} sx={{ cursor: "pointer" }}>
                <TableCell>{d.numero}</TableCell>
                <TableCell>{d.cree_le ? new Date(d.cree_le).toLocaleDateString("fr-FR") : ""}</TableCell>
                <TableCell>{d.client.nom}</TableCell>
                <TableCell>{d.magasin}</TableCell>
                <TableCell align="right">{formaterTexte(d.total_ttc, { devise: d.devise, decimales })}</TableCell>
                <TableCell>{d.vente ? `Ticket ${d.vente}` : dateCourte(d.valable_jusqu_au)}</TableCell>
                <TableCell>
                  <ChipStatut devis={d} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {devis.data?.count === 0 && (
          <Box sx={{ p: 2 }}>
            <Typography color="text.secondary">Aucun devis.</Typography>
          </Box>
        )}
      </TableContainer>
      <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
        <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
          {devis.data ? `${devis.data.count} devis` : ""}
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

/** Verres et lentilles se proposent œil par œil. */
const parOeil = (article: Article) => article.famille === "verre" || article.famille === "lentille";

/**
 * Devis d'équipement d'un client : établi au tarif du jour, figé jusqu'à sa date de validité,
 * puis accepté ou refusé, et encaissé au prix du devis.
 */
export function Devis({ droits }: { droits: DroitsDevis }) {
  const queryClient = useQueryClient();
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = magasinChoisi || magasins.data?.[0]?.id || "";
  const pays = magasins.data?.find((m) => m.id === magasin)?.pays;
  const monnaie: Monnaie = { devise: pays?.devise ?? "TND", decimales: pays?.decimales ?? 3 };

  const [rechercheClient, setRechercheClient] = useState("");
  const [client, setClient] = useState<Client | null>(null);
  const [prescription, setPrescription] = useState("");
  const [recherche, setRecherche] = useState("");
  const [lignes, setLignes] = useState<Ligne[]>([]);
  const [mode, setMode] = useState<ModePaiement>("carte");
  // Devis avec verres à commander : acompte à l'encaissement, solde à la livraison.
  const [enCommande, setEnCommande] = useState(false);
  const [acompte, setAcompte] = useState("");
  const [peniche, setPeniche] = useState("");
  const [message, setMessage] = useState("");
  const [onglet, setOnglet] = useState<"etablir" | "liste">("etablir");
  const [detail, setDetail] = useState<string | null>(null);

  const clients = useQuery({
    queryKey: ["clients", rechercheClient],
    queryFn: () => chercherClients(rechercheClient),
    enabled: !client && rechercheClient.trim().length >= 2,
  });
  const ordonnances = useQuery({
    queryKey: ["prescriptions", client?.id],
    queryFn: () => listerPrescriptions(client!.id),
    enabled: Boolean(client) && droits.voirOrdonnances,
  });
  const devisClient = useQuery({
    queryKey: ["devis", client?.id],
    queryFn: () => listerDevis(client!.id),
    enabled: Boolean(client),
  });
  const articles = useQuery({
    queryKey: ["articles", magasin, recherche],
    queryFn: () => chercherArticles(magasin, recherche),
    enabled: Boolean(magasin) && recherche.trim().length >= 2,
  });

  const total = lignes.reduce(
    (somme, l) =>
      somme +
      Math.round(
        enUnites(l.article.prix_vente_ttc, monnaie.decimales) * l.quantite * (1 - Number(l.remise || 0) / 100),
      ),
    0,
  );

  const rafraichir = () => queryClient.invalidateQueries({ queryKey: ["devis", client?.id] });
  const creation = useMutation({
    mutationFn: () =>
      etablirDevis({
        magasin,
        client: client!.id,
        prescription: prescription || undefined,
        lignes: lignes.map((l) => ({
          article: l.article.id,
          quantite: l.quantite,
          ...(Number(l.remise) > 0 ? { remise_pct: l.remise } : {}),
          ...(l.oeil ? { oeil: l.oeil } : {}),
        })),
      }),
    onSuccess: (devis) => {
      setMessage(`Devis ${devis.numero} établi, valable jusqu'au ${dateCourte(devis.valable_jusqu_au)}.`);
      setLignes([]);
      setPrescription("");
      void rafraichir();
    },
  });
  const action = useMutation({
    mutationFn: ({ devis, quoi }: { devis: DevisType; quoi: "accepter" | "refuser" | "encaisser" }) => {
      if (quoi === "accepter") return accepterDevis(devis.id).then((d) => `Devis ${d.numero} accepté.`);
      if (quoi === "refuser") return refuserDevis(devis.id).then((d) => `Devis ${d.numero} refusé.`);
      const montant = enCommande ? acompte || "0" : devis.total_ttc;
      return encaisserDevis(devis.id, { mode, montant }, enCommande, Number(peniche)).then((vente) =>
        vente.statut === "en_commande"
          ? `Devis ${devis.numero} passé en commande ${vente.numero} : reste ${formaterTexte(vente.reste_a_payer, monnaie)} à la livraison.`
          : `Devis ${devis.numero} encaissé : ticket ${vente.numero}.`,
      );
    },
    onSuccess: (texte) => {
      setMessage(texte);
      void rafraichir();
      void queryClient.invalidateQueries({ queryKey: ["articles"] });
    },
  });

  function ajouter(article: Article) {
    setMessage("");
    setLignes((actuelles) => [
      ...actuelles,
      { cle: Date.now() + actuelles.length, article, quantite: 1, remise: "", oeil: parOeil(article) ? "od" : "" },
    ]);
  }

  const modifier = (ligne: Ligne, changement: Partial<Ligne>) =>
    setLignes((actuelles) => actuelles.map((l) => (l === ligne ? { ...l, ...changement } : l)));

  const entete = (
    <>
      <Typography variant="h6" component="h2">
        Devis
      </Typography>
      {droits.consulter && (
        <Tabs value={onglet} onChange={(_, valeur) => setOnglet(valeur)}>
          <Tab value="etablir" label="Devis d'un client" />
          <Tab value="liste" label="Tous les devis" />
        </Tabs>
      )}
    </>
  );
  const fenetre = detail && <DetailDevis id={detail} decimales={monnaie.decimales} onFerme={() => setDetail(null)} />;

  if (onglet === "liste")
    return (
      <Card>
        <CardContent>
          <Stack spacing={2}>
            {entete}
            <ListeDevis decimales={monnaie.decimales} onDetail={setDetail} />
            {fenetre}
          </Stack>
        </CardContent>
      </Card>
    );

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          {entete}
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField
              select
              label="Magasin"
              value={magasin}
              onChange={(e) => {
                setMagasin(e.target.value);
                setLignes([]);
              }}
              sx={{ minWidth: 200 }}
            >
              {magasins.data?.map((m) => (
                <MenuItem key={m.id} value={m.id}>
                  {m.nom}
                </MenuItem>
              ))}
            </TextField>
            {client ? (
              <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexGrow: 1 }}>
                <Typography>
                  Client : {client.nom.toUpperCase()} {client.prenom}
                </Typography>
                <Button
                  size="small"
                  onClick={() => {
                    setClient(null);
                    setPrescription("");
                    setMessage("");
                  }}
                >
                  Changer
                </Button>
              </Stack>
            ) : (
              <TextField
                label="Client du devis"
                helperText="Nom, téléphone ou e-mail"
                value={rechercheClient}
                onChange={(e) => setRechercheClient(e.target.value)}
                sx={{ flexGrow: 1 }}
              />
            )}
          </Stack>
          {!client && (
            <List dense>
              {clients.data?.map((c) => (
                <ListItemButton key={c.id} onClick={() => setClient(c)}>
                  <ListItemText primary={`${c.nom.toUpperCase()} ${c.prenom}`} secondary={c.telephone} />
                </ListItemButton>
              ))}
            </List>
          )}

          {client && (
            <>
              {droits.voirOrdonnances && (
                <TextField
                  select
                  label="Ordonnance"
                  value={prescription}
                  onChange={(e) => setPrescription(e.target.value)}
                >
                  <MenuItem value="">Sans ordonnance</MenuItem>
                  {ordonnances.data?.map((o) => (
                    <MenuItem key={o.id} value={o.id}>
                      {o.type === "lunettes" ? "Lunettes" : "Lentilles"} du {dateCourte(o.date_prescription)},{" "}
                      {o.prescripteur}
                    </MenuItem>
                  ))}
                </TextField>
              )}
              <TextField
                label="Ajouter un article"
                helperText="Monture, verre, lentille… (référence, libellé ou code-barres)"
                value={recherche}
                onChange={(e) => setRecherche(e.target.value)}
              />
              <List dense>
                {articles.data?.map((article) => (
                  <ListItem
                    key={article.id}
                    disableGutters
                    secondaryAction={
                      <Button size="small" onClick={() => ajouter(article)}>
                        Ajouter
                      </Button>
                    }
                  >
                    <ListItemText
                      primary={`${article.libelle} · ${formaterTexte(article.prix_vente_ttc, monnaie)}`}
                      secondary={[article.reference, article.description].filter(Boolean).join(" · ")}
                    />
                  </ListItem>
                ))}
              </List>

              {lignes.length > 0 && (
                <Table size="small" aria-label="Lignes du devis">
                  <TableHead>
                    <TableRow>
                      <TableCell>Article</TableCell>
                      <TableCell />
                      <TableCell align="center">Quantité</TableCell>
                      {droits.remise && <TableCell />}
                      <TableCell />
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {lignes.map((ligne) => (
                      <TableRow key={ligne.cle}>
                        <TableCell>{ligne.article.libelle}</TableCell>
                        <TableCell>
                          {parOeil(ligne.article) && (
                            <TextField
                              select
                              size="small"
                              label="Œil"
                              value={ligne.oeil}
                              onChange={(e) => modifier(ligne, { oeil: e.target.value as Oeil })}
                            >
                              <MenuItem value="od">Droit</MenuItem>
                              <MenuItem value="og">Gauche</MenuItem>
                            </TextField>
                          )}
                        </TableCell>
                        <TableCell align="center">
                          <IconButton
                            size="small"
                            aria-label="Retirer un"
                            onClick={() => modifier(ligne, { quantite: Math.max(1, ligne.quantite - 1) })}
                          >
                            −
                          </IconButton>
                          {ligne.quantite}
                          <IconButton
                            size="small"
                            aria-label="Ajouter un"
                            onClick={() => modifier(ligne, { quantite: ligne.quantite + 1 })}
                          >
                            +
                          </IconButton>
                        </TableCell>
                        {droits.remise && (
                          <TableCell>
                            <TextField
                              size="small"
                              type="number"
                              label="Remise %"
                              value={ligne.remise}
                              onChange={(e) => modifier(ligne, { remise: e.target.value })}
                              sx={{ width: 90 }}
                            />
                          </TableCell>
                        )}
                        <TableCell>
                          <Button size="small" onClick={() => setLignes((a) => a.filter((l) => l !== ligne))}>
                            Retirer
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
              <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
                <Typography variant="h6" sx={{ flexGrow: 1 }}>
                  Total du devis : {formater(total, monnaie)}
                </Typography>
                <Button
                  variant="contained"
                  disabled={lignes.length === 0 || creation.isPending}
                  onClick={() => creation.mutate()}
                >
                  Établir le devis
                </Button>
              </Stack>
              {creation.isError && <Alert severity="error">{creation.error.message}</Alert>}
              {action.isError && <Alert severity="error">{action.error.message}</Alert>}
              {message && <Alert severity="success">{message}</Alert>}

              {devisClient.data && devisClient.data.length > 0 && (
                <>
                  <Typography variant="subtitle1" component="h3">
                    Devis du client
                  </Typography>
                  {droits.encaisser && (
                    <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ alignItems: "center" }}>
                      <TextField
                        select
                        size="small"
                        label="Paiement à l'encaissement"
                        value={mode}
                        onChange={(e) => setMode(e.target.value as ModePaiement)}
                        sx={{ minWidth: 220 }}
                      >
                        {MODES.map((m) => (
                          <MenuItem key={m.valeur} value={m.valeur}>
                            {m.libelle}
                          </MenuItem>
                        ))}
                      </TextField>
                      <FormControlLabel
                        control={<Checkbox checked={enCommande} onChange={(e) => setEnCommande(e.target.checked)} />}
                        label="En commande (verres à commander)"
                      />
                      {enCommande && (
                        <>
                          <TextField
                            size="small"
                            type="number"
                            label="Acompte"
                            value={acompte}
                            onChange={(e) => setAcompte(e.target.value)}
                          />
                          <TextField
                            size="small"
                            type="number"
                            required
                            label="Péniche"
                            value={peniche}
                            onChange={(e) => setPeniche(e.target.value)}
                          />
                        </>
                      )}
                    </Stack>
                  )}
                  <List dense aria-label="Devis du client">
                    {devisClient.data.map((devis) => {
                      const expire = devis.valable_jusqu_au < aujourdHui();
                      const ouvert = (devis.statut === "en_cours" || devis.statut === "accepte") && !expire;
                      const montant = formaterTexte(devis.total_ttc, {
                        devise: devis.devise,
                        decimales: monnaie.decimales,
                      });
                      return (
                        <ListItem key={devis.id} disableGutters>
                          <ListItemText
                            primary={`${devis.numero} · ${montant}`}
                            secondary={
                              devis.vente
                                ? `Ticket ${devis.vente}`
                                : `Valable jusqu'au ${dateCourte(devis.valable_jusqu_au)}`
                            }
                          />
                          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                            <ChipStatut devis={devis} />
                            {droits.consulter && (
                              <Button size="small" onClick={() => setDetail(devis.id)}>
                                Détail
                              </Button>
                            )}
                            {ouvert && droits.changerStatut && devis.statut === "en_cours" && (
                              <Button size="small" onClick={() => action.mutate({ devis, quoi: "accepter" })}>
                                Accepter
                              </Button>
                            )}
                            {ouvert && droits.changerStatut && (
                              <Button
                                size="small"
                                color="error"
                                onClick={() => action.mutate({ devis, quoi: "refuser" })}
                              >
                                Refuser
                              </Button>
                            )}
                            {ouvert && droits.encaisser && (
                              <Button
                                size="small"
                                variant="outlined"
                                disabled={action.isPending || (enCommande && !peniche)}
                                onClick={() => action.mutate({ devis, quoi: "encaisser" })}
                              >
                                {enCommande ? "Commander" : "Encaisser"}
                              </Button>
                            )}
                          </Stack>
                        </ListItem>
                      );
                    })}
                  </List>
                </>
              )}
            </>
          )}
          {fenetre}
        </Stack>
      </CardContent>
    </Card>
  );
}
