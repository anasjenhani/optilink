import Delete from "@mui/icons-material/Delete";
import Print from "@mui/icons-material/Print";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import IconButton from "@mui/material/IconButton";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableFooter from "@mui/material/TableFooter";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import type { Article } from "../api/caisse";
import { depotDabord, listerMagasins } from "../api/magasins";
import {
  envoyerTransfert,
  type FiltresTransferts,
  lireTransfert,
  listerTransferts,
  recevoirTransfert,
  annulerTransfert,
  type Transfert,
} from "../api/transferts";
import { AjoutArticle } from "./BonReception";
import { dateCourte, imprimer } from "./FactureAchat";
import { BANDEAU, BORDEAUX, BOUTON, useApaise } from "./RechercheClients";

const ENTETE = { color: BORDEAUX, fontWeight: 700, bgcolor: "grey.100", whiteSpace: "nowrap" } as const;

type Ligne = { article: Article; quantite: string };

function Bandeau({ titre }: { titre: string }) {
  return (
    <Box sx={{ px: 3, py: 1, borderRadius: 1, background: BANDEAU }}>
      <Typography variant="h5" component="h3" sx={{ color: "common.white", fontWeight: 500 }}>
        {titre}
      </Typography>
    </Box>
  );
}

/** Bon de transfert imprimable (A4), à joindre au colis. */
export function pageTransfert(t: Transfert) {
  const e = (texte: string) =>
    texte.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] as string);
  const lignes = t.lignes
    .map(
      (l) =>
        `<tr><td>${e(l.code_barres || l.reference)}</td><td>${e(l.libelle)}</td><td class="n">${l.quantite}</td><td></td></tr>`,
    )
    .join("");
  return `<!doctype html><html><head><meta charset="utf-8"><title>${e(t.numero)}</title><style>
@page { size: A4; margin: 12mm; }
body { font-family: Arial, sans-serif; font-size: 10pt; }
h1 { font-size: 16pt; margin: 0 0 4mm; }
table { border-collapse: collapse; width: 100%; margin: 3mm 0; }
th, td { border: 1px solid #999; padding: 1mm 1.5mm; }
th { background: #eee; text-align: left; }
.n { text-align: right; }
.signatures { display: flex; gap: 20mm; margin-top: 12mm; }
</style></head><body>
<h1>Bon de Transfert ${e(t.numero)}</h1>
<p>De : <strong>${e(t.magasin)}</strong> · Vers : <strong>${e(t.destination)}</strong> · Envoyé le ${dateCourte(t.cree_le)} par ${e(t.envoye_par)}</p>
<table><thead><tr><th>Code</th><th>Article</th><th class="n">Quantité</th><th>Reçu (✓)</th></tr></thead><tbody>${lignes}</tbody>
<tfoot><tr><th colspan="2">Total</th><th class="n">${t.total_articles ?? 0}</th><th></th></tr></tfoot></table>
${t.observation ? `<p>Observation : ${e(t.observation)}</p>` : ""}
<div class="signatures"><p>Signature départ :</p><p>Signature réception :</p></div>
</body></html>`;
}

/** « Bon Transfert » : le dépôt central envoie des articles de son stock à un magasin. */
export function TransfertStock() {
  const queryClient = useQueryClient();
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const liste = magasins.data ? depotDabord(magasins.data) : undefined;
  const [departChoisi, setDepart] = useState("");
  const depart = liste?.find((m) => m.id === departChoisi) ?? liste?.[0];
  const destinations = (liste ?? []).filter((m) => depart && m.id !== depart.id && m.societe_id === depart.societe_id);
  const [destinationChoisie, setDestination] = useState("");
  const destination = destinations.find((m) => m.id === destinationChoisie);
  const [lignes, setLignes] = useState<Ligne[]>([]);
  const [observation, setObservation] = useState("");
  const [envoye, setEnvoye] = useState<Transfert | null>(null);

  const ajouter = (article: Article) =>
    setLignes((ls) =>
      ls.some((l) => l.article.id === article.id)
        ? ls.map((l) => (l.article.id === article.id ? { ...l, quantite: String(Number(l.quantite) + 1) } : l))
        : [...ls, { article, quantite: "1" }],
    );
  const total = lignes.reduce((s, l) => s + (Number(l.quantite) || 0), 0);
  const manque = !depart
    ? "Aucun magasin de départ."
    : !destination
      ? "Choisissez le magasin destinataire."
      : lignes.length === 0
        ? "Ajoutez au moins un article."
        : lignes.some((l) => !(Number(l.quantite) >= 1))
          ? "Chaque ligne doit avoir une quantité."
          : lignes.find((l) => l.article.stock !== null && Number(l.quantite) > l.article.stock)
            ? "Quantité supérieure au stock du magasin de départ."
            : "";
  const envoi = useMutation({
    mutationFn: () =>
      envoyerTransfert({
        magasin: depart!.id,
        destination: destination!.id,
        observation,
        lignes: lignes.map((l) => ({ article: l.article.id, quantite: Number(l.quantite) })),
      }),
    onSuccess: (transfert) => {
      setEnvoye(transfert);
      setLignes([]);
      setObservation("");
      for (const cle of ["transferts", "articles"]) void queryClient.invalidateQueries({ queryKey: [cle] });
    },
  });

  return (
    <Stack spacing={1.5}>
      <Bandeau titre="Bon Transfert" />
      <Typography variant="body2" color="text.secondary">
        Les articles sortent du stock de départ à l'envoi et entrent dans le stock du magasin quand il réceptionne le
        transfert (Liste des Transferts › Réceptionner).
      </Typography>
      <Stack direction="row" spacing={1.5} useFlexGap sx={{ flexWrap: "wrap" }}>
        <TextField
          select
          size="small"
          label="Départ"
          value={depart?.id ?? ""}
          onChange={(e) => {
            setDepart(e.target.value);
            setLignes([]);
            setDestination("");
          }}
          sx={{ width: 240 }}
        >
          {(liste ?? []).map((m) => (
            <MenuItem key={m.id} value={m.id}>
              {m.nom}
              {m.type === "depot" ? " (dépôt central)" : ""}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          size="small"
          label="Vers le magasin"
          value={destination?.id ?? ""}
          onChange={(e) => setDestination(e.target.value)}
          sx={{ width: 240, bgcolor: "#fffde7" }}
          slotProps={{ select: { displayEmpty: true }, inputLabel: { shrink: true } }}
        >
          <MenuItem value="" disabled>
            Choisir
          </MenuItem>
          {destinations.map((m) => (
            <MenuItem key={m.id} value={m.id}>
              {m.nom}
            </MenuItem>
          ))}
        </TextField>
      </Stack>
      {depart && (
        <AjoutArticle
          magasin={depart.id}
          famille=""
          avecStock
          onAjoute={(a) => {
            setEnvoye(null);
            ajouter(a);
          }}
        />
      )}
      <TableContainer sx={{ border: 1, borderColor: "grey.400", borderRadius: 1 }}>
        <Table size="small" aria-label="Articles à transférer">
          <TableHead>
            <TableRow>
              <TableCell sx={ENTETE}>Code</TableCell>
              <TableCell sx={ENTETE}>Article</TableCell>
              <TableCell sx={ENTETE} align="right">
                Stock au départ
              </TableCell>
              <TableCell sx={ENTETE} align="right">
                Quantité
              </TableCell>
              <TableCell sx={ENTETE} />
            </TableRow>
          </TableHead>
          <TableBody>
            {lignes.map((l) => (
              <TableRow key={l.article.id}>
                <TableCell>{l.article.code_barres || l.article.reference}</TableCell>
                <TableCell>{l.article.libelle}</TableCell>
                <TableCell align="right">{l.article.stock ?? "—"}</TableCell>
                <TableCell align="right">
                  <TextField
                    size="small"
                    value={l.quantite}
                    error={l.article.stock !== null && Number(l.quantite) > l.article.stock}
                    onChange={(e) =>
                      setLignes((ls) =>
                        ls.map((x) => (x.article.id === l.article.id ? { ...x, quantite: e.target.value } : x)),
                      )
                    }
                    slotProps={{
                      htmlInput: { inputMode: "numeric", "aria-label": `Quantité ${l.article.libelle}` },
                    }}
                    sx={{ width: 80, "& input": { textAlign: "right", py: 0.5 } }}
                  />
                </TableCell>
                <TableCell padding="checkbox">
                  <IconButton
                    size="small"
                    aria-label={`Retirer ${l.article.libelle}`}
                    onClick={() => setLignes((ls) => ls.filter((x) => x.article.id !== l.article.id))}
                  >
                    <Delete fontSize="small" />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
          {lignes.length > 0 && (
            <TableFooter>
              <TableRow sx={{ "& td": { fontWeight: 700, color: "text.primary", bgcolor: "grey.100" } }}>
                <TableCell colSpan={3}>{lignes.length} article(s)</TableCell>
                <TableCell align="right">{total}</TableCell>
                <TableCell />
              </TableRow>
            </TableFooter>
          )}
        </Table>
        {lignes.length === 0 && (
          <Box sx={{ p: 2 }}>
            <Typography color="text.secondary">
              Ajoutez les articles à envoyer (code barre, référence, libellé).
            </Typography>
          </Box>
        )}
      </TableContainer>
      <TextField
        label="Observation"
        size="small"
        value={observation}
        onChange={(e) => setObservation(e.target.value)}
        sx={{ maxWidth: 700 }}
      />
      {envoi.isError && <Alert severity="error">{envoi.error.message}</Alert>}
      {envoye && (
        <Alert
          severity="success"
          action={
            <Button color="inherit" startIcon={<Print />} onClick={() => imprimer(pageTransfert(envoye))}>
              Imprimer
            </Button>
          }
        >
          Transfert {envoye.numero} envoyé à {envoye.destination} ({envoye.total_articles} article(s)). Il entrera dans
          son stock à la réception.
        </Alert>
      )}
      <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end", alignItems: "center" }}>
        {manque && lignes.length > 0 && (
          <Typography variant="body2" color="text.secondary">
            {manque}
          </Typography>
        )}
        <Button sx={BOUTON} onClick={() => setLignes([])} disabled={envoi.isPending}>
          Annuler
        </Button>
        <Button
          variant="contained"
          disabled={Boolean(manque) || envoi.isPending}
          onClick={() => {
            setEnvoye(null);
            envoi.mutate();
          }}
        >
          Envoyer
        </Button>
      </Stack>
    </Stack>
  );
}

/** Détail d'un transfert ; le magasin destinataire le réceptionne. */
function DetailTransfert({
  id,
  peutRecevoir,
  peutAnnuler,
  onFerme,
}: {
  id: string;
  peutRecevoir: (t: Transfert) => boolean;
  peutAnnuler: (t: Transfert) => boolean;
  onFerme: () => void;
}) {
  const queryClient = useQueryClient();
  const transfert = useQuery({ queryKey: ["transferts", id], queryFn: () => lireTransfert(id) });
  const reception = useMutation({
    mutationFn: () => recevoirTransfert(id),
    onSuccess: (t) => {
      queryClient.setQueryData(["transferts", id], t);
      for (const cle of ["transferts", "articles"]) void queryClient.invalidateQueries({ queryKey: [cle] });
    },
  });
  const [confirmer, setConfirmer] = useState(false);
  const annulation = useMutation({
    mutationFn: () => annulerTransfert(id),
    onSuccess: (t) => {
      setConfirmer(false);
      queryClient.setQueryData(["transferts", id], t);
      for (const cle of ["transferts", "articles"]) void queryClient.invalidateQueries({ queryKey: [cle] });
    },
  });
  const t = transfert.data;
  return (
    <Dialog open onClose={onFerme} maxWidth="md" fullWidth>
      <DialogTitle sx={{ color: BORDEAUX, fontWeight: 700 }}>{t ? `Transfert ${t.numero}` : "Transfert"}</DialogTitle>
      <DialogContent>
        {transfert.isError && <Alert severity="error">{transfert.error.message}</Alert>}
        {t && (
          <Stack spacing={1.5}>
            <Typography>
              De <strong>{t.magasin}</strong> vers <strong>{t.destination}</strong> · envoyé le{" "}
              {new Date(t.cree_le).toLocaleString("fr-FR")} par {t.envoye_par}
            </Typography>
            <Typography
              color={t.statut === "recu" ? "success.main" : t.statut === "annule" ? "text.secondary" : "warning.main"}
              sx={{ fontWeight: 700 }}
            >
              {t.statut === "recu"
                ? `Reçu le ${new Date(t.recu_le!).toLocaleString("fr-FR")} par ${t.recu_par}`
                : t.statut === "annule"
                  ? `Annulé le ${new Date(t.annule_le!).toLocaleString("fr-FR")} par ${t.annule_par} : les articles sont revenus au stock de départ.`
                  : "En route : pas encore réceptionné par le magasin."}
            </Typography>
            <Table size="small" aria-label="Articles du transfert">
              <TableHead>
                <TableRow>
                  <TableCell sx={ENTETE}>Code</TableCell>
                  <TableCell sx={ENTETE}>Article</TableCell>
                  <TableCell sx={ENTETE} align="right">
                    Quantité
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {t.lignes.map((l) => (
                  <TableRow key={l.article}>
                    <TableCell>{l.code_barres || l.reference}</TableCell>
                    <TableCell>{l.libelle}</TableCell>
                    <TableCell align="right">{l.quantite}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {t.observation && <Typography variant="body2">Observation : {t.observation}</Typography>}
            {reception.isError && <Alert severity="error">{reception.error.message}</Alert>}
            {annulation.isError && <Alert severity="error">{annulation.error.message}</Alert>}
            {confirmer && (
              <Alert
                severity="warning"
                action={
                  <Stack direction="row" spacing={1}>
                    <Button color="inherit" onClick={() => setConfirmer(false)}>
                      Non
                    </Button>
                    <Button
                      color="error"
                      variant="contained"
                      disabled={annulation.isPending}
                      onClick={() => annulation.mutate()}
                    >
                      Oui, annuler
                    </Button>
                  </Stack>
                }
              >
                Annuler ce transfert ? Les articles reviennent au stock de {t.magasin}.
              </Alert>
            )}
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        {t && (
          <Button startIcon={<Print />} onClick={() => imprimer(pageTransfert(t))}>
            Imprimer
          </Button>
        )}
        {t && t.statut === "envoye" && peutAnnuler(t) && !confirmer && (
          <Button color="error" onClick={() => setConfirmer(true)}>
            Annuler le transfert
          </Button>
        )}
        {t && t.statut === "envoye" && peutRecevoir(t) && (
          <Button variant="contained" disabled={reception.isPending} onClick={() => reception.mutate()}>
            Réceptionner
          </Button>
        )}
        <Button onClick={onFerme}>Fermer</Button>
      </DialogActions>
    </Dialog>
  );
}

/** « Liste des Transferts » : envoyés par le dépôt et à réceptionner par les magasins. */
export function ListeTransferts({ recevoir, annuler = false }: { recevoir: boolean; annuler?: boolean }) {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const mesMagasins = new Set((magasins.data ?? []).map((m) => m.id));
  const [filtres, setFiltres] = useState<FiltresTransferts>({});
  const [page, setPage] = useState(1);
  const [ouvert, setOuvert] = useState<string | null>(null);
  const recherche = useApaise(JSON.stringify(filtres));
  const transferts = useQuery({
    queryKey: ["transferts", "liste", recherche, page],
    queryFn: () => listerTransferts(JSON.parse(recherche) as FiltresTransferts, page),
    placeholderData: keepPreviousData,
  });
  const pages = Math.max(1, Math.ceil((transferts.data?.count ?? 0) / 50));
  const filtrer = (cle: keyof FiltresTransferts, valeur: string) => {
    setFiltres((f) => ({ ...f, [cle]: valeur }));
    setPage(1);
  };
  return (
    <Stack spacing={1}>
      <Bandeau titre="Liste des Transferts" />
      <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap" }}>
        <TextField
          size="small"
          label="Numéro"
          value={filtres.numero ?? ""}
          onChange={(e) => filtrer("numero", e.target.value)}
        />
        <TextField
          select
          size="small"
          label="Statut"
          value={filtres.statut ?? ""}
          onChange={(e) => filtrer("statut", e.target.value)}
          sx={{ width: 200 }}
          slotProps={{ select: { displayEmpty: true }, inputLabel: { shrink: true } }}
        >
          <MenuItem value="">Tous</MenuItem>
          <MenuItem value="envoye">En route</MenuItem>
          <MenuItem value="recu">Reçus</MenuItem>
          <MenuItem value="annule">Annulés</MenuItem>
        </TextField>
        <TextField
          size="small"
          type="date"
          label="Du"
          value={filtres.du ?? ""}
          onChange={(e) => filtrer("du", e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <TextField
          size="small"
          type="date"
          label="Au"
          value={filtres.au ?? ""}
          onChange={(e) => filtrer("au", e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
        />
      </Stack>
      {transferts.isError && <Alert severity="error">{transferts.error.message}</Alert>}
      <TableContainer sx={{ maxHeight: 520, border: 1, borderColor: "grey.400", borderRadius: 1 }}>
        <Table stickyHeader size="small" aria-label="Transferts">
          <TableHead>
            <TableRow>
              {["Numéro", "Envoyé le", "Départ", "Destination", "Articles", "Statut", "Envoyé par", "Reçu le"].map(
                (t) => (
                  <TableCell key={t} sx={ENTETE} align={t === "Articles" ? "right" : "left"}>
                    {t}
                  </TableCell>
                ),
              )}
            </TableRow>
          </TableHead>
          <TableBody>
            {transferts.data?.results.map((t) => (
              <TableRow
                key={t.id}
                hover
                onClick={() => setOuvert(t.id)}
                sx={{ cursor: "pointer", "& td": { whiteSpace: "nowrap" } }}
              >
                <TableCell>{t.numero}</TableCell>
                <TableCell>{dateCourte(t.cree_le)}</TableCell>
                <TableCell>{t.magasin}</TableCell>
                <TableCell>{t.destination}</TableCell>
                <TableCell align="right">{t.total_articles ?? 0}</TableCell>
                <TableCell
                  sx={{
                    color:
                      t.statut === "recu" ? "success.main" : t.statut === "annule" ? "text.secondary" : "warning.main",
                    fontWeight: 600,
                  }}
                >
                  {t.statut === "recu" ? "Reçu" : t.statut === "annule" ? "Annulé" : "En route"}
                </TableCell>
                <TableCell>{t.envoye_par}</TableCell>
                <TableCell>{t.recu_le ? dateCourte(t.recu_le) : ""}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {transferts.data?.count === 0 && (
          <Box sx={{ p: 2 }}>
            <Typography color="text.secondary">Aucun transfert.</Typography>
          </Box>
        )}
      </TableContainer>
      {pages > 1 && (
        <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end", alignItems: "center" }}>
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
      {ouvert && (
        <DetailTransfert
          id={ouvert}
          peutRecevoir={(t) => recevoir && mesMagasins.has(t.destination_id)}
          peutAnnuler={(t) => annuler && mesMagasins.has(t.magasin_id)}
          onFerme={() => setOuvert(null)}
        />
      )}
    </Stack>
  );
}
