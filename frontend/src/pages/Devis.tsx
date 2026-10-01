import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemText from "@mui/material/ListItemText";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { chercherArticles, type Article, type ModePaiement } from "../api/caisse";
import { chercherClients, listerPrescriptions, type Client } from "../api/clients";
import {
  accepterDevis,
  encaisserDevis,
  etablirDevis,
  listerDevis,
  refuserDevis,
  type Devis as DevisType,
  type Oeil,
  type StatutDevis,
} from "../api/devis";
import { listerMagasins } from "../api/magasins";
import { enUnites, formater, formaterTexte, type Monnaie } from "../api/monnaie";

export type DroitsDevis = {
  remise: boolean;
  voirOrdonnances: boolean;
  changerStatut: boolean;
  encaisser: boolean;
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
  const [message, setMessage] = useState("");

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
      Math.round(enUnites(l.article.prix_vente_ttc, monnaie.decimales) * l.quantite * (1 - Number(l.remise || 0) / 100)),
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
      return encaisserDevis(devis.id, { mode, montant: devis.total_ttc }).then(
        (vente) => `Devis ${devis.numero} encaissé : ticket ${vente.numero}.`,
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

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Devis
          </Typography>
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
                      {o.type === "lunettes" ? "Lunettes" : "Lentilles"} du {dateCourte(o.date_prescription)}, {o.prescripteur}
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
                      secondary={article.reference}
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
                    <TextField
                      select
                      size="small"
                      label="Paiement à l'encaissement"
                      value={mode}
                      onChange={(e) => setMode(e.target.value as ModePaiement)}
                      sx={{ maxWidth: 240 }}
                    >
                      {MODES.map((m) => (
                        <MenuItem key={m.valeur} value={m.valeur}>
                          {m.libelle}
                        </MenuItem>
                      ))}
                    </TextField>
                  )}
                  <List dense aria-label="Devis du client">
                    {devisClient.data.map((devis) => {
                      const expire = devis.valable_jusqu_au < aujourdHui();
                      const ouvert = (devis.statut === "en_cours" || devis.statut === "accepte") && !expire;
                      const statut = expire && !devis.vente && devis.statut !== "refuse"
                        ? { libelle: "Expiré", couleur: "default" as const }
                        : STATUTS[devis.statut];
                      const montant = formaterTexte(devis.total_ttc, { devise: devis.devise, decimales: monnaie.decimales });
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
                            <Chip size="small" label={statut.libelle} color={statut.couleur} />
                            {ouvert && droits.changerStatut && devis.statut === "en_cours" && (
                              <Button size="small" onClick={() => action.mutate({ devis, quoi: "accepter" })}>
                                Accepter
                              </Button>
                            )}
                            {ouvert && droits.changerStatut && (
                              <Button size="small" color="error" onClick={() => action.mutate({ devis, quoi: "refuser" })}>
                                Refuser
                              </Button>
                            )}
                            {ouvert && droits.encaisser && (
                              <Button
                                size="small"
                                variant="outlined"
                                disabled={action.isPending}
                                onClick={() => action.mutate({ devis, quoi: "encaisser" })}
                              >
                                Encaisser
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
        </Stack>
      </CardContent>
    </Card>
  );
}
