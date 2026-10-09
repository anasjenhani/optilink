import Delete from "@mui/icons-material/Delete";
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
import FormControlLabel from "@mui/material/FormControlLabel";
import IconButton from "@mui/material/IconButton";
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

import { FAMILLES, type Article, type Famille } from "../api/caisse";
import { listerMagasins, type Magasin } from "../api/magasins";
import { formaterTexte } from "../api/monnaie";
import {
  annulerDemande,
  demanderTransfert,
  listerBonsSortie,
  listerDemandes,
  lirePeremptions,
  lireStockADate,
  proposerReassort,
  refuserDemande,
  servirDemande,
  sortirDuStock,
  type BonSortie as Bon,
  type DemandeTransfert,
  type EtatPeremption,
  type TypeSortie,
} from "../api/sorties";
import { AjoutArticle } from "./BonReception";
import { dateCourte, imprimer } from "./FactureAchat";
import { echapper } from "./Factures";
import { useApaise } from "./RechercheClients";

type Ligne = { article: Article; quantite: string };

const jourIso = (d: Date) => d.toLocaleDateString("en-CA");
const ilYA = (jours: number) => {
  const d = new Date();
  d.setDate(d.getDate() - jours);
  return jourIso(d);
};

const STYLE = `<style>
@page { size: A4; margin: 12mm; }
body { font-family: Arial, sans-serif; font-size: 10pt; }
h1 { font-size: 16pt; margin: 0 0 4mm; }
table { border-collapse: collapse; width: 100%; margin: 3mm 0; }
th, td { border: 1px solid #999; padding: 1mm 1.5mm; }
th { background: #eee; text-align: left; }
.n { text-align: right; }
</style>`;

function pageBonSortie(b: Bon) {
  const e = echapper;
  const lignes = b.lignes
    .map((l) => `<tr><td>${e(l.reference)}</td><td>${e(l.libelle)}</td><td class="n">${l.quantite}</td></tr>`)
    .join("");
  return `<!doctype html><html><head><meta charset="utf-8"><title>${e(b.numero)}</title>${STYLE}</head><body>
<h1>${e(b.type_libelle)} ${e(b.numero)}</h1>
<p>${e(b.magasin)} · ${dateCourte(b.cree_le)} · par ${e(b.cree_par)}</p>
<p>Motif : <strong>${e(b.motif)}</strong>${b.observation ? `<br>${e(b.observation)}` : ""}</p>
<table><thead><tr><th>Référence</th><th>Article</th><th class="n">Quantité</th></tr></thead><tbody>${lignes}</tbody>
<tfoot><tr><th colspan="2">Total</th><th class="n">${b.total_articles}</th></tr></tfoot></table>
<p>Signature :</p>
</body></html>`;
}

function ChoixMagasin({
  label,
  magasins,
  valeur,
  onChange,
}: {
  label: string;
  magasins: Magasin[];
  valeur: string;
  onChange: (id: string) => void;
}) {
  return (
    <TextField
      select
      size="small"
      label={label}
      value={valeur}
      onChange={(ev) => onChange(ev.target.value)}
      sx={{ minWidth: 220 }}
    >
      {magasins.map((m) => (
        <MenuItem key={m.id} value={m.id}>
          {m.nom}
          {m.type === "depot" ? " (dépôt central)" : ""}
        </MenuItem>
      ))}
    </TextField>
  );
}

/** Articles choisis avec leur quantité, ajoutés par code barre, référence ou libellé. */
function SaisieLignes({
  magasin,
  lignes,
  onChange,
  avecStock,
}: {
  magasin: string;
  lignes: Ligne[];
  onChange: (lignes: Ligne[]) => void;
  avecStock: boolean;
}) {
  const ajouter = (article: Article) =>
    onChange(
      lignes.some((l) => l.article.id === article.id)
        ? lignes.map((l) => (l.article.id === article.id ? { ...l, quantite: String(Number(l.quantite) + 1) } : l))
        : [...lignes, { article, quantite: "1" }],
    );
  return (
    <>
      <AjoutArticle magasin={magasin} famille="" avecStock={avecStock} onAjoute={ajouter} />
      {lignes.length > 0 && (
        <Table size="small" aria-label="Articles">
          <TableHead>
            <TableRow>
              <TableCell>Code</TableCell>
              <TableCell>Article</TableCell>
              {avecStock && <TableCell align="right">Stock</TableCell>}
              <TableCell align="right">Quantité</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {lignes.map((l) => (
              <TableRow key={l.article.id}>
                <TableCell>{l.article.code_barres || l.article.reference}</TableCell>
                <TableCell>{l.article.libelle}</TableCell>
                {avecStock && <TableCell align="right">{l.article.stock ?? "—"}</TableCell>}
                <TableCell align="right">
                  <TextField
                    size="small"
                    value={l.quantite}
                    error={avecStock && l.article.stock !== null && Number(l.quantite) > l.article.stock}
                    onChange={(ev) =>
                      onChange(
                        lignes.map((x) => (x.article.id === l.article.id ? { ...x, quantite: ev.target.value } : x)),
                      )
                    }
                    slotProps={{ htmlInput: { inputMode: "numeric", "aria-label": `Quantité ${l.article.libelle}` } }}
                    sx={{ width: 80, "& input": { textAlign: "right", py: 0.5 } }}
                  />
                </TableCell>
                <TableCell padding="checkbox">
                  <IconButton
                    size="small"
                    aria-label={`Retirer ${l.article.libelle}`}
                    onClick={() => onChange(lignes.filter((x) => x.article.id !== l.article.id))}
                  >
                    <Delete fontSize="small" />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </>
  );
}

const lignesValides = (lignes: Ligne[]) => lignes.length > 0 && lignes.every((l) => Number(l.quantite) >= 1);
const versSaisie = (lignes: Ligne[]) => lignes.map((l) => ({ article: l.article.id, quantite: Number(l.quantite) }));

/**
 * Bon de sortie (usage interne, cadeau, échantillon…) ou sortie casse : les articles sortent du
 * stock du magasin dès la validation, avec un bon numéroté et imprimable.
 */
export function BonSortie({ casse = false }: { casse?: boolean }) {
  const type: TypeSortie = casse ? "casse" : "sortie";
  const queryClient = useQueryClient();
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = magasins.data?.find((m) => m.id === magasinChoisi) ?? magasins.data?.[0];
  const [lignes, setLignes] = useState<Ligne[]>([]);
  const [motif, setMotif] = useState("");
  const [observation, setObservation] = useState("");
  const [fait, setFait] = useState<Bon | null>(null);
  const bons = useQuery({ queryKey: ["bons-sortie", type], queryFn: () => listerBonsSortie(type) });
  const sortie = useMutation({
    mutationFn: () => sortirDuStock({ magasin: magasin!.id, type, motif, observation, lignes: versSaisie(lignes) }),
    onSuccess: (bon) => {
      setFait(bon);
      setLignes([]);
      setMotif("");
      setObservation("");
      for (const cle of ["bons-sortie", "articles"]) void queryClient.invalidateQueries({ queryKey: [cle] });
    },
  });
  const trop = lignes.some((l) => l.article.stock !== null && Number(l.quantite) > l.article.stock);

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            {casse ? "Bon de sortie casse" : "Bon de sortie"}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {casse
              ? "Articles cassés, défectueux ou perdus : ils sortent du stock à la validation."
              : "Articles sortis sans vente (usage interne, cadeau, échantillon…) : ils sortent du stock à la validation."}
          </Typography>
          <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap" }}>
            {(magasins.data?.length ?? 0) > 1 && (
              <ChoixMagasin
                label="Magasin"
                magasins={magasins.data!}
                valeur={magasin?.id ?? ""}
                onChange={(id) => {
                  setMagasin(id);
                  setLignes([]);
                }}
              />
            )}
            <TextField
              size="small"
              label="Motif"
              value={motif}
              onChange={(ev) => setMotif(ev.target.value)}
              sx={{ minWidth: 320 }}
            />
          </Stack>
          {magasin && <SaisieLignes magasin={magasin.id} lignes={lignes} onChange={setLignes} avecStock />}
          <TextField
            size="small"
            label="Observation"
            value={observation}
            onChange={(ev) => setObservation(ev.target.value)}
          />
          {sortie.isError && <Alert severity="error">{sortie.error.message}</Alert>}
          {fait && (
            <Alert
              severity="success"
              action={
                <Button color="inherit" startIcon={<Print />} onClick={() => imprimer(pageBonSortie(fait))}>
                  Imprimer
                </Button>
              }
            >
              {fait.type_libelle} {fait.numero} : {fait.total_articles} article(s) sorti(s) du stock.
            </Alert>
          )}
          <Button
            variant="contained"
            sx={{ alignSelf: "flex-end" }}
            disabled={!motif.trim() || !lignesValides(lignes) || trop || sortie.isPending}
            onClick={() => {
              setFait(null);
              sortie.mutate();
            }}
          >
            Valider la sortie
          </Button>
          {(bons.data?.length ?? 0) > 0 && (
            <>
              <Typography variant="subtitle1">Derniers bons</Typography>
              <Table size="small" aria-label="Derniers bons">
                <TableHead>
                  <TableRow>
                    <TableCell>Numéro</TableCell>
                    <TableCell>Date</TableCell>
                    <TableCell>Magasin</TableCell>
                    <TableCell>Motif</TableCell>
                    <TableCell align="right">Articles</TableCell>
                    <TableCell />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {bons.data!.map((b) => (
                    <TableRow key={b.id}>
                      <TableCell>{b.numero}</TableCell>
                      <TableCell>{dateCourte(b.cree_le)}</TableCell>
                      <TableCell>{b.magasin}</TableCell>
                      <TableCell>{b.motif}</TableCell>
                      <TableCell align="right">{b.total_articles}</TableCell>
                      <TableCell>
                        <IconButton
                          size="small"
                          aria-label={`Imprimer ${b.numero}`}
                          onClick={() => imprimer(pageBonSortie(b))}
                        >
                          <Print fontSize="small" />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}

function NouvelleDemande({ alimentation }: { alimentation: boolean }) {
  const queryClient = useQueryClient();
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const tous = magasins.data ?? [];
  const miens = tous.filter((m) => m.type !== "depot");
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = (miens.length ? miens : tous).find((m) => m.id === magasinChoisi) ?? miens[0] ?? tous[0];
  const possibles = tous.filter(
    (m) =>
      magasin && m.id !== magasin.id && m.societe_id === magasin.societe_id && (!alimentation || m.type === "depot"),
  );
  const [aupresChoisi, setAupres] = useState("");
  const aupres = possibles.find((m) => m.id === aupresChoisi) ?? (alimentation ? possibles[0] : undefined);
  const [lignes, setLignes] = useState<Ligne[]>([]);
  const [observation, setObservation] = useState("");
  const [faite, setFaite] = useState<DemandeTransfert | null>(null);
  const demande = useMutation({
    mutationFn: () =>
      demanderTransfert({ magasin: magasin!.id, aupres_de: aupres!.id, observation, lignes: versSaisie(lignes) }),
    onSuccess: (d) => {
      setFaite(d);
      setLignes([]);
      setObservation("");
      void queryClient.invalidateQueries({ queryKey: ["demandes-transfert"] });
    },
  });

  return (
    <Stack spacing={2}>
      <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap" }}>
        {(miens.length > 1 || !miens.length) && tous.length > 1 && (
          <ChoixMagasin
            label="Magasin qui demande"
            magasins={miens.length ? miens : tous}
            valeur={magasin?.id ?? ""}
            onChange={setMagasin}
          />
        )}
        <ChoixMagasin
          label={alimentation ? "Dépôt" : "Demander à"}
          magasins={possibles}
          valeur={aupres?.id ?? ""}
          onChange={setAupres}
        />
      </Stack>
      {alimentation && possibles.length === 0 && magasins.isSuccess && (
        <Alert severity="info">Aucun dépôt central dans cette société.</Alert>
      )}
      {magasin && <SaisieLignes magasin={magasin.id} lignes={lignes} onChange={setLignes} avecStock={false} />}
      <TextField
        size="small"
        label="Observation"
        value={observation}
        onChange={(ev) => setObservation(ev.target.value)}
      />
      {demande.isError && <Alert severity="error">{demande.error.message}</Alert>}
      {faite && (
        <Alert severity="success">
          Demande {faite.numero} envoyée à {faite.aupres_de}. Elle arrivera en transfert quand elle sera servie.
        </Alert>
      )}
      <Button
        variant="contained"
        sx={{ alignSelf: "flex-end" }}
        disabled={!aupres || !lignesValides(lignes) || demande.isPending}
        onClick={() => {
          setFaite(null);
          demande.mutate();
        }}
      >
        Envoyer la demande
      </Button>
    </Stack>
  );
}

function DetailDemande({
  demande: d,
  servir,
  onFermer,
}: {
  demande: DemandeTransfert;
  servir: boolean;
  onFermer: () => void;
}) {
  const queryClient = useQueryClient();
  const [quantites, setQuantites] = useState<Record<string, string>>(
    Object.fromEntries(d.lignes.map((l) => [l.article, String(l.quantite)])),
  );
  const [motif, setMotif] = useState("");
  const apres = {
    onSuccess: () => {
      for (const cle of ["demandes-transfert", "transferts", "articles"])
        void queryClient.invalidateQueries({ queryKey: [cle] });
      onFermer();
    },
  };
  const service = useMutation({
    mutationFn: () =>
      servirDemande(
        d.id,
        d.lignes.map((l) => ({ article: l.article, quantite: Number(quantites[l.article]) || 0 })),
      ),
    ...apres,
  });
  const refus = useMutation({ mutationFn: () => refuserDemande(d.id, motif), ...apres });
  const retrait = useMutation({ mutationFn: () => annulerDemande(d.id), ...apres });
  const enAttente = d.statut === "en_attente";
  const erreur = service.error ?? refus.error ?? retrait.error;

  return (
    <Dialog open onClose={onFermer} fullWidth maxWidth="md">
      <DialogTitle>Demande {d.numero}</DialogTitle>
      <DialogContent>
        <Stack spacing={2}>
          <Typography>
            {d.magasin} demande à {d.aupres_de} · {dateCourte(d.cree_le)} par {d.demandee_par} · {d.statut_libelle}
            {d.transfert && ` · transfert ${d.transfert}`}
            {d.motif_refus && ` · refusée : ${d.motif_refus}`}
          </Typography>
          {d.observation && <Typography color="text.secondary">{d.observation}</Typography>}
          <Table size="small" aria-label="Articles demandés">
            <TableHead>
              <TableRow>
                <TableCell>Référence</TableCell>
                <TableCell>Article</TableCell>
                <TableCell align="right">Demandé</TableCell>
                <TableCell align="right">{enAttente && servir ? "À envoyer" : "Envoyé"}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {d.lignes.map((l) => (
                <TableRow key={l.article}>
                  <TableCell>{l.reference}</TableCell>
                  <TableCell>{l.libelle}</TableCell>
                  <TableCell align="right">{l.quantite}</TableCell>
                  <TableCell align="right">
                    {enAttente && servir ? (
                      <TextField
                        size="small"
                        value={quantites[l.article]}
                        onChange={(ev) => setQuantites({ ...quantites, [l.article]: ev.target.value })}
                        slotProps={{ htmlInput: { inputMode: "numeric", "aria-label": `Envoyer ${l.libelle}` } }}
                        sx={{ width: 80, "& input": { textAlign: "right", py: 0.5 } }}
                      />
                    ) : (
                      l.quantite_servie
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {enAttente && servir && (
            <TextField size="small" label="Motif du refus" value={motif} onChange={(ev) => setMotif(ev.target.value)} />
          )}
          {erreur && <Alert severity="error">{erreur.message}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        {enAttente && !servir && (
          <Button color="error" disabled={retrait.isPending} onClick={() => retrait.mutate()}>
            Retirer la demande
          </Button>
        )}
        {enAttente && servir && (
          <>
            <Button color="error" disabled={!motif.trim() || refus.isPending} onClick={() => refus.mutate()}>
              Refuser
            </Button>
            <Button variant="contained" disabled={service.isPending} onClick={() => service.mutate()}>
              Servir (envoyer le transfert)
            </Button>
          </>
        )}
        <Button onClick={onFermer}>Fermer</Button>
      </DialogActions>
    </Dialog>
  );
}

function ListeDemandes({ sens, servir }: { sens: "recues" | "envoyees"; servir: boolean }) {
  const demandes = useQuery({ queryKey: ["demandes-transfert", sens], queryFn: () => listerDemandes(sens) });
  const [ouverte, setOuverte] = useState<DemandeTransfert | null>(null);
  return (
    <Stack spacing={1}>
      {demandes.isError && <Alert severity="error">{demandes.error.message}</Alert>}
      {demandes.data?.length === 0 && <Typography color="text.secondary">Aucune demande.</Typography>}
      {(demandes.data?.length ?? 0) > 0 && (
        <TableContainer sx={{ maxHeight: 520 }}>
          <Table stickyHeader size="small" aria-label={sens === "recues" ? "Demandes reçues" : "Mes demandes"}>
            <TableHead>
              <TableRow>
                <TableCell>Numéro</TableCell>
                <TableCell>Date</TableCell>
                <TableCell>Demandeur</TableCell>
                <TableCell>Auprès de</TableCell>
                <TableCell align="right">Articles</TableCell>
                <TableCell>Statut</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {demandes.data!.map((d) => (
                <TableRow key={d.id} hover sx={{ cursor: "pointer" }} onClick={() => setOuverte(d)}>
                  <TableCell>{d.numero}</TableCell>
                  <TableCell>{dateCourte(d.cree_le)}</TableCell>
                  <TableCell>{d.magasin}</TableCell>
                  <TableCell>{d.aupres_de}</TableCell>
                  <TableCell align="right">{d.lignes.reduce((s, l) => s + l.quantite, 0)}</TableCell>
                  <TableCell>{d.statut_libelle}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      {ouverte && <DetailDemande demande={ouverte} servir={servir} onFermer={() => setOuverte(null)} />}
    </Stack>
  );
}

/**
 * Demandes de transfert : un magasin demande des articles à un autre ; au dépôt central, c'est
 * une demande d'alimentation. Le magasin sollicité la sert par un transfert, ou la refuse.
 */
export function DemandesTransfert({
  alimentation = false,
  demander = true,
  servir = false,
}: {
  alimentation?: boolean;
  demander?: boolean;
  servir?: boolean;
}) {
  const onglets = [
    ...(demander ? [{ cle: "nouvelle", libelle: "Nouvelle demande" }] : []),
    { cle: "envoyees", libelle: "Mes demandes" },
    ...(servir ? [{ cle: "recues", libelle: "Demandes à servir" }] : []),
  ];
  const [onglet, setOnglet] = useState(0);
  const cle = onglets[onglet]?.cle ?? "envoyees";
  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            {alimentation ? "Demande d'alimentation" : "Demande de transfert"}
          </Typography>
          <Tabs value={onglet} onChange={(_, o: number) => setOnglet(o)}>
            {onglets.map((o) => (
              <Tab key={o.cle} label={o.libelle} />
            ))}
          </Tabs>
          {cle === "nouvelle" && <NouvelleDemande alimentation={alimentation} />}
          {cle === "envoyees" && <ListeDemandes sens="envoyees" servir={false} />}
          {cle === "recues" && <ListeDemandes sens="recues" servir />}
        </Stack>
      </CardContent>
    </Card>
  );
}

/**
 * Réassort : ce que le magasin a vendu sur la période, son stock et celui du dépôt ; les
 * quantités proposées (modifiables) partent en demande d'alimentation au dépôt.
 */
export function Reassort() {
  const queryClient = useQueryClient();
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const tous = magasins.data ?? [];
  const miens = tous.filter((m) => m.type !== "depot");
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = miens.find((m) => m.id === magasinChoisi) ?? miens[0];
  const depot = tous.find((m) => m.type === "depot" && magasin && m.societe_id === magasin.societe_id);
  const [du, setDu] = useState(ilYA(30));
  const [au, setAu] = useState(jourIso(new Date()));
  const [famille, setFamille] = useState<Famille | "">("");
  const [quantites, setQuantites] = useState<Record<string, string>>({});
  const proposition = useQuery({
    queryKey: ["reassort", magasin?.id, du, au, famille],
    queryFn: () => proposerReassort({ magasin: magasin!.id, du, au, famille }),
    enabled: Boolean(magasin && du && au),
  });
  const quantite = (article: string, propose: number) => quantites[article] ?? String(propose);
  const lignes = (proposition.data ?? [])
    .map((l) => ({ article: l.article, quantite: Number(quantite(l.article, l.propose)) || 0 }))
    .filter((l) => l.quantite > 0);
  const demande = useMutation({
    mutationFn: () =>
      demanderTransfert({
        magasin: magasin!.id,
        aupres_de: depot!.id,
        observation: `Réassort du ${du} au ${au}`,
        lignes,
      }),
    onSuccess: () => {
      setQuantites({});
      void queryClient.invalidateQueries({ queryKey: ["demandes-transfert"] });
    },
  });

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Réassort
          </Typography>
          <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap" }}>
            {miens.length > 1 && (
              <ChoixMagasin label="Magasin" magasins={miens} valeur={magasin?.id ?? ""} onChange={setMagasin} />
            )}
            <TextField
              size="small"
              type="date"
              label="Ventes du"
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
            <TextField
              select
              size="small"
              label="Famille"
              value={famille}
              onChange={(ev) => setFamille(ev.target.value as Famille | "")}
              sx={{ minWidth: 160 }}
            >
              <MenuItem value="">Toutes</MenuItem>
              {FAMILLES.map((f) => (
                <MenuItem key={f.valeur} value={f.valeur}>
                  {f.libelle}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
          {proposition.isError && <Alert severity="error">{proposition.error.message}</Alert>}
          {proposition.data?.length === 0 && (
            <Typography color="text.secondary">Rien de vendu sur la période.</Typography>
          )}
          {(proposition.data?.length ?? 0) > 0 && (
            <TableContainer sx={{ maxHeight: 480 }}>
              <Table stickyHeader size="small" aria-label="Réassort">
                <TableHead>
                  <TableRow>
                    <TableCell>Référence</TableCell>
                    <TableCell>Article</TableCell>
                    <TableCell align="right">Vendu</TableCell>
                    <TableCell align="right">Stock magasin</TableCell>
                    <TableCell align="right">Stock dépôt</TableCell>
                    <TableCell align="right">À demander</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {proposition.data!.map((l) => (
                    <TableRow key={l.article}>
                      <TableCell>{l.reference}</TableCell>
                      <TableCell>{l.libelle}</TableCell>
                      <TableCell align="right">{l.vendu}</TableCell>
                      <TableCell align="right">{l.stock}</TableCell>
                      <TableCell align="right">{l.stock_depot ?? "—"}</TableCell>
                      <TableCell align="right">
                        <TextField
                          size="small"
                          value={quantite(l.article, l.propose)}
                          onChange={(ev) => setQuantites({ ...quantites, [l.article]: ev.target.value })}
                          slotProps={{ htmlInput: { inputMode: "numeric", "aria-label": `Demander ${l.libelle}` } }}
                          sx={{ width: 80, "& input": { textAlign: "right", py: 0.5 } }}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
          {!depot && magasins.isSuccess && <Alert severity="info">Aucun dépôt central à qui demander.</Alert>}
          {demande.isError && <Alert severity="error">{demande.error.message}</Alert>}
          {demande.isSuccess && (
            <Alert severity="success">
              Demande d'alimentation {demande.data.numero} envoyée au {demande.data.aupres_de}.
            </Alert>
          )}
          <Button
            variant="contained"
            sx={{ alignSelf: "flex-end" }}
            disabled={!depot || lignes.length === 0 || demande.isPending}
            onClick={() => demande.mutate()}
          >
            Demander au dépôt ({lignes.reduce((s, l) => s + l.quantite, 0)} articles)
          </Button>
        </Stack>
      </CardContent>
    </Card>
  );
}

/** Stock d'un magasin tel qu'il était à la fin d'un jour donné, avec sa valeur d'achat. */
export function StockALaDate() {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = magasins.data?.find((m) => m.id === magasinChoisi) ?? magasins.data?.[0];
  const [date, setDate] = useState(jourIso(new Date()));
  const [famille, setFamille] = useState<Famille | "">("");
  const [saisie, setSaisie] = useState("");
  const recherche = useApaise(saisie);
  const stock = useQuery({
    queryKey: ["stock-a-date", magasin?.id, date, famille, recherche],
    queryFn: () => lireStockADate({ magasin: magasin!.id, date, famille, recherche }),
    enabled: Boolean(magasin && date),
  });
  const monnaie = { devise: magasin?.pays.devise ?? "TND", decimales: magasin?.pays.decimales ?? 3 };
  const s = stock.data;
  const imprimerStock = () => {
    const e = echapper;
    const lignes = s!.lignes
      .map(
        (l) =>
          `<tr><td>${e(l.reference)}</td><td>${e(l.libelle)}</td><td class="n">${l.quantite}</td><td class="n">${l.valeur_achat ? formaterTexte(l.valeur_achat, monnaie) : ""}</td></tr>`,
      )
      .join("");
    imprimer(`<!doctype html><html><head><meta charset="utf-8"><title>Stock</title>${STYLE}</head><body>
<h1>Stock au ${dateCourte(s!.date)} · ${e(s!.magasin)}</h1>
<table><thead><tr><th>Référence</th><th>Article</th><th class="n">Quantité</th><th class="n">Valeur d'achat HT</th></tr></thead><tbody>${lignes}</tbody>
<tfoot><tr><th colspan="2">${s!.articles} articles</th><th class="n">${s!.quantite}</th><th class="n">${formaterTexte(s!.valeur_achat, monnaie)}</th></tr></tfoot></table>
</body></html>`);
  };

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Stock à la date
          </Typography>
          <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap" }}>
            {(magasins.data?.length ?? 0) > 1 && (
              <ChoixMagasin
                label="Magasin"
                magasins={magasins.data!}
                valeur={magasin?.id ?? ""}
                onChange={setMagasin}
              />
            )}
            <TextField
              size="small"
              type="date"
              label="Date"
              value={date}
              onChange={(ev) => setDate(ev.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <TextField
              select
              size="small"
              label="Famille"
              value={famille}
              onChange={(ev) => setFamille(ev.target.value as Famille | "")}
              sx={{ minWidth: 160 }}
            >
              <MenuItem value="">Toutes</MenuItem>
              {FAMILLES.map((f) => (
                <MenuItem key={f.valeur} value={f.valeur}>
                  {f.libelle}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              size="small"
              label="Article"
              helperText="Référence ou libellé"
              value={saisie}
              onChange={(ev) => setSaisie(ev.target.value)}
            />
            {s && s.lignes.length > 0 && (
              <Button startIcon={<Print />} onClick={imprimerStock}>
                Imprimer
              </Button>
            )}
          </Stack>
          {stock.isError && <Alert severity="error">{stock.error.message}</Alert>}
          {s && (
            <Typography>
              {s.articles} articles · {s.quantite} pièces · valeur d'achat {formaterTexte(s.valeur_achat, monnaie)} HT
            </Typography>
          )}
          {s && s.lignes.length > 0 && (
            <TableContainer sx={{ maxHeight: 520 }}>
              <Table stickyHeader size="small" aria-label="Stock à la date">
                <TableHead>
                  <TableRow>
                    <TableCell>Référence</TableCell>
                    <TableCell>Article</TableCell>
                    <TableCell align="right">Quantité</TableCell>
                    <TableCell align="right">Valeur d'achat HT</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {s.lignes.map((l) => (
                    <TableRow key={l.article}>
                      <TableCell>{l.reference}</TableCell>
                      <TableCell>{l.libelle}</TableCell>
                      <TableCell align="right">{l.quantite}</TableCell>
                      <TableCell align="right">
                        {l.valeur_achat ? formaterTexte(l.valeur_achat, monnaie) : "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}

const ETATS_PEREMPTION: Record<EtatPeremption, { libelle: string; couleur: string }> = {
  perimee: { libelle: "Périmée", couleur: "error.main" },
  proche: { libelle: "Bientôt", couleur: "warning.main" },
  inconnue: { libelle: "À dater", couleur: "text.secondary" },
  ok: { libelle: "", couleur: "text.primary" },
};

/** « Péremption Lentilles » : lentilles en stock avec leurs dates ; périmées et proches en tête. */
export function PeremptionLentilles() {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = magasins.data?.find((m) => m.id === magasinChoisi) ?? magasins.data?.[0];
  const [jours, setJours] = useState("90");
  const [toutes, setToutes] = useState(false);
  const delai = Math.max(Number(jours) || 0, 0);
  const liste = useQuery({
    queryKey: ["peremptions", magasin?.id, delai],
    queryFn: () => lirePeremptions(magasin!.id, delai),
    enabled: Boolean(magasin),
  });
  const lignes = (liste.data ?? []).filter((l) => toutes || l.etat !== "ok");
  const compte = (etat: EtatPeremption) => (liste.data ?? []).filter((l) => l.etat === etat).length;

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Péremption des lentilles
          </Typography>
          <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap", alignItems: "center" }}>
            {(magasins.data?.length ?? 0) > 1 && (
              <ChoixMagasin
                label="Magasin"
                magasins={magasins.data!}
                valeur={magasin?.id ?? ""}
                onChange={setMagasin}
              />
            )}
            <TextField
              size="small"
              label="Bientôt : dans les"
              value={jours}
              onChange={(ev) => setJours(ev.target.value.replace(/\D/g, ""))}
              slotProps={{ htmlInput: { inputMode: "numeric" }, input: { endAdornment: "jours" } }}
              sx={{ width: 170 }}
            />
            <FormControlLabel
              control={<Checkbox checked={toutes} onChange={(ev) => setToutes(ev.target.checked)} />}
              label="Voir aussi les lentilles sans souci"
            />
          </Stack>
          {liste.isError && <Alert severity="error">{liste.error.message}</Alert>}
          {liste.data && (
            <Typography>
              {`${compte("perimee")} périmées · ${compte("proche")} bientôt périmées · ${compte("inconnue")} à dater (au prochain inventaire des lentilles)`}
            </Typography>
          )}
          {lignes.length > 0 && (
            <TableContainer sx={{ maxHeight: 520 }}>
              <Table stickyHeader size="small" aria-label="Péremption des lentilles">
                <TableHead>
                  <TableRow>
                    <TableCell>Référence</TableCell>
                    <TableCell>Lentille</TableCell>
                    <TableCell align="right">Stock</TableCell>
                    <TableCell>Péremption</TableCell>
                    <TableCell />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {lignes.map((l) => (
                    <TableRow key={l.article}>
                      <TableCell>{l.reference}</TableCell>
                      <TableCell>{l.libelle}</TableCell>
                      <TableCell align="right">{l.stock}</TableCell>
                      <TableCell>
                        {l.lots
                          .map((lot) => `${lot.quantite} × ${lot.date ? dateCourte(lot.date) : "date inconnue"}`)
                          .join(" · ")}
                      </TableCell>
                      <TableCell sx={{ color: ETATS_PEREMPTION[l.etat].couleur, fontWeight: 700 }}>
                        {ETATS_PEREMPTION[l.etat].libelle}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
          {liste.data && lignes.length === 0 && (
            <Typography color="text.secondary">Aucune lentille périmée, bientôt périmée ou à dater.</Typography>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
