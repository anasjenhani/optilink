import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemText from "@mui/material/ListItemText";
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
import { useState, type FormEvent } from "react";

import { chercherClients, type Client } from "../api/clients";
import { listerMagasins } from "../api/magasins";
import { listerVisites, type FiltresVisites } from "../api/visites";
import { Filtres } from "../navigation/Filtres";
import { dateHeure, FicheVisite, STATUTS_VENTE, useMontant } from "./FicheVisite";

const STATUTS = [
  { valeur: "", libelle: "Tous" },
  { valeur: "en_commande", libelle: "En commande" },
  { valeur: "livree", libelle: "Livrée" },
  { valeur: "annulee", libelle: "Annulée" },
];
const FACTUREE = [
  { valeur: "" as const, libelle: "Tous" },
  { valeur: "true" as const, libelle: "Facturée" },
  { valeur: "false" as const, libelle: "Non facturée" },
];

function ListeVisites({ filtres, casse, resume = false }: { filtres: FiltresVisites; casse: boolean; resume?: boolean }) {
  const [page, setPage] = useState(1);
  const [ouverte, setOuverte] = useState<string | null>(null);
  const montant = useMontant();
  const visites = useQuery({
    queryKey: ["visites", filtres, page],
    queryFn: () => listerVisites({ ...filtres, page }),
  });
  const lignes = visites.data?.results ?? [];
  const pages = Math.max(1, Math.ceil((visites.data?.count ?? 0) / 50));
  const total = lignes.filter((v) => v.statut !== "annulee").reduce((s, v) => s + Number(v.total_ttc), 0);

  return (
    <Stack spacing={1}>
      {visites.isError && <Alert severity="error">{visites.error.message}</Alert>}
      {visites.data && (
        <Typography variant="body2" color="text.secondary">
          {visites.data.count} visite{visites.data.count > 1 ? "s" : ""}
          {resume && lignes[0] && ` · ${montant(String(total), lignes[0].devise, lignes[0].magasin)} d'achats (hors annulées)`}
        </Typography>
      )}
      {visites.data?.count === 0 && <Typography color="text.secondary">Aucune visite ne correspond.</Typography>}
      {lignes.length > 0 && (
        <TableContainer>
          <Table size="small" aria-label="Visites">
            <TableHead>
              <TableRow>
                {["N° visite", "Date", "Client", "Vendeur", "Total", "Reste", "Statut", "Facture"].map((t) => (
                  <TableCell key={t} align={t === "Total" || t === "Reste" ? "right" : "left"}>
                    {t}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {lignes.map((v) => (
                <TableRow key={v.id} hover onClick={() => setOuverte(v.id)} sx={{ cursor: "pointer" }}>
                  <TableCell>
                    <Button size="small" sx={{ p: 0, minWidth: 0, textTransform: "none" }} onClick={() => setOuverte(v.id)}>
                      {v.numero}
                    </Button>
                  </TableCell>
                  <TableCell>{dateHeure(v.cree_le)}</TableCell>
                  <TableCell>{v.client?.nom ?? "Client de passage"}</TableCell>
                  <TableCell>{v.vendeur}</TableCell>
                  <TableCell align="right">{montant(v.total_ttc, v.devise, v.magasin)}</TableCell>
                  <TableCell align="right">
                    {Number(v.reste_a_payer) > 0 ? montant(v.reste_a_payer, v.devise, v.magasin) : ""}
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={STATUTS_VENTE[v.statut] ?? v.statut}
                      color={v.statut === "annulee" ? "error" : v.statut === "en_commande" ? "warning" : "default"}
                    />
                  </TableCell>
                  <TableCell>{v.facture ?? ""}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      {pages > 1 && (
        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <Button size="small" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            Précédente
          </Button>
          <Typography variant="body2">
            Page {page} / {pages}
          </Typography>
          <Button size="small" disabled={page >= pages} onClick={() => setPage(page + 1)}>
            Suivante
          </Button>
        </Stack>
      )}
      {ouverte && <FicheVisite id={ouverte} casse={casse} onFermer={() => setOuverte(null)} />}
    </Stack>
  );
}

/** Liste des visites (ventes et commandes) avec ses filtres ; un clic ouvre la fiche. */
export function Visites({ casse = false, factureeInitiale = "" }: { casse?: boolean; factureeInitiale?: "" | "true" | "false" }) {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [magasin, setMagasin] = useState("");
  const [du, setDu] = useState("");
  const [au, setAu] = useState("");
  const [saisie, setSaisie] = useState("");
  const [recherche, setRecherche] = useState("");
  const [statut, setStatut] = useState("");
  const [facturee, setFacturee] = useState<"" | "true" | "false">(factureeInitiale);

  function chercher(e: FormEvent) {
    e.preventDefault();
    setRecherche(saisie);
  }

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Liste des visites
          </Typography>
          <Stack component="form" onSubmit={chercher} direction={{ xs: "column", md: "row" }} spacing={2}>
            <TextField select size="small" label="Magasin" value={magasin} onChange={(e) => setMagasin(e.target.value)} sx={{ minWidth: 180 }}>
              <MenuItem value="">Tous</MenuItem>
              {magasins.data?.map((m) => (
                <MenuItem key={m.id} value={m.id}>
                  {m.nom}
                </MenuItem>
              ))}
            </TextField>
            <TextField size="small" type="date" label="Du" value={du} onChange={(e) => setDu(e.target.value)} slotProps={{ inputLabel: { shrink: true } }} />
            <TextField size="small" type="date" label="Au" value={au} onChange={(e) => setAu(e.target.value)} slotProps={{ inputLabel: { shrink: true } }} />
            <TextField
              size="small"
              label="N° visite, nom, téléphone ou n° de fiche"
              value={saisie}
              onChange={(e) => setSaisie(e.target.value)}
              sx={{ flex: 1, minWidth: 0 }}
            />
            <Button type="submit" variant="contained">
              Rechercher
            </Button>
          </Stack>
          <ListeVisites filtres={{ magasin, du, au, recherche, statut, facturee }} casse={casse} />
          <Filtres libelle="Statut" options={STATUTS} valeur={statut} onChange={setStatut} />
          <Filtres libelle="Facture" options={FACTUREE} valeur={facturee} onChange={setFacturee} />
        </Stack>
      </CardContent>
    </Card>
  );
}

/** Ouvre une visite par son numéro (ou sa fin : « 12 » pour …-000012). */
export function ConsulterVisite({ casse = false }: { casse?: boolean }) {
  const [saisie, setSaisie] = useState("");
  const [recherche, setRecherche] = useState("");
  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Consulter une visite
          </Typography>
          <Stack
            component="form"
            direction="row"
            spacing={2}
            onSubmit={(e) => {
              e.preventDefault();
              setRecherche(saisie.trim());
            }}
          >
            <TextField
              size="small"
              autoFocus
              label="N° de visite"
              helperText="Le numéro complet, ou ses derniers chiffres."
              value={saisie}
              onChange={(e) => setSaisie(e.target.value)}
            />
            <Button type="submit" variant="contained" sx={{ alignSelf: "flex-start" }}>
              Ouvrir
            </Button>
          </Stack>
          {recherche && <ListeVisites filtres={{ recherche }} casse={casse} />}
        </Stack>
      </CardContent>
    </Card>
  );
}

/** Historique d'un client : on le cherche, puis on voit toutes ses visites. */
export function HistoriqueVisites({ casse = false }: { casse?: boolean }) {
  const [saisie, setSaisie] = useState("");
  const [recherche, setRecherche] = useState("");
  const [client, setClient] = useState<Client | null>(null);
  const clients = useQuery({
    queryKey: ["clients", recherche],
    queryFn: () => chercherClients(recherche),
    enabled: recherche.length >= 2,
  });
  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Historique des visites d'un client
          </Typography>
          {client ? (
            <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
              <Typography>
                <strong>
                  {client.nom} {client.prenom}
                </strong>{" "}
                · fiche n° {client.numero}
                {client.telephone && ` · ${client.telephone}`}
              </Typography>
              <Button size="small" onClick={() => setClient(null)}>
                Changer de client
              </Button>
            </Stack>
          ) : (
            <Stack
              component="form"
              direction="row"
              spacing={2}
              onSubmit={(e) => {
                e.preventDefault();
                setRecherche(saisie.trim());
              }}
            >
              <TextField
                size="small"
                autoFocus
                label="Nom, prénom, téléphone ou n° de fiche"
                value={saisie}
                onChange={(e) => setSaisie(e.target.value)}
                sx={{ flex: 1, minWidth: 0 }}
              />
              <Button type="submit" variant="contained">
                Chercher
              </Button>
            </Stack>
          )}
          {!client && clients.data?.length === 0 && <Typography color="text.secondary">Aucun client trouvé.</Typography>}
          {!client && clients.data && clients.data.length > 0 && (
            <List dense aria-label="Clients trouvés">
              {clients.data.map((c) => (
                <ListItemButton key={c.id} onClick={() => setClient(c)}>
                  <ListItemText primary={`${c.nom} ${c.prenom}`} secondary={`Fiche n° ${c.numero}${c.telephone ? ` · ${c.telephone}` : ""}`} />
                </ListItemButton>
              ))}
            </List>
          )}
          {client && <ListeVisites filtres={{ client: client.id }} casse={casse} resume />}
        </Stack>
      </CardContent>
    </Card>
  );
}
