import Print from "@mui/icons-material/Print";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import List from "@mui/material/List";
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
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import {
  genererFacture,
  lireFacture,
  listerFactures,
  trouverVente,
  type Facture,
  type ModePaiement,
  type Vente,
} from "../api/caisse";
import { chercherClients, type Client } from "../api/clients";
import { listerMagasins, type Magasin } from "../api/magasins";
import { formaterTexte, type Monnaie } from "../api/monnaie";
import { imprimer } from "./FactureAchat";
import { useApaise } from "./RechercheClients";

const MODES: { valeur: ModePaiement; libelle: string }[] = [
  { valeur: "especes", libelle: "Espèces" },
  { valeur: "carte", libelle: "Carte bancaire" },
  { valeur: "cheque", libelle: "Chèque" },
];

export const LIBELLES_MODES: Record<string, string> = Object.fromEntries(MODES.map((m) => [m.valeur, m.libelle]));

export const dateDocument = (iso: string) => new Date(iso).toLocaleDateString("fr-FR");
export const echapper = (t: string) =>
  t.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] as string);

/** Monnaie d'un document de vente : sa devise, les décimales du pays de son magasin. */
export const monnaieDu = (magasins: Magasin[] | undefined, code: string, devise: string): Monnaie => ({
  devise,
  decimales: magasins?.find((m) => m.code === code)?.pays.decimales ?? 3,
});

/** Début commun des documents de vente imprimés (A4) : l'émetteur, puis le titre. */
export function enteteDocument(titre: string, magasin: Magasin | undefined) {
  const e = echapper;
  return `<!doctype html><html><head><meta charset="utf-8"><title>${e(titre)}</title><style>
@page { size: A4; margin: 12mm; }
body { font-family: Arial, sans-serif; font-size: 10pt; }
h1 { font-size: 16pt; margin: 4mm 0; }
table { border-collapse: collapse; width: 100%; margin: 3mm 0; }
th, td { border: 1px solid #999; padding: 1mm 1.5mm; }
th { background: #eee; text-align: left; }
.n { text-align: right; }
.totaux { width: auto; margin-left: auto; }
</style></head><body>
${magasin ? `<p><strong>${e(magasin.societe)}</strong><br>${e(magasin.nom)} · ${e(magasin.ville)}</p>` : ""}
<h1>${e(titre)}</h1>`;
}

/** Facture client imprimable (A4), telle qu'émise : client, lignes du ticket, totaux, timbre. */
export function pageFactureVente(f: Facture, monnaie: Monnaie, magasin?: Magasin) {
  const m = (v: string) => formaterTexte(v, monnaie);
  const e = echapper;
  const lignes = f.lignes
    .map(
      (l) =>
        `<tr><td>${e(l.libelle)}</td><td class="n">${l.quantite}</td><td class="n">${m(l.prix_unitaire_ttc)}</td><td class="n">${Number(l.remise_pct).toFixed(2)}</td><td class="n">${Number(l.taux_tva ?? 0).toFixed(2)}</td><td class="n">${m(l.total_ttc)}</td></tr>`,
    )
    .join("");
  const total = (libelle: string, valeur: string) => `<tr><td>${libelle}</td><td class="n">${m(valeur)}</td></tr>`;
  const client = f.client;
  return `${enteteDocument(`Facture ${f.numero}`, magasin)}
<p>Date : ${dateDocument(f.cree_le)} · Ticket : ${e(f.vente)}</p>
<p>Client : <strong>${e(client.nom)}</strong>${client.adresse ? `<br>${e(client.adresse)}` : ""}${client.matricule_fiscal ? `<br>Matricule fiscal : ${e(client.matricule_fiscal)}` : ""}</p>
<table><thead><tr><th>Article</th><th class="n">Qté</th><th class="n">Prix unitaire TTC</th><th class="n">Remise %</th><th class="n">TVA %</th><th class="n">Total TTC</th></tr></thead><tbody>${lignes}</tbody></table>
<table class="totaux"><tbody>${total("Total HT", f.total_ht)}${total("Total TVA", f.total_tva)}${total("Total TTC", f.total_ttc)}${Number(f.timbre_fiscal) ? total("Timbre fiscal", f.timbre_fiscal) : ""}<tr><th>Net à payer</th><th class="n">${m(f.net_a_payer)}</th></tr></tbody></table>
<p>Émise par ${e(f.emise_par)}${f.mode_paiement_timbre ? ` · Timbre réglé : ${LIBELLES_MODES[f.mode_paiement_timbre]}` : ""}</p>
</body></html>`;
}

/** Pagination des listes (50 par page côté API). */
export function Pages({ page, total, onPage }: { page: number; total: number; onPage: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / 50));
  if (pages <= 1) return null;
  return (
    <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end", alignItems: "center" }}>
      <Button size="small" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        Précédente
      </Button>
      <Typography variant="body2">
        Page {page} / {pages}
      </Typography>
      <Button size="small" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        Suivante
      </Button>
    </Stack>
  );
}

/** Facture émise, en lecture seule (document légal), avec réimpression. */
function DetailFacture({ id, magasins, onFerme }: { id: string; magasins?: Magasin[]; onFerme: () => void }) {
  const facture = useQuery({ queryKey: ["factures", id], queryFn: () => lireFacture(id) });
  const f = facture.data;
  const monnaie = monnaieDu(magasins, f?.magasin ?? "", f?.devise ?? "TND");
  const m = (v: string) => formaterTexte(v, monnaie);
  return (
    <Dialog open onClose={onFerme} maxWidth="md" fullWidth>
      <DialogTitle>{f ? `Facture ${f.numero}` : "Facture"}</DialogTitle>
      <DialogContent>
        {facture.isError && <Alert severity="error">{facture.error.message}</Alert>}
        {f && (
          <Stack spacing={2}>
            <Typography>
              {dateDocument(f.cree_le)} · {f.magasin} · ticket {f.vente} · émise par {f.emise_par}
            </Typography>
            <Typography>
              Client : <strong>{f.client.nom}</strong>
              {f.client.adresse && ` · ${f.client.adresse}`}
              {f.client.matricule_fiscal && ` · MF ${f.client.matricule_fiscal}`}
            </Typography>
            <Table size="small" aria-label="Lignes de la facture">
              <TableHead>
                <TableRow>
                  <TableCell>Article</TableCell>
                  <TableCell align="right">Qté</TableCell>
                  <TableCell align="right">Prix unitaire TTC</TableCell>
                  <TableCell align="right">Remise %</TableCell>
                  <TableCell align="right">Total TTC</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {f.lignes.map((l) => (
                  <TableRow key={l.id}>
                    <TableCell>{l.libelle}</TableCell>
                    <TableCell align="right">{l.quantite}</TableCell>
                    <TableCell align="right">{m(l.prix_unitaire_ttc)}</TableCell>
                    <TableCell align="right">{Number(l.remise_pct)}</TableCell>
                    <TableCell align="right">{m(l.total_ttc)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Typography>
              Total HT {m(f.total_ht)} · TVA {m(f.total_tva)} · TTC {m(f.total_ttc)}
              {Number(f.timbre_fiscal) > 0 && ` · Timbre ${m(f.timbre_fiscal)}`} ·{" "}
              <strong>Net à payer {m(f.net_a_payer)}</strong>
            </Typography>
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        {f && (
          <Button
            startIcon={<Print />}
            onClick={() =>
              imprimer(
                pageFactureVente(
                  f,
                  monnaie,
                  magasins?.find((mg) => mg.code === f.magasin),
                ),
              )
            }
          >
            Imprimer
          </Button>
        )}
        <Button onClick={onFerme}>Fermer</Button>
      </DialogActions>
    </Dialog>
  );
}

/** Factures déjà émises : consultation et réimpression ; ni modification ni suppression. */
function ListeFactures() {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [numero, setNumero] = useState("");
  const [page, setPage] = useState(1);
  const [ouverte, setOuverte] = useState<string | null>(null);
  const recherche = useApaise(numero);
  const factures = useQuery({
    queryKey: ["factures", "liste", recherche, page],
    queryFn: () => listerFactures(recherche, page),
    placeholderData: keepPreviousData,
  });
  const ttc = (f: Facture) => formaterTexte(f.total_ttc, monnaieDu(magasins.data, f.magasin, f.devise));

  return (
    <Stack spacing={1}>
      <TextField
        size="small"
        label="N° de facture"
        helperText="Numéro complet, par exemple T01-F2026-000001"
        value={numero}
        onChange={(e) => {
          setNumero(e.target.value);
          setPage(1);
        }}
      />
      {factures.isError && <Alert severity="error">{factures.error.message}</Alert>}
      <TableContainer sx={{ maxHeight: 520 }}>
        <Table stickyHeader size="small" aria-label="Factures émises">
          <TableHead>
            <TableRow>
              <TableCell>Numéro</TableCell>
              <TableCell>Date</TableCell>
              <TableCell>Client</TableCell>
              <TableCell>Magasin</TableCell>
              <TableCell align="right">Total TTC</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {factures.data?.results.map((f) => (
              <TableRow key={f.id} hover onClick={() => setOuverte(f.id)} sx={{ cursor: "pointer" }}>
                <TableCell>{f.numero}</TableCell>
                <TableCell>{dateDocument(f.cree_le)}</TableCell>
                <TableCell>{f.client.nom}</TableCell>
                <TableCell>{f.magasin}</TableCell>
                <TableCell align="right">{ttc(f)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      {factures.data?.count === 0 && <Typography color="text.secondary">Aucune facture.</Typography>}
      <Pages page={page} total={factures.data?.count ?? 0} onPage={setPage} />
      {ouverte && <DetailFacture id={ouverte} magasins={magasins.data} onFerme={() => setOuverte(null)} />}
    </Stack>
  );
}

/**
 * Factures : génération (droit d'en émettre) et consultation des factures émises (droit de les
 * voir). Ce sont des documents légaux : jamais modifiés ni supprimés.
 */
export function Factures({ generer = true, consulter = true }: { generer?: boolean; consulter?: boolean }) {
  const [onglet, setOnglet] = useState(generer ? 0 : 1);
  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Factures
          </Typography>
          {generer && consulter && (
            <Tabs value={onglet} onChange={(_, o: number) => setOnglet(o)}>
              <Tab label="Générer une facture" />
              <Tab label="Factures émises" />
            </Tabs>
          )}
          {onglet === 0 ? <GenerationFacture /> : <ListeFactures />}
        </Stack>
      </CardContent>
    </Card>
  );
}

/**
 * Génération d'une facture, à part de la caisse : on retrouve le ticket, on vérifie qu'il est
 * entièrement payé, on choisit le client et on encaisse le droit de timbre.
 */
function GenerationFacture() {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [numero, setNumero] = useState("");
  const [vente, setVente] = useState<Vente | null>(null);
  const [recherche, setRecherche] = useState("");
  const [client, setClient] = useState<Client | null>(null);
  const [mode, setMode] = useState<ModePaiement>("especes");
  const [facture, setFacture] = useState<Facture | null>(null);

  const magasin = magasins.data?.find((m) => vente?.numero.startsWith(`${m.code}-`));
  const pays = magasin?.pays;
  const monnaie: Monnaie = { devise: vente?.devise ?? "TND", decimales: pays?.decimales ?? 3 };
  const timbre = Number(pays?.timbre_fiscal ?? "0");
  const solde = vente !== null && Number(vente.reste_a_payer) === 0;

  const recherchee = useMutation({
    mutationFn: () => trouverVente(numero.trim()),
    onSuccess: (trouvee) => {
      setVente(trouvee);
      setClient(null);
      setFacture(null);
    },
  });
  const clients = useQuery({
    queryKey: ["clients", recherche],
    queryFn: () => chercherClients(recherche),
    enabled: Boolean(vente) && !vente?.client && !client && recherche.trim().length >= 2,
  });
  const generation = useMutation({
    mutationFn: () =>
      genererFacture({
        vente: vente!.id,
        client: client?.id ?? vente!.client?.id,
        mode_paiement_timbre: timbre > 0 ? mode : undefined,
      }),
    onSuccess: setFacture,
  });

  function chercher(e: FormEvent) {
    e.preventDefault();
    recherchee.mutate();
  }

  const nomClient = client ? `${client.nom.toUpperCase()} ${client.prenom}` : vente?.client?.nom;

  return (
    <Stack spacing={2}>
      <Stack component="form" direction="row" spacing={2} onSubmit={chercher}>
        <TextField
          label="N° de ticket"
          value={numero}
          onChange={(e) => setNumero(e.target.value)}
          sx={{ flexGrow: 1 }}
        />
        <Button type="submit" disabled={!numero.trim() || recherchee.isPending}>
          Rechercher
        </Button>
      </Stack>
      {recherchee.isError && <Alert severity="error">{recherchee.error.message}</Alert>}
      {recherchee.isSuccess && !vente && <Alert severity="warning">Ticket introuvable.</Alert>}

      {vente && (
        <>
          <Typography>
            Ticket {vente.numero} : {formaterTexte(vente.total_ttc, monnaie)}
          </Typography>
          {vente.facture && <Alert severity="info">Déjà facturé : facture {vente.facture}.</Alert>}
          {!vente.facture && !solde && (
            <Alert severity="warning">
              Commande pas entièrement payée : reste {formaterTexte(vente.reste_a_payer, monnaie)}. La facture sera
              possible une fois soldée.
            </Alert>
          )}
        </>
      )}

      {vente && solde && !vente.facture && !facture && (
        <>
          {nomClient ? (
            <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
              <Typography>Au nom de {nomClient}</Typography>
              {client && (
                <Button size="small" onClick={() => setClient(null)}>
                  Changer
                </Button>
              )}
            </Stack>
          ) : (
            <>
              <TextField
                label="Client de la facture"
                helperText="Nom, téléphone ou e-mail"
                value={recherche}
                onChange={(e) => setRecherche(e.target.value)}
              />
              <List dense>
                {clients.data?.map((c) => (
                  <ListItemButton key={c.id} onClick={() => setClient(c)}>
                    <ListItemText primary={`${c.nom.toUpperCase()} ${c.prenom}`} secondary={c.telephone} />
                  </ListItemButton>
                ))}
              </List>
            </>
          )}
          {timbre > 0 && (
            <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
              <Typography sx={{ flexGrow: 1 }}>
                Timbre fiscal à encaisser : {formaterTexte(pays!.timbre_fiscal, monnaie)}
              </Typography>
              <TextField
                select
                size="small"
                label="Paiement du timbre"
                value={mode}
                onChange={(e) => setMode(e.target.value as ModePaiement)}
              >
                {MODES.map((m) => (
                  <MenuItem key={m.valeur} value={m.valeur}>
                    {m.libelle}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>
          )}
          {generation.isError && <Alert severity="error">{generation.error.message}</Alert>}
          <Button variant="contained" disabled={!nomClient || generation.isPending} onClick={() => generation.mutate()}>
            Générer la facture
          </Button>
        </>
      )}

      {facture && (
        <Alert
          severity="success"
          action={
            <Button
              color="inherit"
              startIcon={<Print />}
              onClick={() => imprimer(pageFactureVente(facture, monnaie, magasin))}
            >
              Imprimer
            </Button>
          }
        >
          Facture {facture.numero} au nom de {facture.client.nom} : {formaterTexte(facture.total_ttc, monnaie)}
          {Number(facture.timbre_fiscal) > 0 && ` + timbre ${formaterTexte(facture.timbre_fiscal, monnaie)}`} ={" "}
          {formaterTexte(facture.net_a_payer, monnaie)}.
        </Alert>
      )}
    </Stack>
  );
}
