import Delete from "@mui/icons-material/Delete";
import Download from "@mui/icons-material/Download";
import Print from "@mui/icons-material/Print";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
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

import { derniersPrix, type Fournisseur } from "../api/achats";
import type { Article } from "../api/caisse";
import { depotDabord, listerMagasins } from "../api/magasins";
import { formaterTexte, type Monnaie } from "../api/monnaie";
import {
  type BonRetour as Bon,
  type BonRetourResume,
  enregistrerRetour,
  type FiltresRetours,
  lireRetour,
  listerRetours,
  type NonConforme,
  nonConformesARetourner,
} from "../api/retours";
import { AjoutArticle, ChoixFournisseur } from "./BonReception";
import { dateCourte, imprimer } from "./FactureAchat";
import { BANDEAU, BORDEAUX, BOUTON, useApaise } from "./RechercheClients";

const ENTETE = { color: BORDEAUX, fontWeight: 700, bgcolor: "grey.100", whiteSpace: "nowrap" } as const;
const TAUX_FODEC = 1;
const aujourdhui = () => new Date().toISOString().slice(0, 10);
const nombre = (texte: string) => Number(texte.replace(",", ".")) || 0;
const arrondi = (montant: number, decimales: number) => Math.round(montant * 10 ** decimales) / 10 ** decimales;

type Ligne = {
  cle: string;
  /** Ligne non conforme d'un bon de réception, sinon article du stock (qui en sortira). */
  ligne_reception: number | null;
  origine: string;
  article: Article | null;
  code: string;
  designation: string;
  stock: number | null;
  quantite: string;
  prix_achat_ht: string;
  taux_remise: string;
  taux_tva: string;
  motif: string;
};

function Bandeau({ titre }: { titre: string }) {
  return (
    <Box sx={{ px: 3, py: 1, borderRadius: 1, background: BANDEAU }}>
      <Typography variant="h5" component="h3" sx={{ color: "common.white", fontWeight: 500 }}>
        {titre}
      </Typography>
    </Box>
  );
}

/** Même calcul que le serveur : net HT, FODEC (1 %) si le fournisseur y est soumis, TVA par taux. */
function calculer(lignes: Ligne[], fodec: boolean, decimales: number) {
  let net = 0;
  let tva = 0;
  for (const l of lignes) {
    const ligne = nombre(l.prix_achat_ht) * nombre(l.quantite) * (1 - nombre(l.taux_remise) / 100);
    net += ligne;
    tva += (ligne * (1 + (fodec ? TAUX_FODEC : 0) / 100) * nombre(l.taux_tva)) / 100;
  }
  const netHt = arrondi(net, decimales);
  const totalFodec = fodec ? arrondi((netHt * TAUX_FODEC) / 100, decimales) : 0;
  const totalTva = arrondi(tva, decimales);
  return { netHt, totalFodec, totalTva, totalTtc: netHt + totalFodec + totalTva };
}

/** Non conformes des bons de réception de ce fournisseur, pas encore renvoyés. */
function ImportNonConformes({
  magasin,
  fournisseur,
  deja,
  monnaie,
  onImporte,
  onFerme,
}: {
  magasin: string;
  fournisseur: Fournisseur;
  deja: Set<number>;
  monnaie: Monnaie;
  onImporte: (lignes: NonConforme[]) => void;
  onFerme: () => void;
}) {
  const liste = useQuery({
    queryKey: ["bons-retour", "a-retourner", magasin, fournisseur.id],
    queryFn: () => nonConformesARetourner(magasin, fournisseur.id),
  });
  const disponibles = (liste.data ?? []).filter((l) => !deja.has(l.id));
  const [choisis, setChoisis] = useState<Set<number>>(new Set());
  return (
    <Dialog open onClose={onFerme} maxWidth="lg" fullWidth>
      <DialogTitle>Non conformes reçus de {fournisseur.nom}</DialogTitle>
      <DialogContent>
        {liste.isError && <Alert severity="error">{liste.error.message}</Alert>}
        {liste.data && disponibles.length === 0 && (
          <Typography color="text.secondary">Aucun article non conforme à renvoyer à ce fournisseur.</Typography>
        )}
        {disponibles.length > 0 && (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox">
                  <Checkbox
                    size="small"
                    slotProps={{ input: { "aria-label": "Tout choisir" } }}
                    checked={choisis.size === disponibles.length}
                    onChange={(e) => setChoisis(new Set(e.target.checked ? disponibles.map((l) => l.id) : []))}
                  />
                </TableCell>
                <TableCell>BL</TableCell>
                <TableCell>Reçu à</TableCell>
                <TableCell>Article</TableCell>
                <TableCell align="right">Qté</TableCell>
                <TableCell>Motif</TableCell>
                <TableCell align="right">Net HT</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {disponibles.map((l) => (
                <TableRow
                  key={l.id}
                  hover
                  sx={{ cursor: "pointer" }}
                  onClick={() =>
                    setChoisis((c) => {
                      const suite = new Set(c);
                      if (suite.has(l.id)) suite.delete(l.id);
                      else suite.add(l.id);
                      return suite;
                    })
                  }
                >
                  <TableCell padding="checkbox">
                    <Checkbox
                      size="small"
                      checked={choisis.has(l.id)}
                      slotProps={{ input: { "aria-label": `Non conforme ${l.designation}` } }}
                    />
                  </TableCell>
                  <TableCell>
                    {l.numero_bl} du {dateCourte(l.date_bl)}
                  </TableCell>
                  <TableCell>{l.magasin}</TableCell>
                  <TableCell>{l.designation}</TableCell>
                  <TableCell align="right">{l.quantite}</TableCell>
                  <TableCell>{l.motif}</TableCell>
                  <TableCell align="right">{formaterTexte(l.net_ht, monnaie)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onFerme}>Fermer</Button>
        <Button
          variant="contained"
          disabled={choisis.size === 0}
          onClick={() => {
            onImporte(disponibles.filter((l) => choisis.has(l.id)));
            onFerme();
          }}
        >
          Importer
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/** Bon retour imprimable (A4), à joindre à la marchandise renvoyée. */
export function pageRetour(b: Bon, monnaie: Monnaie) {
  const m = (v: string) => formaterTexte(v, monnaie);
  const e = (t: string) =>
    t.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] as string);
  const lignes = b.lignes
    .map(
      (l) =>
        `<tr><td>${e(l.code)}</td><td>${e(l.designation)}${l.bon_reception ? `<br><small>${e(l.bon_reception)}</small>` : ""}</td><td>${e(l.motif)}</td><td class="n">${l.quantite}</td><td class="n">${m(l.prix_achat_ht)}</td><td class="n">${Number(l.taux_remise).toFixed(2)}</td><td class="n">${m(l.net_ht)}</td><td class="n">${Number(l.taux_tva).toFixed(2)}</td></tr>`,
    )
    .join("");
  const total = (libelle: string, valeur: string) => `<tr><td>${libelle}</td><td class="n">${m(valeur)}</td></tr>`;
  return `<!doctype html><html><head><meta charset="utf-8"><title>${e(b.numero)}</title><style>
@page { size: A4; margin: 12mm; }
body { font-family: Arial, sans-serif; font-size: 10pt; }
h1 { font-size: 16pt; margin: 0 0 4mm; }
table { border-collapse: collapse; width: 100%; margin: 3mm 0; }
th, td { border: 1px solid #999; padding: 1mm 1.5mm; }
th { background: #eee; text-align: left; }
.n { text-align: right; }
.totaux { width: auto; margin-left: auto; }
</style></head><body>
<h1>Bon Retour Fournisseur ${e(b.numero)}</h1>
<p>Fournisseur : <strong>${b.fournisseur_code} · ${e(b.fournisseur)}</strong> · Date : ${dateCourte(b.date_retour)} · ${e(b.magasin)}${b.motif ? `<br>Motif : ${e(b.motif)}` : ""}</p>
<table><thead><tr><th>Code</th><th>Désignation</th><th>Motif</th><th class="n">Qté</th><th class="n">Prix achat HT</th><th class="n">Remise %</th><th class="n">Net HT</th><th class="n">TVA %</th></tr></thead><tbody>${lignes}</tbody></table>
<table class="totaux"><tbody>${total("Total net HT", b.total_net_ht)}${Number(b.total_fodec) ? total("Total FODEC", b.total_fodec) : ""}${total("Total TVA", b.total_tva)}<tr><th>Total TTC</th><th class="n">${m(b.total_ttc)}</th></tr></tbody></table>
${b.observation ? `<p>Observation : ${e(b.observation)}</p>` : ""}
<p>Créé par ${e(b.cree_par)} le ${dateCourte(b.cree_le)}</p>
</body></html>`;
}

/** « Bon Retour Fournisseur » : non conformes reçus, ou articles du stock renvoyés au fournisseur. */
export function BonRetour() {
  const queryClient = useQueryClient();
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const liste = magasins.data ? depotDabord(magasins.data) : undefined;
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = liste?.find((m) => m.id === magasinChoisi) ?? liste?.[0];
  const monnaie: Monnaie = { devise: magasin?.pays.devise ?? "TND", decimales: magasin?.pays.decimales ?? 3 };
  const m = (v: number) => formaterTexte(v.toFixed(monnaie.decimales), monnaie);
  const [fournisseur, setFournisseur] = useState<Fournisseur | null>(null);
  const [dateRetour, setDateRetour] = useState(aujourdhui());
  const [motif, setMotif] = useState("");
  const [observation, setObservation] = useState("");
  const [lignes, setLignes] = useState<Ligne[]>([]);
  const [importer, setImporter] = useState(false);
  const [enregistre, setEnregistre] = useState<Bon | null>(null);

  const totaux = calculer(lignes, Boolean(fournisseur?.fodec), monnaie.decimales);
  const changer = (cle: string, modification: Partial<Ligne>) =>
    setLignes((ls) => ls.map((l) => (l.cle === cle ? { ...l, ...modification } : l)));
  const vider = () => {
    setLignes([]);
    setMotif("");
    setObservation("");
    setDateRetour(aujourdhui());
  };
  const ajouterArticle = async (article: Article) => {
    setEnregistre(null);
    const prix = magasin ? await derniersPrix(magasin.id, [article.id]).catch(() => ({})) : {};
    const connu = (prix as Record<string, { dernier_prix_achat: string | null; taux_tva: string }>)[article.id];
    setLignes((ls) => [
      ...ls,
      {
        cle: `a-${article.id}-${Date.now()}`,
        ligne_reception: null,
        origine: "Stock",
        article,
        code: article.code_barres || article.reference,
        designation: article.libelle,
        stock: article.stock,
        quantite: "1",
        prix_achat_ht: connu?.dernier_prix_achat ?? "",
        taux_remise: "0",
        taux_tva: connu?.taux_tva ?? article.taux_tva,
        motif: "",
      },
    ]);
  };
  const importerNonConformes = (importees: NonConforme[]) => {
    setEnregistre(null);
    setLignes((ls) => [
      ...ls,
      ...importees.map((l) => ({
        cle: `nc-${l.id}`,
        ligne_reception: l.id,
        origine: `BL ${l.numero_bl}`,
        article: null,
        code: l.code,
        designation: l.designation,
        stock: null,
        quantite: String(l.quantite),
        prix_achat_ht: l.prix_achat_ht,
        taux_remise: l.taux_remise,
        taux_tva: l.taux_tva,
        motif: l.motif,
      })),
    ]);
  };

  const manque = !fournisseur
    ? "Choisissez le fournisseur."
    : lignes.length === 0
      ? "Importez un non conforme ou ajoutez un article du stock."
      : lignes.some((l) => l.ligne_reception === null && !(nombre(l.quantite) >= 1))
        ? "Chaque ligne doit avoir une quantité."
        : lignes.some((l) => l.ligne_reception === null && l.prix_achat_ht.trim() === "")
          ? "Chaque article du stock doit avoir un prix d'achat HT."
          : lignes.find((l) => l.stock !== null && nombre(l.quantite) > l.stock)
            ? "Quantité supérieure au stock."
            : "";
  const validation = useMutation({
    mutationFn: () =>
      enregistrerRetour({
        magasin: magasin!.id,
        fournisseur: fournisseur!.id,
        date_retour: dateRetour,
        motif,
        observation,
        lignes: lignes.map((l) =>
          l.ligne_reception !== null
            ? { ligne_reception: l.ligne_reception, motif: l.motif }
            : {
                article: l.article!.id,
                quantite: nombre(l.quantite),
                prix_achat_ht: String(nombre(l.prix_achat_ht)),
                taux_remise: String(nombre(l.taux_remise)),
                taux_tva: String(nombre(l.taux_tva)),
                motif: l.motif,
              },
        ),
      }),
    onSuccess: (bon) => {
      setEnregistre(bon);
      vider();
      for (const cle of ["bons-retour", "factures-achat", "articles"])
        void queryClient.invalidateQueries({ queryKey: [cle] });
    },
  });
  const petit = (largeur: number) => ({ width: largeur, "& input": { py: 0.5, px: 1, fontSize: 14 } });

  return (
    <Stack spacing={1.5}>
      <Bandeau titre="Bon Retour Fournisseur" />
      <Stack direction="row" spacing={1.5} useFlexGap sx={{ flexWrap: "wrap", alignItems: "center" }}>
        <TextField
          size="small"
          label="Numéro Bon Retour"
          value="Attribué à la validation"
          slotProps={{ htmlInput: { readOnly: true } }}
          sx={{ width: 200 }}
        />
        <TextField
          size="small"
          type="date"
          label="Date du retour"
          value={dateRetour}
          onChange={(e) => setDateRetour(e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <ChoixFournisseur
          valeur={fournisseur}
          onChange={(f) => {
            setFournisseur(f);
            setLignes([]);
          }}
          libelle="Code Fournisseur / Raison sociale"
        />
        {liste && (
          <TextField
            select
            size="small"
            label="Dépôt / Magasin"
            value={magasin?.id ?? ""}
            onChange={(e) => {
              setMagasin(e.target.value);
              setLignes([]);
            }}
            sx={{ width: 200 }}
          >
            {liste.map((x) => (
              <MenuItem key={x.id} value={x.id}>
                {x.nom}
              </MenuItem>
            ))}
          </TextField>
        )}
        <TextField
          size="small"
          label="Motif du retour"
          value={motif}
          onChange={(e) => setMotif(e.target.value)}
          sx={{ width: 280 }}
        />
      </Stack>
      <Stack direction="row" spacing={1.5} useFlexGap sx={{ flexWrap: "wrap", alignItems: "center" }}>
        <Button
          startIcon={<Download sx={{ color: "error.main" }} />}
          sx={BOUTON}
          disabled={!fournisseur || !magasin}
          onClick={() => setImporter(true)}
        >
          Importer Non Conformes
        </Button>
        {magasin && fournisseur && (
          <Box sx={{ flex: 1, minWidth: 320 }}>
            <AjoutArticle magasin={magasin.id} famille="" avecStock onAjoute={(a) => void ajouterArticle(a)} />
          </Box>
        )}
      </Stack>
      <TableContainer sx={{ border: 1, borderColor: "grey.400", borderRadius: 1 }}>
        <Table size="small" aria-label="Articles renvoyés">
          <TableHead>
            <TableRow>
              {[
                "Origine",
                "Code",
                "Désignation",
                "Quantité",
                "Prix Achat HT",
                "Remise %",
                "TVA %",
                "Net HT",
                "Motif",
              ].map((t, i) => (
                <TableCell key={t} sx={ENTETE} align={i >= 3 && i <= 7 ? "right" : "left"}>
                  {t}
                </TableCell>
              ))}
              <TableCell sx={ENTETE} />
            </TableRow>
          </TableHead>
          <TableBody>
            {lignes.map((l) => {
              const stockLigne = l.ligne_reception === null;
              const net = nombre(l.prix_achat_ht) * nombre(l.quantite) * (1 - nombre(l.taux_remise) / 100);
              return (
                <TableRow key={l.cle} sx={{ "& td": { p: 0.5 } }}>
                  <TableCell>
                    {l.origine}
                    {stockLigne && l.stock !== null && (
                      <Typography variant="caption" color="text.secondary" component="div">
                        en stock : {l.stock}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>{l.code}</TableCell>
                  <TableCell>{l.designation}</TableCell>
                  {(["quantite", "prix_achat_ht", "taux_remise", "taux_tva"] as const).map((champ) => (
                    <TableCell key={champ} align="right">
                      {stockLigne ? (
                        <TextField
                          size="small"
                          value={l[champ]}
                          error={champ === "quantite" && l.stock !== null && nombre(l.quantite) > l.stock}
                          onChange={(e) => changer(l.cle, { [champ]: e.target.value })}
                          slotProps={{ htmlInput: { inputMode: "decimal", "aria-label": `${champ} ${l.designation}` } }}
                          sx={{ ...petit(champ === "prix_achat_ht" ? 110 : 70), "& input": { textAlign: "right" } }}
                        />
                      ) : champ === "prix_achat_ht" ? (
                        formaterTexte(l[champ], monnaie)
                      ) : (
                        l[champ]
                      )}
                    </TableCell>
                  ))}
                  <TableCell align="right">{m(net)}</TableCell>
                  <TableCell>
                    <TextField
                      size="small"
                      value={l.motif}
                      onChange={(e) => changer(l.cle, { motif: e.target.value })}
                      slotProps={{ htmlInput: { "aria-label": `Motif ${l.designation}` } }}
                      sx={petit(180)}
                    />
                  </TableCell>
                  <TableCell padding="checkbox">
                    <IconButton
                      size="small"
                      aria-label={`Retirer ${l.designation}`}
                      onClick={() => setLignes((ls) => ls.filter((x) => x.cle !== l.cle))}
                    >
                      <Delete fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
          {lignes.length > 0 && (
            <TableFooter>
              <TableRow sx={{ "& td": { fontWeight: 700, color: "text.primary", bgcolor: "grey.100" } }}>
                <TableCell colSpan={3}>{lignes.length} ligne(s)</TableCell>
                <TableCell align="right">{lignes.reduce((s, l) => s + nombre(l.quantite), 0)}</TableCell>
                <TableCell colSpan={3} />
                <TableCell align="right">{m(totaux.netHt)}</TableCell>
                <TableCell colSpan={2} />
              </TableRow>
            </TableFooter>
          )}
        </Table>
        {lignes.length === 0 && (
          <Box sx={{ p: 2 }}>
            <Typography color="text.secondary">
              « Importer Non Conformes » reprend les articles refusés à la réception (ils ne sont pas en stock). Un
              article ajouté du stock en sortira à la validation.
            </Typography>
          </Box>
        )}
      </TableContainer>
      <Stack direction="row" spacing={3} useFlexGap sx={{ flexWrap: "wrap", alignItems: "flex-start" }}>
        <TextField
          label="Observation"
          size="small"
          multiline
          minRows={2}
          value={observation}
          onChange={(e) => setObservation(e.target.value)}
          sx={{ flex: 1, minWidth: 300, maxWidth: 700 }}
        />
        <Table size="small" aria-label="Totaux du retour" sx={{ width: 300 }}>
          <TableBody>
            <TableRow>
              <TableCell>Total Net HT</TableCell>
              <TableCell align="right">{m(totaux.netHt)}</TableCell>
            </TableRow>
            {fournisseur?.fodec && (
              <TableRow>
                <TableCell>Total Fodec</TableCell>
                <TableCell align="right">{m(totaux.totalFodec)}</TableCell>
              </TableRow>
            )}
            <TableRow>
              <TableCell>Total TVA</TableCell>
              <TableCell align="right">{m(totaux.totalTva)}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell sx={{ fontWeight: 700, color: BORDEAUX }}>Total TTC</TableCell>
              <TableCell align="right" sx={{ fontWeight: 700, color: BORDEAUX }}>
                {m(totaux.totalTtc)}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </Stack>
      {validation.isError && <Alert severity="error">{validation.error.message}</Alert>}
      {enregistre && (
        <Alert
          severity="success"
          action={
            <Button color="inherit" startIcon={<Print />} onClick={() => imprimer(pageRetour(enregistre, monnaie))}>
              Imprimer
            </Button>
          }
        >
          Bon retour {enregistre.numero} enregistré ({formaterTexte(enregistre.total_ttc, monnaie)} TTC). Il se déduit
          de la prochaine facture achat de {enregistre.fournisseur} (« Importer BR »).
        </Alert>
      )}
      <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end", alignItems: "center" }}>
        {manque && (fournisseur || lignes.length > 0) && (
          <Typography variant="body2" color="text.secondary">
            {manque}
          </Typography>
        )}
        <Button sx={BOUTON} onClick={vider} disabled={validation.isPending}>
          Annuler
        </Button>
        <Button
          variant="contained"
          disabled={Boolean(manque) || validation.isPending}
          onClick={() => {
            setEnregistre(null);
            validation.mutate();
          }}
        >
          Valider
        </Button>
      </Stack>
      {importer && fournisseur && magasin && (
        <ImportNonConformes
          magasin={magasin.id}
          fournisseur={fournisseur}
          deja={new Set(lignes.flatMap((l) => (l.ligne_reception === null ? [] : [l.ligne_reception])))}
          monnaie={monnaie}
          onImporte={importerNonConformes}
          onFerme={() => setImporter(false)}
        />
      )}
    </Stack>
  );
}

function DetailRetour({ id, monnaie, onFerme }: { id: string; monnaie: Monnaie; onFerme: () => void }) {
  const bon = useQuery({ queryKey: ["bons-retour", id], queryFn: () => lireRetour(id) });
  const b = bon.data;
  const m = (v: string) => formaterTexte(v, monnaie);
  return (
    <Dialog open onClose={onFerme} maxWidth="lg" fullWidth>
      <DialogTitle sx={{ color: BORDEAUX, fontWeight: 700 }}>{b ? `Bon Retour ${b.numero}` : "Bon Retour"}</DialogTitle>
      <DialogContent>
        {bon.isError && <Alert severity="error">{bon.error.message}</Alert>}
        {b && (
          <Stack spacing={1.5}>
            <Typography>
              {b.fournisseur_code} · {b.fournisseur} · {dateCourte(b.date_retour)} · {b.magasin}
              {b.motif && ` · ${b.motif}`}
            </Typography>
            <Typography color={b.facture ? "success.main" : "text.secondary"}>
              {b.facture ? `Déduit de la facture achat ${b.facture}` : "Pas encore déduit d'une facture achat"}
            </Typography>
            <Table size="small" aria-label="Lignes du bon retour">
              <TableHead>
                <TableRow>
                  {["Code", "Désignation", "Origine", "Motif", "Qté", "Prix Achat HT", "Net HT", "TVA %"].map(
                    (t, i) => (
                      <TableCell key={t} sx={ENTETE} align={i >= 4 ? "right" : "left"}>
                        {t}
                      </TableCell>
                    ),
                  )}
                </TableRow>
              </TableHead>
              <TableBody>
                {b.lignes.map((l, i) => (
                  <TableRow key={i}>
                    <TableCell>{l.code}</TableCell>
                    <TableCell>{l.designation}</TableCell>
                    <TableCell>{l.bon_reception || "Stock"}</TableCell>
                    <TableCell>{l.motif}</TableCell>
                    <TableCell align="right">{l.quantite}</TableCell>
                    <TableCell align="right">{m(l.prix_achat_ht)}</TableCell>
                    <TableCell align="right">{m(l.net_ht)}</TableCell>
                    <TableCell align="right">{Number(l.taux_tva).toFixed(2)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Typography sx={{ textAlign: "right" }}>
              Net HT {m(b.total_net_ht)} · TVA {m(b.total_tva)}
              {Number(b.total_fodec) ? ` · Fodec ${m(b.total_fodec)}` : ""} ·{" "}
              <strong style={{ color: BORDEAUX }}>TTC {m(b.total_ttc)}</strong>
            </Typography>
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        {b && (
          <Button startIcon={<Print />} onClick={() => imprimer(pageRetour(b, monnaie))}>
            Imprimer
          </Button>
        )}
        <Button onClick={onFerme}>Fermer</Button>
      </DialogActions>
    </Dialog>
  );
}

type Colonne = { cle: keyof BonRetourResume; titre: string; filtre?: keyof FiltresRetours; montant?: boolean };

const COLONNES: Colonne[] = [
  { cle: "numero", titre: "Numéro", filtre: "numero" },
  { cle: "date_retour", titre: "Date" },
  { cle: "fournisseur", titre: "Fournisseur", filtre: "fournisseur" },
  { cle: "motif", titre: "Motif" },
  { cle: "total_articles", titre: "Articles" },
  { cle: "total_net_ht", titre: "Net HT", montant: true },
  { cle: "total_tva", titre: "TVA", montant: true },
  { cle: "total_ttc", titre: "TTC", montant: true },
  { cle: "etat_libelle", titre: "Facture" },
  { cle: "cree_par", titre: "Créé par" },
];

/** « Liste des Bons Retour » : filtres sous les colonnes, totaux en pied de tableau. */
export function ListeBonsRetour() {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const pays = magasins.data?.[0]?.pays;
  const monnaie: Monnaie = pays ? { devise: pays.devise, decimales: pays.decimales } : { devise: "TND", decimales: 3 };
  const [filtres, setFiltres] = useState<FiltresRetours>({});
  const [page, setPage] = useState(1);
  const [ouvert, setOuvert] = useState<string | null>(null);
  const recherche = useApaise(JSON.stringify(filtres));
  const bons = useQuery({
    queryKey: ["bons-retour", "liste", recherche, page],
    queryFn: () => listerRetours(JSON.parse(recherche) as FiltresRetours, page),
    placeholderData: keepPreviousData,
  });
  const pages = Math.max(1, Math.ceil((bons.data?.count ?? 0) / 50));
  const filtrer = (cle: keyof FiltresRetours, valeur: string) => {
    setFiltres((f) => ({ ...f, [cle]: valeur }));
    setPage(1);
  };
  const afficher = (b: BonRetourResume, c: Colonne) => {
    const valeur = b[c.cle];
    if (c.montant) return formaterTexte(String(valeur), monnaie);
    if (c.cle === "date_retour") return dateCourte(b.date_retour);
    if (c.cle === "fournisseur") return `${b.fournisseur_code} · ${b.fournisseur}`;
    if (c.cle === "etat_libelle") return b.facture ? `Déduit (${b.facture})` : "Non déduit";
    return valeur ?? "";
  };
  return (
    <Stack spacing={1}>
      <Bandeau titre="Liste des Bons Retour" />
      <Stack direction="row" spacing={2}>
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
      {bons.isError && <Alert severity="error">{bons.error.message}</Alert>}
      <TableContainer sx={{ maxHeight: 520, border: 1, borderColor: "grey.400", borderRadius: 1 }}>
        <Table stickyHeader size="small" aria-label="Bons retour">
          <TableHead>
            <TableRow>
              {COLONNES.map((c) => (
                <TableCell key={c.cle} align={c.montant ? "right" : "left"} sx={ENTETE}>
                  {c.titre}
                </TableCell>
              ))}
            </TableRow>
            <TableRow>
              {COLONNES.map((c) => (
                <TableCell key={c.cle} sx={{ top: 37, p: 0.5, bgcolor: "grey.300" }}>
                  {c.filtre && (
                    <TextField
                      size="small"
                      fullWidth
                      value={filtres[c.filtre] ?? ""}
                      onChange={(e) => filtrer(c.filtre!, e.target.value)}
                      slotProps={{
                        htmlInput: { "aria-label": `Filtrer ${c.titre}` },
                        input: { sx: { bgcolor: "common.white", height: 28, fontSize: 14 } },
                      }}
                    />
                  )}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {bons.data?.results.map((b) => (
              <TableRow
                key={b.id}
                hover
                onClick={() => setOuvert(b.id)}
                sx={{ cursor: "pointer", "& td": { whiteSpace: "nowrap" } }}
              >
                {COLONNES.map((c) => (
                  <TableCell key={c.cle} align={c.montant ? "right" : "left"}>
                    {afficher(b, c)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
          {bons.data && (
            <TableFooter>
              <TableRow sx={{ "& td": { fontWeight: 700, color: "text.primary", fontSize: 14, bgcolor: "grey.100" } }}>
                <TableCell colSpan={5}>
                  {bons.data.count} bon{bons.data.count > 1 ? "s" : ""} retour
                </TableCell>
                <TableCell align="right">{formaterTexte(bons.data.totaux.total_net_ht, monnaie)}</TableCell>
                <TableCell align="right">{formaterTexte(bons.data.totaux.total_tva, monnaie)}</TableCell>
                <TableCell align="right">{formaterTexte(bons.data.totaux.total_ttc, monnaie)}</TableCell>
                <TableCell colSpan={2} />
              </TableRow>
            </TableFooter>
          )}
        </Table>
        {bons.data?.count === 0 && (
          <Box sx={{ p: 2 }}>
            <Typography color="text.secondary">Aucun bon retour.</Typography>
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
      {ouvert && <DetailRetour id={ouvert} monnaie={monnaie} onFerme={() => setOuvert(null)} />}
    </Stack>
  );
}
