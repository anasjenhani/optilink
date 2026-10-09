import Print from "@mui/icons-material/Print";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Checkbox from "@mui/material/Checkbox";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
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
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { MODES_PAIEMENT, type ModePaiement } from "../api/caisse";
import { chercherClients, nomClient, type Client } from "../api/clients";
import {
  cloturerMois,
  facturerEnsemble,
  lireFactureGroupee,
  listerClotures,
  listerFacturesGroupees,
  preparerCloture,
  ventesAFacturer,
  type DetailTva,
  type FactureGroupeeDetail,
} from "../api/facturation";
import { listerMagasins, type Magasin } from "../api/magasins";
import { formaterTexte, type Monnaie } from "../api/monnaie";
import { imprimer } from "./FactureAchat";
import { dateDocument, echapper, enteteDocument } from "./Factures";

const MOIS = [
  "janvier",
  "février",
  "mars",
  "avril",
  "mai",
  "juin",
  "juillet",
  "août",
  "septembre",
  "octobre",
  "novembre",
  "décembre",
];
const libelleMois = (annee: number, mois: number) => `${MOIS[mois - 1]} ${annee}`;
const date = (iso: string | null) => (iso ? dateDocument(iso) : "");
const monnaieDe = (magasin: Magasin | undefined): Monnaie => ({
  devise: magasin?.pays.devise ?? "TND",
  decimales: magasin?.pays.decimales ?? 3,
});

/** Facture groupée ou récapitulative imprimable (A4) : ventes, TVA par taux, totaux, timbre. */
export function pageFactureGroupee(f: FactureGroupeeDetail, monnaie: Monnaie, magasin?: Magasin) {
  const m = (v: string) => formaterTexte(v, monnaie);
  const e = echapper;
  const detail = f.lignes.length
    ? `<table><thead><tr><th>Ticket</th><th>Article</th><th class="n">Qté</th><th class="n">Prix unitaire TTC</th><th class="n">Remise %</th><th class="n">TVA %</th><th class="n">Total TTC</th></tr></thead><tbody>${f.lignes
        .map(
          (l) =>
            `<tr><td>${e(l.vente)}</td><td>${e(l.libelle)}</td><td class="n">${l.quantite}</td><td class="n">${m(l.prix_unitaire_ttc)}</td><td class="n">${Number(l.remise_pct).toFixed(2)}</td><td class="n">${Number(l.taux_tva).toFixed(2)}</td><td class="n">${m(l.total_ttc)}</td></tr>`,
        )
        .join("")}</tbody></table>`
    : `<p>${f.ventes.length} ventes du ${dateDocument(f.du)} au ${dateDocument(f.au)} : ${f.ventes.map((v) => e(v.numero)).join(", ")}</p>`;
  const tva = f.detail_tva
    .map(
      (d) =>
        `<tr><td class="n">${Number(d.taux).toFixed(2)} %</td><td class="n">${m(d.total_ht)}</td><td class="n">${m(d.total_tva)}</td><td class="n">${m(d.total_ttc)}</td></tr>`,
    )
    .join("");
  const total = (libelle: string, valeur: string) => `<tr><td>${libelle}</td><td class="n">${m(valeur)}</td></tr>`;
  const titre = f.type === "mensuelle" ? `Facture récapitulative ${f.numero}` : `Facture ${f.numero}`;
  return `${enteteDocument(titre, magasin)}
<p>Date : ${dateDocument(f.cree_le)} · Période : du ${dateDocument(f.du)} au ${dateDocument(f.au)}</p>
<p>Client : <strong>${e(f.client_nom)}</strong>${f.client_adresse ? `<br>${e(f.client_adresse)}` : ""}${f.client_matricule_fiscal ? `<br>Matricule fiscal : ${e(f.client_matricule_fiscal)}` : ""}</p>
${detail}
<table class="totaux"><thead><tr><th>Taux TVA</th><th class="n">Base HT</th><th class="n">TVA</th><th class="n">TTC</th></tr></thead><tbody>${tva}</tbody></table>
<table class="totaux"><tbody>${total("Total HT", f.total_ht)}${total("Total TVA", f.total_tva)}${total("Total TTC", f.total_ttc)}${Number(f.timbre_fiscal) ? total("Timbre fiscal", f.timbre_fiscal) : ""}<tr><th>Net à payer</th><th class="n">${m(f.net_a_payer)}</th></tr></tbody></table>
<p>Émise par ${e(f.emise_par)}</p>
</body></html>`;
}

function ChoixMagasin({
  magasins,
  valeur,
  onChange,
}: {
  magasins: Magasin[] | undefined;
  valeur: string;
  onChange: (id: string) => void;
}) {
  if ((magasins?.length ?? 0) <= 1) return null;
  return (
    <TextField
      select
      size="small"
      label="Magasin"
      value={valeur}
      onChange={(ev) => onChange(ev.target.value)}
      sx={{ minWidth: 200 }}
    >
      {magasins?.map((m) => (
        <MenuItem key={m.id} value={m.id}>
          {m.nom}
        </MenuItem>
      ))}
    </TextField>
  );
}

function TableauTva({ detail, monnaie }: { detail: DetailTva[]; monnaie: Monnaie }) {
  const m = (v: string) => formaterTexte(v, monnaie);
  return (
    <Table size="small" aria-label="TVA par taux" sx={{ width: "auto" }}>
      <TableHead>
        <TableRow>
          <TableCell>Taux TVA</TableCell>
          <TableCell align="right">Base HT</TableCell>
          <TableCell align="right">TVA</TableCell>
          <TableCell align="right">TTC</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {detail.map((d) => (
          <TableRow key={d.taux}>
            <TableCell>{Number(d.taux)} %</TableCell>
            <TableCell align="right">{m(d.total_ht)}</TableCell>
            <TableCell align="right">{m(d.total_tva)}</TableCell>
            <TableCell align="right">{m(d.total_ttc)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

/** Bouton d'impression d'une facture groupée : la lit en entier puis l'imprime. */
function ImprimerFacture({ id, magasins }: { id: string; magasins?: Magasin[] }) {
  const lecture = useMutation({ mutationFn: () => lireFactureGroupee(id) });
  return (
    <Button
      size="small"
      startIcon={<Print />}
      disabled={lecture.isPending}
      onClick={() =>
        lecture.mutate(undefined, {
          onSuccess: (f) => {
            const magasin = magasins?.find((m) => m.code === f.magasin);
            imprimer(pageFactureGroupee(f, monnaieDe(magasin), magasin));
          },
        })
      }
    >
      Imprimer
    </Button>
  );
}

function NouvelleFacture({ comptoir }: { comptoir: boolean }) {
  const queryClient = useQueryClient();
  const magasins = useQuery({
    queryKey: ["magasins"],
    queryFn: listerMagasins,
  });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = magasins.data?.find((m) => m.id === magasinChoisi) ?? magasins.data?.[0];
  const monnaie = monnaieDe(magasin);
  const [recherche, setRecherche] = useState("");
  const [client, setClient] = useState<Client | null>(null);
  const [societe, setSociete] = useState({
    nom: "",
    adresse: "",
    matricule: "",
  });
  const [du, setDu] = useState("");
  const [au, setAu] = useState("");
  const [coches, setCoches] = useState<Set<string>>(new Set());
  const [mode, setMode] = useState<ModePaiement>("especes");
  const [emise, setEmise] = useState<FactureGroupeeDetail | null>(null);
  const timbre = Number(magasin?.pays.timbre_fiscal ?? "0");

  const clients = useQuery({
    queryKey: ["clients", recherche],
    queryFn: () => chercherClients(recherche),
    enabled: !client && recherche.trim().length >= 2,
  });
  const ventes = useQuery({
    queryKey: ["ventes-a-facturer", magasin?.id, client?.id, comptoir, du, au],
    queryFn: () =>
      ventesAFacturer({
        magasin: magasin!.id,
        client: client?.id,
        comptoir,
        du,
        au,
      }),
    enabled: Boolean(magasin && (client || comptoir)),
  });
  const generation = useMutation({
    mutationFn: () =>
      facturerEnsemble({
        magasin: magasin!.id,
        ventes: [...coches],
        client: client?.id ?? null,
        client_nom: client ? "" : societe.nom,
        client_adresse: client ? "" : societe.adresse,
        client_matricule_fiscal: client ? "" : societe.matricule,
        mode_paiement_timbre: timbre > 0 ? mode : "",
      }),
    onSuccess: (f) => {
      setEmise(f);
      setCoches(new Set());
      void queryClient.invalidateQueries({ queryKey: ["ventes-a-facturer"] });
      void queryClient.invalidateQueries({ queryKey: ["factures-groupees"] });
    },
  });
  const choisies = ventes.data?.filter((v) => coches.has(v.id)) ?? [];
  const total = choisies.reduce((s, v) => s + Number(v.total_ttc), 0).toFixed(monnaie.decimales);
  const basculer = (id: string) =>
    setCoches((c) => {
      const suivant = new Set(c);
      if (suivant.has(id)) suivant.delete(id);
      else suivant.add(id);
      return suivant;
    });
  const nomOk = Boolean(client || societe.nom.trim());

  return (
    <Stack spacing={2}>
      <Stack direction="row" spacing={2} sx={{ flexWrap: "wrap", rowGap: 2 }}>
        <ChoixMagasin
          magasins={magasins.data}
          valeur={magasin?.id ?? ""}
          onChange={(id) => {
            setMagasin(id);
            setCoches(new Set());
          }}
        />
        <TextField
          size="small"
          type="date"
          label="Du"
          value={du}
          onChange={(ev) => setDu(ev.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <TextField
          size="small"
          type="date"
          label="Au"
          value={au}
          onChange={(ev) => setAu(ev.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
        />
      </Stack>
      {client ? (
        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <Typography>
            Client : <strong>{nomClient(client)}</strong>
          </Typography>
          <Button
            size="small"
            onClick={() => {
              setClient(null);
              setCoches(new Set());
            }}
          >
            Changer
          </Button>
        </Stack>
      ) : (
        <>
          <TextField
            size="small"
            label="Client"
            helperText={
              comptoir
                ? "Fiche client (nom, téléphone), ou laisser vide et saisir la société ci-dessous"
                : "Nom, téléphone ou n° de fiche"
            }
            value={recherche}
            onChange={(ev) => setRecherche(ev.target.value)}
          />
          {(clients.data?.length ?? 0) > 0 && (
            <List dense>
              {clients.data?.map((c) => (
                <ListItemButton key={c.id} onClick={() => setClient(c)}>
                  <ListItemText primary={nomClient(c)} secondary={c.telephone} />
                </ListItemButton>
              ))}
            </List>
          )}
          {comptoir && (
            <Stack direction="row" spacing={2} sx={{ flexWrap: "wrap", rowGap: 2 }}>
              <TextField
                size="small"
                label="Facturer au nom de"
                value={societe.nom}
                onChange={(ev) => setSociete({ ...societe, nom: ev.target.value })}
              />
              <TextField
                size="small"
                label="Adresse"
                value={societe.adresse}
                onChange={(ev) => setSociete({ ...societe, adresse: ev.target.value })}
              />
              <TextField
                size="small"
                label="Matricule fiscal"
                value={societe.matricule}
                onChange={(ev) => setSociete({ ...societe, matricule: ev.target.value })}
              />
            </Stack>
          )}
        </>
      )}
      {ventes.isError && <Alert severity="error">{ventes.error.message}</Alert>}
      {ventes.data?.length === 0 && (
        <Typography color="text.secondary">
          Aucune vente à facturer : il faut une vente livrée, soldée, sans facture, dans un mois pas encore clôturé.
        </Typography>
      )}
      {(ventes.data?.length ?? 0) > 0 && (
        <TableContainer sx={{ maxHeight: 420 }}>
          <Table stickyHeader size="small" aria-label="Ventes à facturer">
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox">
                  <Checkbox
                    checked={coches.size === ventes.data!.length}
                    indeterminate={coches.size > 0 && coches.size < ventes.data!.length}
                    onChange={(ev) => setCoches(new Set(ev.target.checked ? ventes.data!.map((v) => v.id) : []))}
                    slotProps={{ input: { "aria-label": "Tout cocher" } }}
                  />
                </TableCell>
                <TableCell>N°</TableCell>
                <TableCell>Livrée le</TableCell>
                <TableCell>Client</TableCell>
                <TableCell align="right">Total TTC</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {ventes.data!.map((v) => (
                <TableRow key={v.id} hover onClick={() => basculer(v.id)} sx={{ cursor: "pointer" }}>
                  <TableCell padding="checkbox">
                    <Checkbox checked={coches.has(v.id)} slotProps={{ input: { "aria-label": v.numero } }} />
                  </TableCell>
                  <TableCell>{v.numero}</TableCell>
                  <TableCell>{date(v.livree_le)}</TableCell>
                  <TableCell>{v.client ?? "Passage"}</TableCell>
                  <TableCell align="right">{formaterTexte(v.total_ttc, monnaie)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      {coches.size > 0 && (
        <Stack direction="row" spacing={2} sx={{ alignItems: "center", flexWrap: "wrap", rowGap: 2 }}>
          <Typography sx={{ flexGrow: 1 }}>
            {coches.size} ventes · {formaterTexte(total, monnaie)}
            {timbre > 0 && ` + timbre ${formaterTexte(magasin!.pays.timbre_fiscal, monnaie)}`}
          </Typography>
          {timbre > 0 && (
            <TextField
              select
              size="small"
              label="Paiement du timbre"
              value={mode}
              onChange={(ev) => setMode(ev.target.value as ModePaiement)}
              sx={{ minWidth: 180 }}
            >
              {MODES_PAIEMENT.map((m) => (
                <MenuItem key={m.valeur} value={m.valeur}>
                  {m.libelle}
                </MenuItem>
              ))}
            </TextField>
          )}
          <Button variant="contained" disabled={!nomOk || generation.isPending} onClick={() => generation.mutate()}>
            Générer la facture
          </Button>
        </Stack>
      )}
      {generation.isError && <Alert severity="error">{generation.error.message}</Alert>}
      {emise && (
        <Alert
          severity="success"
          action={
            <Button
              color="inherit"
              startIcon={<Print />}
              onClick={() => imprimer(pageFactureGroupee(emise, monnaie, magasin))}
            >
              Imprimer
            </Button>
          }
        >
          Facture {emise.numero} au nom de {emise.client_nom} : {emise.nombre_ventes} ventes,{" "}
          {formaterTexte(emise.net_a_payer, monnaie)}.
        </Alert>
      )}
    </Stack>
  );
}

function FacturesEmises() {
  const magasins = useQuery({
    queryKey: ["magasins"],
    queryFn: listerMagasins,
  });
  const [numero, setNumero] = useState("");
  const factures = useQuery({
    queryKey: ["factures-groupees", numero],
    queryFn: () => listerFacturesGroupees({ numero }),
  });
  return (
    <Stack spacing={1}>
      <TextField size="small" label="N° de facture" value={numero} onChange={(ev) => setNumero(ev.target.value)} />
      {factures.isError && <Alert severity="error">{factures.error.message}</Alert>}
      <TableContainer sx={{ maxHeight: 520 }}>
        <Table stickyHeader size="small" aria-label="Factures groupées émises">
          <TableHead>
            <TableRow>
              <TableCell>Numéro</TableCell>
              <TableCell>Date</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Client</TableCell>
              <TableCell>Période</TableCell>
              <TableCell align="right">Ventes</TableCell>
              <TableCell align="right">Net à payer</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {factures.data?.map((f) => {
              const magasin = magasins.data?.find((m) => m.code === f.magasin);
              return (
                <TableRow key={f.id}>
                  <TableCell>{f.numero}</TableCell>
                  <TableCell>{dateDocument(f.cree_le)}</TableCell>
                  <TableCell>{f.type_libelle}</TableCell>
                  <TableCell>{f.client_nom}</TableCell>
                  <TableCell>
                    {dateDocument(f.du)} au {dateDocument(f.au)}
                  </TableCell>
                  <TableCell align="right">{f.nombre_ventes}</TableCell>
                  <TableCell align="right">{formaterTexte(f.net_a_payer, monnaieDe(magasin))}</TableCell>
                  <TableCell>
                    <ImprimerFacture id={f.id} magasins={magasins.data} />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
      {factures.data?.length === 0 && <Typography color="text.secondary">Aucune facture groupée.</Typography>}
    </Stack>
  );
}

/**
 * Facturation groupée : une facture pour plusieurs visites (ou ventes comptoir) soldées d'un
 * même client ; au comptoir, une société sans fiche se facture à son nom.
 */
export function FacturationGroupee({ comptoir = false }: { comptoir?: boolean }) {
  const [onglet, setOnglet] = useState(0);
  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            {comptoir ? "Facturation des ventes comptoir" : "Facturation des visites"}
          </Typography>
          <Tabs value={onglet} onChange={(_, o: number) => setOnglet(o)}>
            <Tab label="Nouvelle facture" />
            <Tab label="Factures groupées émises" />
          </Tabs>
          {onglet === 0 ? <NouvelleFacture comptoir={comptoir} /> : <FacturesEmises />}
        </Stack>
      </CardContent>
    </Card>
  );
}

const moisPrecedent = () => {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
};

/**
 * Préparation de la facturation et clôture du mois : ce qui reste sans facture dans le mois, sa
 * TVA par taux ; la clôture l'inscrit sur une facture récapitulative et fige le mois.
 */
export function ClotureMois({ cloturer = false }: { cloturer?: boolean }) {
  const queryClient = useQueryClient();
  const magasins = useQuery({
    queryKey: ["magasins"],
    queryFn: listerMagasins,
  });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = magasins.data?.find((m) => m.id === magasinChoisi) ?? magasins.data?.[0];
  const monnaie = monnaieDe(magasin);
  const m = (v: string) => formaterTexte(v, monnaie);
  const [periode, setPeriode] = useState(moisPrecedent());
  const [annee, mois] = periode.split("-").map(Number);
  const [confirmation, setConfirmation] = useState(false);

  const preparation = useQuery({
    queryKey: ["cloture-mois", magasin?.id, annee, mois],
    queryFn: () => preparerCloture(magasin!.id, annee, mois),
    enabled: Boolean(magasin && annee && mois),
  });
  const clotures = useQuery({
    queryKey: ["clotures-mois"],
    queryFn: listerClotures,
  });
  const cloture = useMutation({
    mutationFn: () => cloturerMois(magasin!.id, annee, mois),
    onSuccess: () => {
      setConfirmation(false);
      void queryClient.invalidateQueries({ queryKey: ["cloture-mois"] });
      void queryClient.invalidateQueries({ queryKey: ["clotures-mois"] });
      void queryClient.invalidateQueries({ queryKey: ["factures-groupees"] });
    },
  });
  const p = preparation.data;

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            {cloturer ? "Clôture du mois" : "Préparation de la facturation"}
          </Typography>
          <Stack direction="row" spacing={2}>
            <ChoixMagasin magasins={magasins.data} valeur={magasin?.id ?? ""} onChange={setMagasin} />
            <TextField
              size="small"
              type="month"
              label="Mois"
              value={periode}
              onChange={(ev) => ev.target.value && setPeriode(ev.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </Stack>
          {preparation.isError && <Alert severity="error">{preparation.error.message}</Alert>}
          {p?.cloture && (
            <Alert
              severity="success"
              action={p.cloture.facture && <ImprimerFacture id={p.cloture.facture} magasins={magasins.data} />}
            >
              {libelleMois(p.annee, p.mois)} clôturé le {dateDocument(p.cloture.cree_le)} par {p.cloture.cloture_par}
              {p.cloture.facture_numero
                ? ` : facture récapitulative ${p.cloture.facture_numero}, ${m(p.cloture.total_ttc)}.`
                : " : toutes les ventes étaient déjà facturées."}
            </Alert>
          )}
          {p && !p.cloture && (
            <>
              <Typography>
                {p.ventes.length
                  ? `${p.ventes.length} ventes livrées en ${libelleMois(p.annee, p.mois)} sont encore sans facture : ${m(p.total_ttc)} TTC.`
                  : `Toutes les ventes de ${libelleMois(p.annee, p.mois)} sont facturées.`}
              </Typography>
              {p.detail_tva.length > 0 && <TableauTva detail={p.detail_tva} monnaie={monnaie} />}
              {p.ventes.length > 0 && (
                <TableContainer sx={{ maxHeight: 360 }}>
                  <Table stickyHeader size="small" aria-label="Ventes sans facture">
                    <TableHead>
                      <TableRow>
                        <TableCell>N°</TableCell>
                        <TableCell>Livrée le</TableCell>
                        <TableCell>Client</TableCell>
                        <TableCell align="right">Total TTC</TableCell>
                        <TableCell align="right">Reste dû</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {p.ventes.map((v) => (
                        <TableRow key={v.id}>
                          <TableCell>{v.numero}</TableCell>
                          <TableCell>{date(v.livree_le)}</TableCell>
                          <TableCell>{v.client ?? "Passage"}</TableCell>
                          <TableCell align="right">{m(v.total_ttc)}</TableCell>
                          <TableCell align="right">{Number(v.reste_a_payer) > 0 ? m(v.reste_a_payer) : ""}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
              {cloturer && (
                <Button variant="contained" sx={{ alignSelf: "flex-start" }} onClick={() => setConfirmation(true)}>
                  Clôturer {libelleMois(p.annee, p.mois)}
                </Button>
              )}
            </>
          )}
          {cloturer && (clotures.data?.length ?? 0) > 0 && (
            <>
              <Typography variant="subtitle1">Mois clôturés</Typography>
              <Table size="small" aria-label="Mois clôturés">
                <TableHead>
                  <TableRow>
                    <TableCell>Mois</TableCell>
                    <TableCell>Magasin</TableCell>
                    <TableCell>Clôturé le</TableCell>
                    <TableCell>Facture récapitulative</TableCell>
                    <TableCell align="right">Total TTC</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {clotures.data!.map((c) => (
                    <TableRow key={c.id}>
                      <TableCell>{libelleMois(c.annee, c.mois)}</TableCell>
                      <TableCell>{c.magasin_nom}</TableCell>
                      <TableCell>
                        {dateDocument(c.cree_le)} · {c.cloture_par}
                      </TableCell>
                      <TableCell>{c.facture_numero ?? "Aucune"}</TableCell>
                      <TableCell align="right">{m(c.total_ttc)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </>
          )}
        </Stack>
      </CardContent>
      {confirmation && p && (
        <Dialog open onClose={() => setConfirmation(false)}>
          <DialogTitle>Clôturer {libelleMois(p.annee, p.mois)} ?</DialogTitle>
          <DialogContent>
            <DialogContentText>
              {p.ventes.length
                ? `Les ${p.ventes.length} ventes sans facture passent sur une facture récapitulative « Clients divers » de ${m(p.total_ttc)}. `
                : ""}
              Ensuite, plus aucune facture ne pourra être faite sur une vente de ce mois. On ne peut pas revenir en
              arrière.
            </DialogContentText>
            {cloture.isError && <Alert severity="error">{cloture.error.message}</Alert>}
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setConfirmation(false)}>Annuler</Button>
            <Button variant="contained" disabled={cloture.isPending} onClick={() => cloture.mutate()}>
              Clôturer
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </Card>
  );
}
