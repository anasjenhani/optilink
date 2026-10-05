import Print from "@mui/icons-material/Print";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Checkbox from "@mui/material/Checkbox";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
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

import { emettreAvoir, lireAvoir, listerAvoirs, type Avoir } from "../api/avoirs";
import { trouverVente, type ModePaiement, type Vente } from "../api/caisse";
import { listerMagasins, type Magasin } from "../api/magasins";
import { formaterTexte, type Monnaie } from "../api/monnaie";
import { imprimer } from "./FactureAchat";
import { dateDocument, echapper, enteteDocument, LIBELLES_MODES, monnaieDu, Pages } from "./Factures";
import { useApaise } from "./RechercheClients";

const MODES: { valeur: ModePaiement; libelle: string }[] = [
  { valeur: "especes", libelle: "Espèces" },
  { valeur: "carte", libelle: "Carte bancaire" },
  { valeur: "cheque", libelle: "Chèque" },
];

type Reprise = { quantite: string; enStock: boolean };

/** Avoir client imprimable (A4), tel qu'émis : articles repris, totaux, remboursement. */
export function pageAvoir(a: Avoir, monnaie: Monnaie, magasin?: Magasin) {
  const m = (v: string) => formaterTexte(v, monnaie);
  const e = echapper;
  const lignes = a.lignes
    .map(
      (l) =>
        `<tr><td>${e(l.libelle)}</td><td class="n">${l.quantite}</td><td class="n">${Number(l.taux_tva).toFixed(2)}</td><td class="n">${m(l.total_ttc)}</td></tr>`,
    )
    .join("");
  const total = (libelle: string, valeur: string) => `<tr><td>${libelle}</td><td class="n">${m(valeur)}</td></tr>`;
  return `${enteteDocument(`Avoir ${a.numero}`, magasin)}
<p>Date : ${dateDocument(a.cree_le)} · ${a.annulation ? "Annulation" : "Reprise d'articles"} · Ticket : ${e(a.vente)}${a.facture ? ` · Facture : ${e(a.facture)}` : ""}</p>
${a.client ? `<p>Client : <strong>${e(a.client.nom)}</strong>${a.client.matricule_fiscal ? `<br>Matricule fiscal : ${e(a.client.matricule_fiscal)}` : ""}</p>` : ""}
<p>Motif : ${e(a.motif)}</p>
<table><thead><tr><th>Article</th><th class="n">Qté</th><th class="n">TVA %</th><th class="n">Total TTC</th></tr></thead><tbody>${lignes}</tbody></table>
<table class="totaux"><tbody>${total("Total HT", a.total_ht)}${total("Total TVA", a.total_tva)}<tr><th>Total TTC</th><th class="n">${m(a.total_ttc)}</th></tr>${total("Remboursé au client", a.montant_rembourse)}</tbody></table>
<p>Émis par ${e(a.emis_par)}${a.mode_remboursement ? ` · Remboursement : ${LIBELLES_MODES[a.mode_remboursement]}` : ""}</p>
</body></html>`;
}

/** Avoir émis, en lecture seule (document légal), avec réimpression. */
function DetailAvoir({ id, magasins, onFerme }: { id: string; magasins?: Magasin[]; onFerme: () => void }) {
  const avoir = useQuery({ queryKey: ["avoirs", id], queryFn: () => lireAvoir(id) });
  const a = avoir.data;
  const monnaie = monnaieDu(magasins, a?.magasin ?? "", a?.devise ?? "TND");
  const m = (v: string) => formaterTexte(v, monnaie);
  return (
    <Dialog open onClose={onFerme} maxWidth="md" fullWidth>
      <DialogTitle>{a ? `Avoir ${a.numero}` : "Avoir"}</DialogTitle>
      <DialogContent>
        {avoir.isError && <Alert severity="error">{avoir.error.message}</Alert>}
        {a && (
          <Stack spacing={2}>
            <Typography>
              {dateDocument(a.cree_le)} · {a.magasin} · {a.annulation ? "annulation" : "reprise d'articles"} · ticket{" "}
              {a.vente}
              {a.facture && ` · facture ${a.facture}`} · émis par {a.emis_par}
            </Typography>
            {a.client && <Typography>Client : {a.client.nom}</Typography>}
            <Typography>Motif : {a.motif}</Typography>
            <Table size="small" aria-label="Lignes de l'avoir">
              <TableHead>
                <TableRow>
                  <TableCell>Article</TableCell>
                  <TableCell align="right">Qté</TableCell>
                  <TableCell align="right">Total TTC</TableCell>
                  <TableCell>Remis en stock</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {a.lignes.map((l, i) => (
                  <TableRow key={i}>
                    <TableCell>{l.libelle}</TableCell>
                    <TableCell align="right">{l.quantite}</TableCell>
                    <TableCell align="right">{m(l.total_ttc)}</TableCell>
                    <TableCell>{l.remis_en_stock ? "Oui" : "Non"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Typography>
              Total HT {m(a.total_ht)} · TVA {m(a.total_tva)} · <strong>TTC {m(a.total_ttc)}</strong> · remboursé{" "}
              {m(a.montant_rembourse)}
              {a.mode_remboursement && ` (${LIBELLES_MODES[a.mode_remboursement]})`}
            </Typography>
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        {a && (
          <Button
            startIcon={<Print />}
            onClick={() =>
              imprimer(
                pageAvoir(
                  a,
                  monnaie,
                  magasins?.find((mg) => mg.code === a.magasin),
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

/** Avoirs déjà émis : consultation et réimpression ; ni modification ni suppression. */
function ListeAvoirs() {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [filtres, setFiltres] = useState({ numero: "", annulation: "" });
  const [page, setPage] = useState(1);
  const [ouvert, setOuvert] = useState<string | null>(null);
  const recherche = useApaise(filtres);
  const avoirs = useQuery({
    queryKey: ["avoirs", "liste", recherche, page],
    queryFn: () => listerAvoirs(recherche, page),
    placeholderData: keepPreviousData,
  });
  const filtrer = (changement: Partial<typeof filtres>) => {
    setFiltres((f) => ({ ...f, ...changement }));
    setPage(1);
  };
  const montant = (a: Avoir, valeur: string) => formaterTexte(valeur, monnaieDu(magasins.data, a.magasin, a.devise));

  return (
    <Stack spacing={1}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <TextField
          size="small"
          label="N° d'avoir"
          helperText="Numéro complet, par exemple T01-A2026-000001"
          value={filtres.numero}
          onChange={(e) => filtrer({ numero: e.target.value })}
          sx={{ flexGrow: 1 }}
        />
        <TextField
          select
          size="small"
          label="Type"
          value={filtres.annulation}
          onChange={(e) => filtrer({ annulation: e.target.value })}
          sx={{ minWidth: 200 }}
        >
          <MenuItem value="">Tous</MenuItem>
          <MenuItem value="false">Reprises d'articles</MenuItem>
          <MenuItem value="true">Annulations</MenuItem>
        </TextField>
      </Stack>
      {avoirs.isError && <Alert severity="error">{avoirs.error.message}</Alert>}
      <TableContainer sx={{ maxHeight: 520 }}>
        <Table stickyHeader size="small" aria-label="Avoirs émis">
          <TableHead>
            <TableRow>
              <TableCell>Numéro</TableCell>
              <TableCell>Date</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Ticket</TableCell>
              <TableCell>Client</TableCell>
              <TableCell>Magasin</TableCell>
              <TableCell align="right">Total TTC</TableCell>
              <TableCell align="right">Remboursé</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {avoirs.data?.results.map((a) => (
              <TableRow key={a.id} hover onClick={() => setOuvert(a.id)} sx={{ cursor: "pointer" }}>
                <TableCell>{a.numero}</TableCell>
                <TableCell>{dateDocument(a.cree_le)}</TableCell>
                <TableCell>{a.annulation ? "Annulation" : "Reprise"}</TableCell>
                <TableCell>{a.vente}</TableCell>
                <TableCell>{a.client?.nom ?? ""}</TableCell>
                <TableCell>{a.magasin}</TableCell>
                <TableCell align="right">{montant(a, a.total_ttc)}</TableCell>
                <TableCell align="right">{montant(a, a.montant_rembourse)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      {avoirs.data?.count === 0 && <Typography color="text.secondary">Aucun avoir.</Typography>}
      <Pages page={page} total={avoirs.data?.count ?? 0} onPage={setPage} />
      {ouvert && <DetailAvoir id={ouvert} magasins={magasins.data} onFerme={() => setOuvert(null)} />}
    </Stack>
  );
}

/**
 * Avoirs : émission (droit d'en émettre) et consultation des avoirs émis (droit de les voir).
 * Ce sont des documents légaux : jamais modifiés ni supprimés.
 */
export function Avoirs({ emettre = true, consulter = true }: { emettre?: boolean; consulter?: boolean }) {
  const [onglet, setOnglet] = useState(emettre ? 0 : 1);
  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Avoirs et annulations
          </Typography>
          {emettre && consulter && (
            <Tabs value={onglet} onChange={(_, o: number) => setOnglet(o)}>
              <Tab label="Émettre un avoir" />
              <Tab label="Avoirs émis" />
            </Tabs>
          )}
          {onglet === 0 ? <EmissionAvoir /> : <ListeAvoirs />}
        </Stack>
      </CardContent>
    </Card>
  );
}

/**
 * Émission d'un avoir : reprendre des articles d'une vente livrée, ou annuler une vente ou une
 * commande. Le client est remboursé de ce qu'il a versé ; les articles repris reviennent en stock.
 */
function EmissionAvoir() {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [numero, setNumero] = useState("");
  const [vente, setVente] = useState<Vente | null>(null);
  const [reprises, setReprises] = useState<Record<number, Reprise>>({});
  const [motif, setMotif] = useState("");
  const [mode, setMode] = useState<ModePaiement>("especes");
  const [avoir, setAvoir] = useState<Avoir | null>(null);

  const pays = magasins.data?.find((m) => vente?.numero.startsWith(`${m.code}-`))?.pays;
  const monnaie: Monnaie = { devise: vente?.devise ?? "TND", decimales: pays?.decimales ?? 3 };

  const recherchee = useMutation({
    mutationFn: () => trouverVente(numero.trim()),
    onSuccess: (trouvee) => {
      setVente(trouvee);
      setReprises({});
    },
  });
  const emission = useMutation({
    mutationFn: (annulation: boolean) => {
      const commun = { vente: vente!.id, motif, mode_remboursement: mode };
      if (annulation) return emettreAvoir({ ...commun, annulation: true });
      return emettreAvoir({
        ...commun,
        lignes: Object.entries(reprises)
          .filter(([, r]) => Number(r.quantite) > 0)
          .map(([ligne, r]) => ({ ligne: Number(ligne), quantite: Number(r.quantite), remis_en_stock: r.enStock })),
      });
    },
    onSuccess: (emis) => {
      setAvoir(emis);
      recherchee.mutate();
    },
  });

  function chercher(e: FormEvent) {
    e.preventDefault();
    setAvoir(null);
    recherchee.mutate();
  }

  const reprise = (id: number): Reprise => reprises[id] ?? { quantite: "", enStock: true };
  const modifier = (id: number, changement: Partial<Reprise>) =>
    setReprises((r) => ({ ...r, [id]: { ...reprise(id), ...changement } }));
  const aReprendre = Object.values(reprises).some((r) => Number(r.quantite) > 0);
  const enCommande = vente?.statut === "en_commande";

  return (
    <Stack spacing={2}>
      <Stack component="form" direction="row" spacing={2} onSubmit={chercher}>
        <TextField
          label="N° de ticket ou de commande"
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
      {avoir && (
        <Alert severity="success">
          Avoir {avoir.numero} : {formaterTexte(avoir.total_ttc, monnaie)} repris
          {Number(avoir.montant_rembourse) > 0
            ? `, ${formaterTexte(avoir.montant_rembourse, monnaie)} remboursé au client`
            : ", rien à rembourser"}
          .
        </Alert>
      )}

      {vente && (
        <>
          <Typography>
            {enCommande ? "Commande" : "Ticket"} {vente.numero} : {formaterTexte(vente.total_ttc, monnaie)}
            {vente.facture && ` · facture ${vente.facture}`}
          </Typography>
          {vente.statut === "annulee" && <Alert severity="info">Cette vente est annulée.</Alert>}
          {enCommande && (
            <Alert severity="info">
              Commande pas encore livrée : elle s'annule en entier, l'acompte est rendu au client.
            </Alert>
          )}
        </>
      )}

      {vente && vente.statut === "livree" && (
        <Table size="small" aria-label="Articles de la vente">
          <TableHead>
            <TableRow>
              <TableCell>Article</TableCell>
              <TableCell align="center">Vendu</TableCell>
              <TableCell align="center">Déjà repris</TableCell>
              <TableCell>À reprendre</TableCell>
              <TableCell>Remettre en stock</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {vente.lignes.map((ligne) => {
              const restante = ligne.quantite - ligne.quantite_reprise;
              return (
                <TableRow key={ligne.id}>
                  <TableCell>{ligne.libelle}</TableCell>
                  <TableCell align="center">{ligne.quantite}</TableCell>
                  <TableCell align="center">{ligne.quantite_reprise}</TableCell>
                  <TableCell>
                    <TextField
                      size="small"
                      type="number"
                      label={`Quantité ${ligne.libelle}`}
                      disabled={restante === 0}
                      value={reprise(ligne.id).quantite}
                      onChange={(e) => modifier(ligne.id, { quantite: e.target.value })}
                      slotProps={{ htmlInput: { min: 0, max: restante } }}
                      sx={{ width: 120 }}
                    />
                  </TableCell>
                  <TableCell>
                    <Checkbox
                      checked={reprise(ligne.id).enStock}
                      disabled={restante === 0}
                      onChange={(e) => modifier(ligne.id, { enStock: e.target.checked })}
                      slotProps={{ input: { "aria-label": `Remettre en stock ${ligne.libelle}` } }}
                    />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}

      {vente && vente.statut !== "annulee" && (
        <>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField label="Motif" value={motif} onChange={(e) => setMotif(e.target.value)} sx={{ flexGrow: 1 }} />
            <TextField
              select
              label="Remboursement"
              value={mode}
              onChange={(e) => setMode(e.target.value as ModePaiement)}
              sx={{ minWidth: 200 }}
            >
              {MODES.map((m) => (
                <MenuItem key={m.valeur} value={m.valeur}>
                  {m.libelle}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
          {emission.isError && <Alert severity="error">{emission.error.message}</Alert>}
          <Stack direction="row" spacing={2}>
            {!enCommande && (
              <Button
                variant="contained"
                disabled={!aReprendre || !motif.trim() || emission.isPending}
                onClick={() => emission.mutate(false)}
              >
                Émettre l'avoir
              </Button>
            )}
            <Button
              color="error"
              variant={enCommande ? "contained" : "outlined"}
              disabled={!motif.trim() || emission.isPending}
              onClick={() => emission.mutate(true)}
            >
              {enCommande ? "Annuler la commande" : "Annuler toute la vente"}
            </Button>
          </Stack>
        </>
      )}
    </Stack>
  );
}
