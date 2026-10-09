import Print from "@mui/icons-material/Print";
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
import MenuItem from "@mui/material/MenuItem";
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

import type { Fournisseur } from "../api/achats";
import { listerMagasins } from "../api/magasins";
import { formaterTexte, type Monnaie } from "../api/monnaie";
import {
  annulerReglement,
  debiterReglement,
  imputerAvance,
  listerReglementsFournisseurs,
  MODES_REGLEMENT_FOURNISSEUR,
  reglerFournisseur,
  situationFournisseur,
  type ModeReglementFournisseur,
  type ReglementFournisseur,
} from "../api/reglementsFournisseurs";
import { ChoixFournisseur } from "./BonReception";
import { dateCourte, imprimer } from "./FactureAchat";
import { echapper as e } from "./Factures";

const aujourdhui = () => new Date().toLocaleDateString("sv-SE");
const nombre = (texte: string) => Number(texte.replace(",", ".").trim() || 0);

const STYLE = `<style>
@page { size: A4; margin: 12mm; }
body { font-family: Arial, sans-serif; font-size: 10pt; }
h1 { font-size: 16pt; margin: 0 0 4mm; }
table { border-collapse: collapse; width: 100%; margin: 3mm 0; }
th, td { border: 1px solid #999; padding: 1mm 1.5mm; }
th { background: #eee; text-align: left; }
.n { text-align: right; }
.signatures { display: flex; justify-content: space-between; margin-top: 15mm; }
</style>`;

/** Pièce du règlement : ce qui est versé, la retenue et les factures soldées. */
export function pageReglement(r: ReglementFournisseur) {
  const m = (v: string) => formaterTexte(v, r);
  const lignes = r.imputations
    .map(
      (i) =>
        `<tr><td>${e(i.facture_numero)}</td><td>${e(i.reference_fournisseur)}</td><td>${dateCourte(i.date_reference)}</td><td class="n">${m(i.facture_total_ttc)}</td><td class="n">${m(i.montant)}</td></tr>`,
    )
    .join("");
  return `<!doctype html><html><head><meta charset="utf-8"><title>${e(r.numero)}</title>${STYLE}</head><body>
<h1>Règlement fournisseur ${e(r.numero)}</h1>
<p>${e(r.societe)} · ${e(r.magasin_nom)}<br>Fournisseur : <strong>${e(r.fournisseur_nom)}</strong><br>
Date : ${dateCourte(r.date_reglement)} · ${e(r.mode_libelle)}${r.reference ? ` n° ${e(r.reference)}` : ""}${r.banque ? ` · ${e(r.banque)}` : ""}${r.echeance ? ` · échéance ${dateCourte(r.echeance)}` : ""}</p>
${lignes ? `<table><thead><tr><th>Facture</th><th>Réf. fournisseur</th><th>Date</th><th class="n">Total TTC</th><th class="n">Réglé</th></tr></thead><tbody>${lignes}</tbody></table>` : "<p>Avance sur factures à venir.</p>"}
<table style="width:auto;margin-left:auto"><tbody>
<tr><td>Montant versé</td><td class="n">${m(r.montant)}</td></tr>
${Number(r.retenue) ? `<tr><td>Retenue à la source (${Number(r.taux_retenue)} %)</td><td class="n">${m(r.retenue)}</td></tr>` : ""}
<tr><th>Total réglé</th><th class="n">${m(r.total_regle)}</th></tr>
${Number(r.disponible) ? `<tr><td>Dont avance à imputer</td><td class="n">${m(r.disponible)}</td></tr>` : ""}
</tbody></table>
${r.observation ? `<p>Observation : ${e(r.observation)}</p>` : ""}
<div class="signatures"><span>Visa</span><span>Signature du fournisseur</span></div>
</body></html>`;
}

/** Certificat de retenue à la source, remis au fournisseur. */
export function pageCertificatRetenue(r: ReglementFournisseur) {
  const m = (v: string) => formaterTexte(v, r);
  const base = r.imputations.reduce((s, i) => s + Number(i.montant), 0).toFixed(r.decimales);
  return `<!doctype html><html><head><meta charset="utf-8"><title>Certificat ${e(r.numero)}</title>${STYLE}</head><body>
<h1>Certificat de retenue à la source</h1>
<table><tbody>
<tr><th colspan="2">Payeur</th></tr>
<tr><td>Raison sociale</td><td>${e(r.societe)}</td></tr>
<tr><td>Matricule fiscal</td><td>${e(r.societe_matricule)}</td></tr>
<tr><td>Adresse</td><td>${e(r.societe_adresse)}</td></tr>
<tr><th colspan="2">Bénéficiaire</th></tr>
<tr><td>Raison sociale</td><td>${e(r.fournisseur_nom)}</td></tr>
<tr><td>Matricule fiscal</td><td>${e(r.fournisseur_matricule)}</td></tr>
<tr><td>Adresse</td><td>${e(r.fournisseur_adresse)}</td></tr>
</tbody></table>
<table><thead><tr><th>Date du paiement</th><th>Factures</th><th class="n">Montant brut</th><th class="n">Taux</th><th class="n">Retenue</th><th class="n">Net servi</th></tr></thead>
<tbody><tr><td>${dateCourte(r.date_reglement)}</td><td>${r.imputations.map((i) => e(i.reference_fournisseur)).join(", ")}</td><td class="n">${m(base)}</td><td class="n">${Number(r.taux_retenue)} %</td><td class="n">${m(r.retenue)}</td><td class="n">${m(r.montant)}</td></tr></tbody></table>
<p>Règlement ${e(r.numero)}.</p>
<div class="signatures"><span>Fait le ${dateCourte(r.date_reglement)}</span><span>Cachet et signature du payeur</span></div>
</body></html>`;
}

type Droits = { regler: boolean; debiter: boolean; annuler: boolean };

/**
 * Règlements fournisseurs : paiement des factures achat (en tout ou en partie), avances,
 * retenue à la source et échéancier des chèques et traites.
 */
export function ReglementsFournisseurs({
  droits,
  ongletInitial = "nouveau",
}: {
  droits: Droits;
  ongletInitial?: "nouveau" | "liste" | "echeancier";
}) {
  const [onglet, setOnglet] = useState(
    droits.regler ? ongletInitial : ongletInitial === "nouveau" ? "liste" : ongletInitial,
  );
  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Règlements fournisseurs
          </Typography>
          <Tabs value={onglet} onChange={(_, valeur: typeof onglet) => setOnglet(valeur)}>
            {droits.regler && <Tab value="nouveau" label="Nouveau règlement" />}
            <Tab value="liste" label="Liste des règlements" />
            <Tab value="echeancier" label="Échéancier" />
          </Tabs>
          {onglet === "nouveau" && <Nouveau />}
          {onglet === "liste" && <Liste droits={droits} />}
          {onglet === "echeancier" && <Echeancier droits={droits} />}
        </Stack>
      </CardContent>
    </Card>
  );
}

function Nouveau() {
  const queryClient = useQueryClient();
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = magasins.data?.find((m) => m.id === magasinChoisi) ?? magasins.data?.[0];
  const monnaie: Monnaie = { devise: magasin?.pays.devise ?? "TND", decimales: magasin?.pays.decimales ?? 3 };
  const [fournisseur, setFournisseur] = useState<Fournisseur | null>(null);
  const [montants, setMontants] = useState<Record<string, string>>({});
  const [dateReglement, setDate] = useState(aujourdhui());
  const [mode, setMode] = useState<ModeReglementFournisseur>("virement");
  const [reference, setReference] = useState("");
  const [banque, setBanque] = useState("");
  const [echeance, setEcheance] = useState("");
  const [avecRetenue, setAvecRetenue] = useState(false);
  const [taux, setTaux] = useState("1");
  const [verseSaisi, setVerse] = useState<string | null>(null);
  const [enregistre, setEnregistre] = useState<ReglementFournisseur | null>(null);
  const situation = useQuery({
    queryKey: ["situation-fournisseur", magasin?.id, fournisseur?.id],
    queryFn: () => situationFournisseur(magasin!.id, fournisseur!.id),
    enabled: Boolean(magasin && fournisseur),
  });
  const m = (v: number) => formaterTexte(v.toFixed(monnaie.decimales), monnaie);
  const lignes = Object.entries(montants)
    .filter(([, v]) => nombre(v) > 0)
    .map(([facture, montant]) => ({ facture, montant: nombre(montant).toFixed(monnaie.decimales) }));
  const totalFactures = lignes.reduce((s, l) => s + Number(l.montant), 0);
  const retenue = avecRetenue ? Number(((totalFactures * nombre(taux)) / 100).toFixed(monnaie.decimales)) : 0;
  const verse = verseSaisi ?? (totalFactures - retenue).toFixed(monnaie.decimales);
  const avance = nombre(verse) + retenue - totalFactures;
  const aEcheance = mode === "cheque" || mode === "traite";

  const vider = () => {
    setMontants({});
    setReference("");
    setBanque("");
    setEcheance("");
    setVerse(null);
  };
  const rafraichir = () => {
    void queryClient.invalidateQueries({ queryKey: ["situation-fournisseur"] });
    void queryClient.invalidateQueries({ queryKey: ["reglements-fournisseurs"] });
  };
  const reglement = useMutation({
    mutationFn: () =>
      reglerFournisseur({
        magasin: magasin!.id,
        fournisseur: fournisseur!.id,
        date_reglement: dateReglement,
        mode,
        montant: nombre(verse).toFixed(monnaie.decimales),
        taux_retenue: avecRetenue ? nombre(taux).toFixed(2) : "0",
        retenue: retenue.toFixed(monnaie.decimales),
        reference,
        banque,
        echeance: aEcheance && echeance ? echeance : null,
        lignes,
      }),
    onSuccess: (r) => {
      setEnregistre(r);
      vider();
      rafraichir();
    },
  });
  const imputation = useMutation({
    mutationFn: (avanceId: string) => imputerAvance(avanceId, dateReglement, lignes),
    onSuccess: (r) => {
      setEnregistre(r);
      vider();
      rafraichir();
    },
  });

  return (
    <Stack spacing={2}>
      {enregistre && (
        <Alert
          severity="success"
          onClose={() => setEnregistre(null)}
          action={
            <Stack direction="row">
              <Button color="inherit" startIcon={<Print />} onClick={() => imprimer(pageReglement(enregistre))}>
                Pièce
              </Button>
              {Number(enregistre.retenue) > 0 && (
                <Button
                  color="inherit"
                  startIcon={<Print />}
                  onClick={() => imprimer(pageCertificatRetenue(enregistre))}
                >
                  Certificat de retenue
                </Button>
              )}
            </Stack>
          }
        >
          Règlement {enregistre.numero} enregistré ({formaterTexte(enregistre.total_regle, enregistre)}).
        </Alert>
      )}
      <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap" }}>
        {(magasins.data?.length ?? 0) > 1 && (
          <TextField
            select
            size="small"
            label="Magasin"
            value={magasin?.id ?? ""}
            onChange={(ev) => {
              setMagasin(ev.target.value);
              vider();
            }}
            sx={{ minWidth: 200 }}
          >
            {magasins.data?.map((mag) => (
              <MenuItem key={mag.id} value={mag.id}>
                {mag.nom}
              </MenuItem>
            ))}
          </TextField>
        )}
        <ChoixFournisseur
          valeur={fournisseur}
          onChange={(f) => {
            setFournisseur(f);
            vider();
          }}
        />
      </Stack>
      {situation.isError && <Alert severity="error">{situation.error.message}</Alert>}
      {situation.data && (
        <>
          <Typography>
            Reste à régler : <strong>{formaterTexte(situation.data.total_reste, monnaie)}</strong>
            {Number(situation.data.total_avances) > 0 &&
              ` · avances à imputer : ${formaterTexte(situation.data.total_avances, monnaie)}`}
          </Typography>
          {situation.data.factures.length === 0 ? (
            <Typography color="text.secondary">Aucune facture à régler pour ce fournisseur.</Typography>
          ) : (
            <Table size="small" aria-label="Factures à régler">
              <TableHead>
                <TableRow>
                  <TableCell padding="checkbox" />
                  <TableCell>Facture</TableCell>
                  <TableCell>Réf. fournisseur</TableCell>
                  <TableCell>Date</TableCell>
                  <TableCell align="right">Total TTC</TableCell>
                  <TableCell align="right">Déjà réglé</TableCell>
                  <TableCell align="right">Reste</TableCell>
                  <TableCell>À régler</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {situation.data.factures.map((f) => (
                  <TableRow key={f.id}>
                    <TableCell padding="checkbox">
                      <Checkbox
                        checked={f.id in montants}
                        onChange={() => {
                          setVerse(null);
                          setMontants((avant) => {
                            const suivant = { ...avant };
                            if (f.id in suivant) delete suivant[f.id];
                            else suivant[f.id] = f.reste;
                            return suivant;
                          });
                        }}
                        slotProps={{ input: { "aria-label": `Régler ${f.numero}` } }}
                      />
                    </TableCell>
                    <TableCell>{f.numero}</TableCell>
                    <TableCell>{f.reference_fournisseur}</TableCell>
                    <TableCell>{dateCourte(f.date_reference)}</TableCell>
                    <TableCell align="right">{formaterTexte(f.total_ttc, monnaie)}</TableCell>
                    <TableCell align="right">{formaterTexte(f.regle, monnaie)}</TableCell>
                    <TableCell align="right">{formaterTexte(f.reste, monnaie)}</TableCell>
                    <TableCell>
                      {f.id in montants && (
                        <TextField
                          size="small"
                          value={montants[f.id]}
                          onChange={(ev) => {
                            setVerse(null);
                            setMontants((avant) => ({ ...avant, [f.id]: ev.target.value }));
                          }}
                          slotProps={{ htmlInput: { "aria-label": `Montant ${f.numero}`, inputMode: "decimal" } }}
                          sx={{ width: 130 }}
                        />
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {situation.data.avances.length > 0 && lignes.length > 0 && (
            <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap", alignItems: "center" }}>
              <Typography variant="body2">Solder avec une avance :</Typography>
              {situation.data.avances.map((a) => (
                <Button
                  key={a.id}
                  size="small"
                  variant="outlined"
                  disabled={imputation.isPending}
                  onClick={() => imputation.mutate(a.id)}
                >
                  {a.numero} ({formaterTexte(a.disponible, monnaie)})
                </Button>
              ))}
            </Stack>
          )}
          {imputation.isError && <Alert severity="error">{imputation.error.message}</Alert>}
          <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap", alignItems: "center" }}>
            <TextField
              size="small"
              type="date"
              label="Date"
              value={dateReglement}
              onChange={(ev) => setDate(ev.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <TextField
              select
              size="small"
              label="Mode"
              value={mode}
              onChange={(ev) => setMode(ev.target.value as ModeReglementFournisseur)}
              sx={{ minWidth: 140 }}
            >
              {MODES_REGLEMENT_FOURNISSEUR.map((md) => (
                <MenuItem key={md.valeur} value={md.valeur}>
                  {md.libelle}
                </MenuItem>
              ))}
            </TextField>
            {mode !== "especes" && (
              <TextField
                size="small"
                label="N° pièce"
                value={reference}
                onChange={(ev) => setReference(ev.target.value)}
              />
            )}
            {mode !== "especes" && (
              <TextField size="small" label="Banque" value={banque} onChange={(ev) => setBanque(ev.target.value)} />
            )}
            {aEcheance && (
              <TextField
                size="small"
                type="date"
                label="Échéance"
                value={echeance}
                onChange={(ev) => setEcheance(ev.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
              />
            )}
          </Stack>
          <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap", alignItems: "center" }}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={avecRetenue}
                  onChange={(ev) => {
                    setVerse(null);
                    setAvecRetenue(ev.target.checked);
                  }}
                />
              }
              label="Retenue à la source"
            />
            {avecRetenue && (
              <TextField
                size="small"
                label="Taux %"
                value={taux}
                onChange={(ev) => {
                  setVerse(null);
                  setTaux(ev.target.value);
                }}
                sx={{ width: 90 }}
              />
            )}
            <TextField
              size="small"
              label="Montant versé"
              value={verse}
              onChange={(ev) => setVerse(ev.target.value)}
              slotProps={{ htmlInput: { inputMode: "decimal" } }}
              sx={{ width: 150 }}
            />
            <Typography variant="body2">
              Factures : {m(totalFactures)}
              {retenue > 0 && ` · retenue : ${m(retenue)}`}
              {avance > 0 && ` · avance : ${m(avance)}`}
            </Typography>
          </Stack>
          {avance < 0 && (
            <Alert severity="warning">Le montant versé et la retenue ne couvrent pas les factures choisies.</Alert>
          )}
          {reglement.isError && <Alert severity="error">{reglement.error.message}</Alert>}
          <Stack direction="row" sx={{ justifyContent: "flex-end" }}>
            <Button
              variant="contained"
              disabled={reglement.isPending || nombre(verse) + retenue <= 0 || avance < 0}
              onClick={() => reglement.mutate()}
            >
              Enregistrer le règlement
            </Button>
          </Stack>
        </>
      )}
    </Stack>
  );
}

function Detail({
  reglement: r,
  droits,
  onFermer,
}: {
  reglement: ReglementFournisseur;
  droits: Droits;
  onFermer: () => void;
}) {
  const queryClient = useQueryClient();
  const annulation = useMutation({
    mutationFn: () => annulerReglement(r.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reglements-fournisseurs"] });
      void queryClient.invalidateQueries({ queryKey: ["situation-fournisseur"] });
      onFermer();
    },
  });
  return (
    <Dialog open onClose={onFermer} fullWidth maxWidth="md">
      <DialogTitle>
        Règlement {r.numero} · {r.fournisseur_nom}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={2}>
          <Typography>
            {dateCourte(r.date_reglement)} · {r.mode_libelle}
            {r.reference && ` n° ${r.reference}`}
            {r.echeance && ` · échéance ${dateCourte(r.echeance)} (${r.statut_libelle.toLowerCase()})`}
            <br />
            Versé {formaterTexte(r.montant, r)}
            {Number(r.retenue) > 0 && ` + retenue ${formaterTexte(r.retenue, r)}`} = réglé{" "}
            {formaterTexte(r.total_regle, r)}
            {Number(r.disponible) > 0 && ` · avance restante ${formaterTexte(r.disponible, r)}`}
          </Typography>
          {r.imputations.length > 0 && (
            <Table size="small" aria-label="Factures réglées">
              <TableHead>
                <TableRow>
                  <TableCell>Facture</TableCell>
                  <TableCell>Réf. fournisseur</TableCell>
                  <TableCell align="right">Réglé</TableCell>
                  <TableCell>Le</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {r.imputations.map((i, n) => (
                  <TableRow key={n}>
                    <TableCell>{i.facture_numero}</TableCell>
                    <TableCell>{i.reference_fournisseur}</TableCell>
                    <TableCell align="right">{formaterTexte(i.montant, r)}</TableCell>
                    <TableCell>{dateCourte(i.le)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {annulation.isError && <Alert severity="error">{annulation.error.message}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        {droits.annuler && (
          <Button color="error" disabled={annulation.isPending} onClick={() => annulation.mutate()}>
            Annuler ce règlement
          </Button>
        )}
        <Button startIcon={<Print />} onClick={() => imprimer(pageReglement(r))}>
          Pièce
        </Button>
        {Number(r.retenue) > 0 && (
          <Button startIcon={<Print />} onClick={() => imprimer(pageCertificatRetenue(r))}>
            Certificat de retenue
          </Button>
        )}
        <Button onClick={onFermer}>Fermer</Button>
      </DialogActions>
    </Dialog>
  );
}

function Liste({ droits }: { droits: Droits }) {
  const [fournisseur, setFournisseur] = useState<Fournisseur | null>(null);
  const [mode, setMode] = useState("");
  const [du, setDu] = useState("");
  const [au, setAu] = useState("");
  const [choisi, setChoisi] = useState<string | null>(null);
  const liste = useQuery({
    queryKey: ["reglements-fournisseurs", fournisseur?.id, mode, du, au],
    queryFn: () => listerReglementsFournisseurs({ fournisseur: fournisseur?.id, mode, du, au }),
  });
  const choix = liste.data?.find((r) => r.id === choisi);
  return (
    <Stack spacing={2}>
      <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap" }}>
        <ChoixFournisseur valeur={fournisseur} onChange={setFournisseur} libelle="Fournisseur" minWidth={260} />
        <TextField
          select
          size="small"
          label="Mode"
          value={mode}
          onChange={(ev) => setMode(ev.target.value)}
          sx={{ minWidth: 140 }}
        >
          <MenuItem value="">Tous</MenuItem>
          {MODES_REGLEMENT_FOURNISSEUR.map((md) => (
            <MenuItem key={md.valeur} value={md.valeur}>
              {md.libelle}
            </MenuItem>
          ))}
        </TextField>
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
      {liste.isError && <Alert severity="error">{liste.error.message}</Alert>}
      {liste.data?.length === 0 && <Typography color="text.secondary">Aucun règlement.</Typography>}
      {liste.data && liste.data.length > 0 && (
        <Table size="small" aria-label="Règlements fournisseurs">
          <TableHead>
            <TableRow>
              <TableCell>N°</TableCell>
              <TableCell>Date</TableCell>
              <TableCell>Fournisseur</TableCell>
              <TableCell>Mode</TableCell>
              <TableCell align="right">Versé</TableCell>
              <TableCell align="right">Retenue</TableCell>
              <TableCell align="right">Avance restante</TableCell>
              <TableCell>Statut</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {liste.data.map((r) => (
              <TableRow key={r.id} hover sx={{ cursor: "pointer" }} onClick={() => setChoisi(r.id)}>
                <TableCell>{r.numero}</TableCell>
                <TableCell>{dateCourte(r.date_reglement)}</TableCell>
                <TableCell>{r.fournisseur_nom}</TableCell>
                <TableCell>
                  {r.mode_libelle}
                  {r.reference && ` ${r.reference}`}
                </TableCell>
                <TableCell align="right">{formaterTexte(r.montant, r)}</TableCell>
                <TableCell align="right">{Number(r.retenue) ? formaterTexte(r.retenue, r) : "—"}</TableCell>
                <TableCell align="right">{Number(r.disponible) ? formaterTexte(r.disponible, r) : "—"}</TableCell>
                <TableCell>{r.statut_libelle}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      {choix && <Detail reglement={choix} droits={droits} onFermer={() => setChoisi(null)} />}
    </Stack>
  );
}

function Echeancier({ droits }: { droits: Droits }) {
  const queryClient = useQueryClient();
  const [debitLe, setDebitLe] = useState(aujourdhui());
  const liste = useQuery({
    queryKey: ["reglements-fournisseurs", "echeancier"],
    queryFn: () => listerReglementsFournisseurs({ statut: "a_echoir" }),
  });
  const debit = useMutation({
    mutationFn: (id: string) => debiterReglement(id, debitLe),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["reglements-fournisseurs"] }),
  });
  const total = (liste.data ?? []).reduce((s, r) => s + Number(r.montant), 0);
  const premier = liste.data?.[0];
  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        Chèques et traites remis aux fournisseurs, pas encore débités par la banque, par date d'échéance.
      </Typography>
      {droits.debiter && (
        <TextField
          size="small"
          type="date"
          label="Date du débit"
          value={debitLe}
          onChange={(ev) => setDebitLe(ev.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
          sx={{ maxWidth: 200 }}
        />
      )}
      {liste.isError && <Alert severity="error">{liste.error.message}</Alert>}
      {debit.isError && <Alert severity="error">{debit.error.message}</Alert>}
      {liste.data?.length === 0 && <Typography color="text.secondary">Aucun chèque ni traite à échoir.</Typography>}
      {liste.data && liste.data.length > 0 && (
        <Table size="small" aria-label="Échéancier">
          <TableHead>
            <TableRow>
              <TableCell>Échéance</TableCell>
              <TableCell>Fournisseur</TableCell>
              <TableCell>Pièce</TableCell>
              <TableCell>Banque</TableCell>
              <TableCell align="right">Montant</TableCell>
              {droits.debiter && <TableCell />}
            </TableRow>
          </TableHead>
          <TableBody>
            {liste.data.map((r) => (
              <TableRow key={r.id}>
                <TableCell>
                  {r.echeance && r.echeance < aujourdhui() ? (
                    <Chip size="small" color="error" label={dateCourte(r.echeance)} />
                  ) : (
                    dateCourte(r.echeance ?? "")
                  )}
                </TableCell>
                <TableCell>{r.fournisseur_nom}</TableCell>
                <TableCell>
                  {r.mode_libelle} {r.reference} · {r.numero}
                </TableCell>
                <TableCell>{r.banque || "—"}</TableCell>
                <TableCell align="right">{formaterTexte(r.montant, r)}</TableCell>
                {droits.debiter && (
                  <TableCell>
                    <Button size="small" disabled={debit.isPending} onClick={() => debit.mutate(r.id)}>
                      Débité
                    </Button>
                  </TableCell>
                )}
              </TableRow>
            ))}
            {premier && (
              <TableRow>
                <TableCell colSpan={4}>
                  <strong>Total à échoir</strong>
                </TableCell>
                <TableCell align="right">
                  <strong>{formaterTexte(total.toFixed(premier.decimales), premier)}</strong>
                </TableCell>
                {droits.debiter && <TableCell />}
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}
    </Stack>
  );
}
