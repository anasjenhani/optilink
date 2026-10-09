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
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  envoyerBordereau,
  listerBordereaux,
  modifierBordereau,
  pecAEnvoyer,
  preparerBordereau,
  reglerBordereau,
  supprimerBordereau,
  type Bordereau,
  type ModeReglementBordereau,
  type PecBordereau,
} from "../api/bordereaux";
import { listerMagasins } from "../api/magasins";
import { formaterTexte, type Monnaie } from "../api/monnaie";
import { listerOrganismes } from "../api/prisesEnCharge";
import { dateCourte, imprimer } from "./FactureAchat";
import { echapper as e } from "./Factures";

const aujourdhui = () => new Date().toLocaleDateString("sv-SE");

const STYLE = `<style>
@page { size: A4; margin: 12mm; }
body { font-family: Arial, sans-serif; font-size: 10pt; }
h1 { font-size: 16pt; margin: 0 0 4mm; }
table { border-collapse: collapse; width: 100%; margin: 3mm 0; }
th, td { border: 1px solid #999; padding: 1mm 1.5mm; }
th { background: #eee; text-align: left; }
.n { text-align: right; }
.page { page-break-after: always; }
.page:last-child { page-break-after: auto; }
</style>`;

/** Bordereau d'envoi à l'organisme : une ligne par prise en charge, avec le total demandé. */
export function pageBordereau(b: Bordereau) {
  const m = (v: string) => formaterTexte(v, b);
  const lignes = b.prises_en_charge
    .map(
      (p, i) =>
        `<tr><td class="n">${i + 1}</td><td>${e(p.vente_numero)}</td><td>${dateCourte(p.vente_date)}</td><td>${e(p.client ?? "")}</td><td>${e(p.numero_affilie)}</td><td>${e(p.numero_dossier)}</td><td class="n">${m(p.vente_total_ttc)}</td><td class="n">${m(p.montant)}</td></tr>`,
    )
    .join("");
  return `<!doctype html><html><head><meta charset="utf-8"><title>${e(b.numero)}</title>${STYLE}</head><body>
<h1>Bordereau ${e(b.numero)}</h1>
<p>${e(b.magasin_nom)} · Organisme : <strong>${e(b.organisme_nom)}</strong>${b.envoye_le ? ` · Envoyé le ${dateCourte(b.envoye_le)}` : ""}</p>
<table><thead><tr><th class="n">#</th><th>Facture</th><th>Date</th><th>Assuré</th><th>N° affilié</th><th>N° dossier</th><th class="n">Total TTC</th><th class="n">Part organisme</th></tr></thead><tbody>${lignes}</tbody>
<tfoot><tr><th colspan="7">Total demandé (${b.prises_en_charge.length} dossiers)</th><th class="n">${m(b.total)}</th></tr></tfoot></table>
${b.observation ? `<p>Observation : ${e(b.observation)}</p>` : ""}
</body></html>`;
}

/** Une facture par prise en charge, à joindre au bordereau. */
export function pageFacturesPec(b: Bordereau) {
  const m = (v: string) => formaterTexte(v, b);
  const facture = (p: PecBordereau) => {
    const lignes = p.lignes
      .map(
        (l) => `<tr><td>${e(l.libelle)}</td><td class="n">${l.quantite}</td><td class="n">${m(l.total_ttc)}</td></tr>`,
      )
      .join("");
    const reste = (Number(p.vente_total_ttc) - Number(p.montant)).toFixed(b.decimales);
    return `<div class="page"><h1>Facture ${e(p.vente_numero)}</h1>
<p>${e(b.magasin_nom)} · ${dateCourte(p.vente_date)}<br>Assuré : <strong>${e(p.client ?? "")}</strong>${p.numero_affilie ? ` · N° affilié ${e(p.numero_affilie)}` : ""}${p.numero_dossier ? ` · Dossier ${e(p.numero_dossier)}` : ""}<br>Organisme : ${e(b.organisme_nom)} · Bordereau ${e(b.numero)}</p>
<table><thead><tr><th>Désignation</th><th class="n">Qté</th><th class="n">Total TTC</th></tr></thead><tbody>${lignes}</tbody>
<tfoot><tr><th colspan="2">Total TTC</th><th class="n">${m(p.vente_total_ttc)}</th></tr>
<tr><th colspan="2">Part ${e(b.organisme_nom)}</th><th class="n">${m(p.montant)}</th></tr>
<tr><th colspan="2">Part assuré</th><th class="n">${m(reste)}</th></tr></tfoot></table></div>`;
  };
  return `<!doctype html><html><head><meta charset="utf-8"><title>Factures ${e(b.numero)}</title>${STYLE}</head><body>${b.prises_en_charge.map(facture).join("")}</body></html>`;
}

/**
 * Bordereaux CNAM, assurances et conventions : on regroupe les prises en charge d'un magasin pour
 * un organisme, on imprime le bordereau et les factures, on l'envoie, puis on saisit ce que
 * l'organisme a payé. Ce qu'il ne paie pas revient à la charge du client.
 */
export function BordereauxPec({ preparer, regler }: { preparer: boolean; regler: boolean }) {
  const [statut, setStatut] = useState("");
  const [nouveau, setNouveau] = useState(false);
  const [choisi, setChoisi] = useState<string | null>(null);
  const liste = useQuery({ queryKey: ["bordereaux-pec", statut], queryFn: () => listerBordereaux(statut) });
  const bordereau = liste.data?.find((b) => b.id === choisi);

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
            <Typography variant="h6" component="h2" sx={{ flexGrow: 1 }}>
              Bordereaux CNAM / conventions
            </Typography>
            {preparer && (
              <Button variant="contained" onClick={() => setNouveau(true)}>
                Nouveau bordereau
              </Button>
            )}
          </Stack>
          <TextField
            select
            size="small"
            label="Statut"
            value={statut}
            onChange={(ev) => setStatut(ev.target.value)}
            sx={{ maxWidth: 260 }}
          >
            <MenuItem value="">Tous</MenuItem>
            <MenuItem value="preparation">En préparation</MenuItem>
            <MenuItem value="envoye">Envoyés, à régler</MenuItem>
            <MenuItem value="regle">Réglés</MenuItem>
          </TextField>
          {liste.isError && <Alert severity="error">{liste.error.message}</Alert>}
          {liste.data?.length === 0 && <Typography color="text.secondary">Aucun bordereau.</Typography>}
          {liste.data && liste.data.length > 0 && (
            <Table size="small" aria-label="Bordereaux">
              <TableHead>
                <TableRow>
                  <TableCell>N°</TableCell>
                  <TableCell>Magasin</TableCell>
                  <TableCell>Organisme</TableCell>
                  <TableCell align="right">Dossiers</TableCell>
                  <TableCell align="right">Demandé</TableCell>
                  <TableCell align="right">Réglé</TableCell>
                  <TableCell>Statut</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {liste.data.map((b) => (
                  <TableRow key={b.id} hover sx={{ cursor: "pointer" }} onClick={() => setChoisi(b.id)}>
                    <TableCell>{b.numero}</TableCell>
                    <TableCell>{b.magasin_nom}</TableCell>
                    <TableCell>{b.organisme_nom}</TableCell>
                    <TableCell align="right">{b.prises_en_charge.length}</TableCell>
                    <TableCell align="right">{formaterTexte(b.total, b)}</TableCell>
                    <TableCell align="right">{b.total_regle ? formaterTexte(b.total_regle, b) : "—"}</TableCell>
                    <TableCell>
                      {b.statut_libelle}
                      {b.envoye_le && b.statut === "envoye" && ` le ${dateCourte(b.envoye_le)}`}
                      {b.regle_le && ` le ${dateCourte(b.regle_le)}`}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Stack>
      </CardContent>
      {nouveau && <Preparation onFermer={() => setNouveau(false)} onCree={(id) => setChoisi(id)} />}
      {bordereau && (
        <Detail
          key={`${bordereau.statut}-${bordereau.prises_en_charge.map((p) => p.id).join()}`}
          bordereau={bordereau}
          preparer={preparer}
          regler={regler}
          onFermer={() => setChoisi(null)}
        />
      )}
    </Card>
  );
}

function TableauPec({
  pecs,
  monnaie,
  coches,
  onCocher,
}: {
  pecs: PecBordereau[];
  monnaie: Monnaie;
  coches?: Set<string>;
  onCocher?: (id: string) => void;
}) {
  return (
    <Table size="small" aria-label="Prises en charge">
      <TableHead>
        <TableRow>
          {coches && <TableCell padding="checkbox" />}
          <TableCell>Facture</TableCell>
          <TableCell>Client</TableCell>
          <TableCell>N° dossier</TableCell>
          <TableCell align="right">Part organisme</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {pecs.map((p) => (
          <TableRow key={p.id}>
            {coches && (
              <TableCell padding="checkbox">
                <Checkbox
                  checked={coches.has(p.id)}
                  onChange={() => onCocher?.(p.id)}
                  slotProps={{ input: { "aria-label": `Inclure ${p.vente_numero}` } }}
                />
              </TableCell>
            )}
            <TableCell>
              {p.vente_numero}
              <Typography variant="caption" sx={{ display: "block" }} color="text.secondary">
                {dateCourte(p.vente_date)}
              </Typography>
            </TableCell>
            <TableCell>
              {p.client ?? "—"}
              {p.numero_affilie && (
                <Typography variant="caption" sx={{ display: "block" }} color="text.secondary">
                  N° affilié {p.numero_affilie}
                </Typography>
              )}
            </TableCell>
            <TableCell>{p.numero_dossier || "—"}</TableCell>
            <TableCell align="right">{formaterTexte(p.montant, monnaie)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

const basculer = (ensemble: Set<string>, id: string) => {
  const suivant = new Set(ensemble);
  if (suivant.has(id)) suivant.delete(id);
  else suivant.add(id);
  return suivant;
};

function Preparation({ onFermer, onCree }: { onFermer: () => void; onCree: (id: string) => void }) {
  const queryClient = useQueryClient();
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const organismes = useQuery({ queryKey: ["organismes"], queryFn: listerOrganismes });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = magasins.data?.find((m) => m.id === magasinChoisi) ?? magasins.data?.[0];
  const [organisme, setOrganisme] = useState("");
  const [coches, setCoches] = useState<Set<string>>(new Set());
  const [observation, setObservation] = useState("");
  const pecs = useQuery({
    queryKey: ["pec-a-envoyer", magasin?.id, organisme],
    queryFn: () => pecAEnvoyer(magasin!.id, organisme),
    enabled: Boolean(magasin && organisme),
  });
  const creation = useMutation({
    mutationFn: () =>
      preparerBordereau({ magasin: magasin!.id, organisme, prises_en_charge: [...coches], observation }),
    onSuccess: (b) => {
      void queryClient.invalidateQueries({ queryKey: ["bordereaux-pec"] });
      void queryClient.invalidateQueries({ queryKey: ["prises-en-charge"] });
      onFermer();
      onCree(b.id);
    },
  });
  const monnaie = { devise: magasin?.pays.devise ?? "TND", decimales: magasin?.pays.decimales ?? 3 };

  return (
    <Dialog open onClose={onFermer} fullWidth maxWidth="md">
      <DialogTitle>Nouveau bordereau</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <Stack direction="row" spacing={2}>
            {(magasins.data?.length ?? 0) > 1 && (
              <TextField
                select
                size="small"
                label="Magasin"
                value={magasin?.id ?? ""}
                onChange={(ev) => {
                  setMagasin(ev.target.value);
                  setCoches(new Set());
                }}
                sx={{ minWidth: 200 }}
              >
                {magasins.data?.map((m) => (
                  <MenuItem key={m.id} value={m.id}>
                    {m.nom}
                  </MenuItem>
                ))}
              </TextField>
            )}
            <TextField
              select
              size="small"
              label="Organisme"
              value={organisme}
              onChange={(ev) => {
                setOrganisme(ev.target.value);
                setCoches(new Set());
              }}
              sx={{ minWidth: 260 }}
            >
              {organismes.data?.map((o) => (
                <MenuItem key={o.id} value={o.id}>
                  {o.nom} · {o.type_libelle}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
          {pecs.data?.length === 0 && (
            <Typography color="text.secondary">Aucune prise en charge à envoyer pour cet organisme.</Typography>
          )}
          {pecs.data && pecs.data.length > 0 && (
            <>
              <Stack direction="row" spacing={1}>
                <Button size="small" onClick={() => setCoches(new Set(pecs.data.map((p) => p.id)))}>
                  Tout cocher
                </Button>
                <Button size="small" onClick={() => setCoches(new Set())}>
                  Tout décocher
                </Button>
              </Stack>
              <TableauPec
                pecs={pecs.data}
                monnaie={monnaie}
                coches={coches}
                onCocher={(id) => setCoches((c) => basculer(c, id))}
              />
            </>
          )}
          <TextField
            size="small"
            label="Observation"
            value={observation}
            onChange={(ev) => setObservation(ev.target.value)}
          />
          {creation.isError && <Alert severity="error">{creation.error.message}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onFermer}>Annuler</Button>
        <Button
          variant="contained"
          disabled={coches.size === 0 || creation.isPending}
          onClick={() => creation.mutate()}
        >
          Créer le bordereau ({coches.size})
        </Button>
      </DialogActions>
    </Dialog>
  );
}

type Saisie = { montant: string; motif: string };

function Detail({
  bordereau: b,
  preparer,
  regler,
  onFermer,
}: {
  bordereau: Bordereau;
  preparer: boolean;
  regler: boolean;
  onFermer: () => void;
}) {
  const queryClient = useQueryClient();
  const [modification, setModification] = useState(false);
  const [coches, setCoches] = useState<Set<string>>(new Set(b.prises_en_charge.map((p) => p.id)));
  const [envoiLe, setEnvoiLe] = useState(aujourdhui());
  const [regleLe, setRegleLe] = useState(aujourdhui());
  const [mode, setMode] = useState<ModeReglementBordereau>("virement");
  const [reference, setReference] = useState("");
  const [saisies, setSaisies] = useState<Record<string, Saisie>>(
    Object.fromEntries(b.prises_en_charge.map((p) => [p.id, { montant: p.montant, motif: "" }])),
  );
  const autres = useQuery({
    queryKey: ["pec-a-envoyer", b.magasin, b.organisme],
    queryFn: () => pecAEnvoyer(b.magasin, b.organisme),
    enabled: modification,
  });
  const rafraichir = () => {
    void queryClient.invalidateQueries({ queryKey: ["bordereaux-pec"] });
    void queryClient.invalidateQueries({ queryKey: ["prises-en-charge"] });
    void queryClient.invalidateQueries({ queryKey: ["pec-a-envoyer"] });
  };
  const action = useMutation({
    mutationFn: (quoi: "modifier" | "supprimer" | "envoyer" | "regler"): Promise<unknown> => {
      if (quoi === "modifier") return modifierBordereau(b.id, [...coches]);
      if (quoi === "supprimer") return supprimerBordereau(b.id);
      if (quoi === "envoyer") return envoyerBordereau(b.id, envoiLe);
      return reglerBordereau(b.id, {
        le: regleLe,
        mode,
        reference,
        lignes: b.prises_en_charge.map((p) => ({
          prise_en_charge: p.id,
          montant_regle: saisies[p.id].montant.replace(",", "."),
          motif_rejet: saisies[p.id].motif,
        })),
      });
    },
    onSuccess: (_, quoi) => {
      rafraichir();
      if (quoi === "supprimer") onFermer();
      if (quoi === "modifier") setModification(false);
    },
  });
  const saisir = (id: string, champ: keyof Saisie, valeur: string) =>
    setSaisies((s) => ({ ...s, [id]: { ...s[id], [champ]: valeur } }));
  const totalSaisi = b.prises_en_charge.reduce((t, p) => t + Number(saisies[p.id].montant.replace(",", ".") || 0), 0);

  return (
    <Dialog open onClose={onFermer} fullWidth maxWidth="md">
      <DialogTitle>
        Bordereau {b.numero} · {b.organisme_nom} · {b.statut_libelle}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={2}>
          <Typography>
            {b.magasin_nom} · {b.prises_en_charge.length} dossiers · demandé {formaterTexte(b.total, b)}
            {b.total_regle &&
              ` · réglé ${formaterTexte(b.total_regle, b)} (${b.mode_reglement_libelle}${b.reference_reglement ? ` ${b.reference_reglement}` : ""})`}
          </Typography>
          <Stack direction="row" spacing={1}>
            <Button startIcon={<Print />} onClick={() => imprimer(pageBordereau(b))}>
              Imprimer le bordereau
            </Button>
            <Button startIcon={<Print />} onClick={() => imprimer(pageFacturesPec(b))}>
              Imprimer les factures
            </Button>
          </Stack>

          {b.statut === "preparation" && modification && autres.data && (
            <TableauPec
              pecs={[...b.prises_en_charge, ...autres.data]}
              monnaie={b}
              coches={coches}
              onCocher={(id) => setCoches((c) => basculer(c, id))}
            />
          )}
          {b.statut === "preparation" && !modification && <TableauPec pecs={b.prises_en_charge} monnaie={b} />}
          {b.statut === "preparation" && preparer && !modification && (
            <Stack direction="row" spacing={2} sx={{ alignItems: "center", flexWrap: "wrap" }} useFlexGap>
              <Button onClick={() => setModification(true)}>Ajouter ou retirer des dossiers</Button>
              <Button color="error" onClick={() => action.mutate("supprimer")} disabled={action.isPending}>
                Supprimer le bordereau
              </Button>
              {regler && (
                <>
                  <TextField
                    size="small"
                    type="date"
                    label="Envoyé le"
                    value={envoiLe}
                    onChange={(ev) => setEnvoiLe(ev.target.value)}
                    slotProps={{ inputLabel: { shrink: true } }}
                  />
                  <Button variant="contained" onClick={() => action.mutate("envoyer")} disabled={action.isPending}>
                    Marquer envoyé
                  </Button>
                </>
              )}
            </Stack>
          )}
          {b.statut === "preparation" && modification && (
            <Stack direction="row" spacing={1}>
              <Button onClick={() => setModification(false)}>Annuler</Button>
              <Button
                variant="contained"
                disabled={coches.size === 0 || action.isPending}
                onClick={() => action.mutate("modifier")}
              >
                Enregistrer ({coches.size} dossiers)
              </Button>
            </Stack>
          )}

          {b.statut === "envoye" && regler && (
            <>
              <Typography variant="subtitle1">Règlement de l'organisme</Typography>
              <Typography variant="body2" color="text.secondary">
                Indiquez ce que l'organisme a payé pour chaque dossier. Un dossier payé en moins ou rejeté demande un
                motif ; l'écart revient à la charge du client.
              </Typography>
              <Table size="small" aria-label="Règlement">
                <TableHead>
                  <TableRow>
                    <TableCell>Facture</TableCell>
                    <TableCell>Client</TableCell>
                    <TableCell align="right">Demandé</TableCell>
                    <TableCell>Réglé</TableCell>
                    <TableCell>Motif du rejet</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {b.prises_en_charge.map((p) => (
                    <TableRow key={p.id}>
                      <TableCell>{p.vente_numero}</TableCell>
                      <TableCell>{p.client ?? "—"}</TableCell>
                      <TableCell align="right">{formaterTexte(p.montant, b)}</TableCell>
                      <TableCell>
                        <TextField
                          size="small"
                          value={saisies[p.id].montant}
                          onChange={(ev) => saisir(p.id, "montant", ev.target.value)}
                          slotProps={{ htmlInput: { "aria-label": `Réglé ${p.vente_numero}`, inputMode: "decimal" } }}
                          sx={{ width: 120 }}
                        />
                      </TableCell>
                      <TableCell>
                        {Number(saisies[p.id].montant.replace(",", ".")) < Number(p.montant) && (
                          <TextField
                            size="small"
                            value={saisies[p.id].motif}
                            onChange={(ev) => saisir(p.id, "motif", ev.target.value)}
                            slotProps={{ htmlInput: { "aria-label": `Motif ${p.vente_numero}` } }}
                          />
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <Stack direction="row" spacing={2} sx={{ alignItems: "center", flexWrap: "wrap" }} useFlexGap>
                <TextField
                  size="small"
                  type="date"
                  label="Réglé le"
                  value={regleLe}
                  onChange={(ev) => setRegleLe(ev.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
                <TextField
                  select
                  size="small"
                  label="Mode"
                  value={mode}
                  onChange={(ev) => setMode(ev.target.value as ModeReglementBordereau)}
                  sx={{ minWidth: 140 }}
                >
                  <MenuItem value="virement">Virement</MenuItem>
                  <MenuItem value="cheque">Chèque</MenuItem>
                </TextField>
                <TextField
                  size="small"
                  label="Référence (n° virement ou chèque)"
                  value={reference}
                  onChange={(ev) => setReference(ev.target.value)}
                />
                <Typography>Total : {formaterTexte(totalSaisi.toFixed(b.decimales), b)}</Typography>
                <Button variant="contained" onClick={() => action.mutate("regler")} disabled={action.isPending}>
                  Enregistrer le règlement
                </Button>
              </Stack>
            </>
          )}
          {b.statut !== "preparation" && !(b.statut === "envoye" && regler) && (
            <Table size="small" aria-label="Dossiers du bordereau">
              <TableHead>
                <TableRow>
                  <TableCell>Facture</TableCell>
                  <TableCell>Client</TableCell>
                  <TableCell align="right">Demandé</TableCell>
                  <TableCell align="right">Réglé</TableCell>
                  <TableCell>Statut</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {b.prises_en_charge.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell>{p.vente_numero}</TableCell>
                    <TableCell>{p.client ?? "—"}</TableCell>
                    <TableCell align="right">{formaterTexte(p.montant, b)}</TableCell>
                    <TableCell align="right">{p.montant_regle ? formaterTexte(p.montant_regle, b) : "—"}</TableCell>
                    <TableCell>
                      {p.statut_libelle}
                      {p.motif_rejet && ` · ${p.motif_rejet}`}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {action.isError && <Alert severity="error">{action.error.message}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onFermer}>Fermer</Button>
      </DialogActions>
    </Dialog>
  );
}
