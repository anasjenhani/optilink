import Delete from "@mui/icons-material/Delete";
import Print from "@mui/icons-material/Print";
import Alert from "@mui/material/Alert";
import Autocomplete from "@mui/material/Autocomplete";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import FormControlLabel from "@mui/material/FormControlLabel";
import IconButton from "@mui/material/IconButton";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Step from "@mui/material/Step";
import StepLabel from "@mui/material/StepLabel";
import Stepper from "@mui/material/Stepper";
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
import { useRef, useState } from "react";

import { type Famille, FAMILLES } from "../api/caisse";
import {
  annulerInventaire,
  type Comptage,
  compterArticle,
  type Inventaire as InventaireComplet,
  type LigneInventaire,
  lireChoixInventaire,
  lireInventaire,
  listerInventaires,
  NATURES,
  type NatureMonture,
  ouvrirInventaire,
  retirerArticle,
  reprendreComptage,
  terminerComptage,
  validerInventaire,
} from "../api/inventaires";
import { depotDabord, listerMagasins } from "../api/magasins";
import { AjoutArticle } from "./BonReception";
import { imprimer } from "./FactureAchat";
import { BANDEAU, BORDEAUX, BOUTON } from "./RechercheClients";

const ENTETE = { color: BORDEAUX, fontWeight: 700, bgcolor: "grey.100", whiteSpace: "nowrap" } as const;

export type DroitsInventaire = { ouvrir: boolean; compter: boolean; valider: boolean };

function Bandeau({ titre }: { titre: string }) {
  return (
    <Box sx={{ px: 3, py: 1, borderRadius: 1, background: BANDEAU }}>
      <Typography variant="h5" component="h3" sx={{ color: "common.white", fontWeight: 500 }}>
        {titre}
      </Typography>
    </Box>
  );
}

const couleurEcart = (ecart: number) => (ecart === 0 ? "success.main" : ecart < 0 ? "error.main" : "warning.main");
const signe = (n: number) => (n > 0 ? `+${n}` : String(n));

/** Feuille d'écarts imprimable (A4). */
export function pageInventaire(inv: InventaireComplet) {
  const e = (texte: string) =>
    texte.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] as string);
  const lignes = inv.lignes
    .map(
      (l) =>
        `<tr><td>${e(l.code_barres || l.reference)}</td><td>${e(l.libelle)}</td><td class="n">${l.stock_theorique}</td><td class="n">${l.comptee ? l.quantite_comptee : "non compté"}</td><td class="n">${signe(l.ecart)}</td><td>${e(l.observation)}</td></tr>`,
    )
    .join("");
  return `<!doctype html><html><head><meta charset="utf-8"><title>${e(inv.numero)}</title><style>
@page { size: A4; margin: 12mm; }
body { font-family: Arial, sans-serif; font-size: 10pt; }
h1 { font-size: 16pt; margin: 0 0 4mm; }
table { border-collapse: collapse; width: 100%; margin: 3mm 0; }
th, td { border: 1px solid #999; padding: 1mm 1.5mm; }
th { background: #eee; text-align: left; }
.n { text-align: right; }
</style></head><body>
<h1>Inventaire ${e(inv.numero)}</h1>
<p>${e(inv.magasin)} · ${e(inv.perimetre)} · ${e(inv.statut_libelle)}${inv.valide_le ? ` le ${new Date(inv.valide_le).toLocaleString("fr-FR")} par ${e(inv.valide_par)}` : ""}</p>
<table><thead><tr><th>Code</th><th>Article</th><th class="n">Ancienne qté</th><th class="n">Quantité</th><th class="n">Écart</th><th>Observation</th></tr></thead><tbody>${lignes}</tbody></table>
${inv.observation ? `<p>Observation : ${e(inv.observation)}</p>` : ""}
${inv.observation_validation ? `<p>Observation de validation : ${e(inv.observation_validation)}</p>` : ""}
</body></html>`;
}

/** Quantité comptée modifiable : la nouvelle valeur remplace le compté à la sortie du champ. */
function CaseComptee({
  ligne,
  actif,
  onCorrige,
}: {
  ligne: LigneInventaire;
  actif: boolean;
  onCorrige: (quantite: number) => void;
}) {
  const [saisie, setSaisie] = useState<string | null>(null);
  if (!actif) return <>{ligne.comptee ? ligne.quantite_comptee : "—"}</>;
  const valeur = saisie ?? (ligne.comptee ? String(ligne.quantite_comptee) : "");
  const enregistrer = () => {
    if (saisie !== null && saisie.trim() !== "" && Number(saisie) >= 0 && Number(saisie) !== ligne.quantite_comptee) {
      onCorrige(Number(saisie));
    }
    setSaisie(null);
  };
  return (
    <TextField
      size="small"
      value={valeur}
      placeholder="—"
      onChange={(e) => setSaisie(e.target.value.replace(/\D/g, ""))}
      onBlur={enregistrer}
      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
      slotProps={{ htmlInput: { inputMode: "numeric", "aria-label": `Compté ${ligne.libelle}` } }}
      sx={{ width: 80, "& input": { textAlign: "right", py: 0.5 } }}
    />
  );
}

/** Observation d'une ligne (article abîmé, mal étiqueté…), enregistrée à la sortie du champ. */
function CaseObservation({
  ligne,
  actif,
  onCorrige,
}: {
  ligne: LigneInventaire;
  actif: boolean;
  onCorrige: (observation: string) => void;
}) {
  const [saisie, setSaisie] = useState<string | null>(null);
  if (!actif) return <>{ligne.observation}</>;
  return (
    <TextField
      size="small"
      value={saisie ?? ligne.observation}
      onChange={(e) => setSaisie(e.target.value)}
      onBlur={() => {
        if (saisie !== null && saisie !== ligne.observation) onCorrige(saisie);
        setSaisie(null);
      }}
      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
      slotProps={{ htmlInput: { maxLength: 200, "aria-label": `Observation ${ligne.libelle}` } }}
      sx={{ width: 200, "& input": { py: 0.5 } }}
    />
  );
}

/** Comptage d'un inventaire : scan ou recherche, écarts avec le stock, validation. */
function Comptage({ id, droits, onRetour }: { id: string; droits: DroitsInventaire; onRetour: () => void }) {
  const queryClient = useQueryClient();
  const inventaire = useQuery({ queryKey: ["inventaires", id], queryFn: () => lireInventaire(id) });
  const [code, setCode] = useState("");
  const [quantite, setQuantite] = useState("1");
  const [ecartsChoisi, setEcartsSeuls] = useState<boolean | null>(null);
  const [confirmer, setConfirmer] = useState<"valider" | "annuler" | null>(null);
  const [observationFinale, setObservationFinale] = useState("");
  const [dernier, setDernier] = useState("");
  const majour = (inv: InventaireComplet) => {
    queryClient.setQueryData(["inventaires", id], inv);
    void queryClient.invalidateQueries({ queryKey: ["inventaires", "liste"] });
  };
  // Une douchette enchaîne les scans plus vite que le serveur ne répond : chaque scan est mis
  // en file et envoyé dans l'ordre, la case est vidée tout de suite pour le scan suivant.
  const champScan = useRef<HTMLInputElement>(null);
  const file = useRef<Comptage[]>([]);
  const envoiEnCours = useRef(false);
  const [enAttente, setEnAttente] = useState(0);
  const [erreurComptage, setErreurComptage] = useState<Error | null>(null);
  const reprendreScan = () => champScan.current?.focus();
  async function viderFile() {
    if (envoiEnCours.current) return;
    envoiEnCours.current = true;
    for (let c = file.current.shift(); c; c = file.current.shift()) {
      try {
        const inv = await compterArticle(id, c);
        majour(inv);
        setErreurComptage(null);
        const ligne = inv.lignes.find(
          (l) =>
            l.article === c!.article ||
            l.code_barres === c!.code ||
            l.reference.toLowerCase() === c!.code?.toLowerCase(),
        );
        setDernier(ligne ? `${ligne.libelle} : ${ligne.quantite_comptee} compté(s)` : "");
      } catch (e) {
        setErreurComptage(e instanceof Error ? e : new Error(String(e)));
      } finally {
        setEnAttente((n) => n - 1);
      }
    }
    envoiEnCours.current = false;
  }
  const compterEnFile = (c: Comptage) => {
    file.current.push(c);
    setEnAttente((n) => n + 1);
    void viderFile();
  };
  const retrait = useMutation({ mutationFn: (article: string) => retirerArticle(id, article), onSuccess: majour });
  const etape = useMutation({
    mutationFn: (quoi: "terminer" | "reprendre") =>
      quoi === "terminer" ? terminerComptage(id) : reprendreComptage(id),
    onSuccess: majour,
  });
  const fin = useMutation({
    mutationFn: (quoi: "valider" | "annuler") =>
      quoi === "valider" ? validerInventaire(id, observationFinale) : annulerInventaire(id),
    onSuccess: (inv) => {
      majour(inv);
      setConfirmer(null);
      void queryClient.invalidateQueries({ queryKey: ["articles"] });
    },
  });
  const inv = inventaire.data;
  if (!inv) {
    return inventaire.isError ? <Alert severity="error">{inventaire.error.message}</Alert> : null;
  }
  const enCours = inv.statut === "en_cours";
  const aVerifier = inv.statut === "a_verifier";
  // Pendant la vérification, seul le responsable corrige les quantités.
  const peutCompter = (enCours && droits.compter) || (aVerifier && droits.valider);
  const ecartsSeuls = ecartsChoisi ?? aVerifier;
  const lignes = ecartsSeuls ? inv.lignes.filter((l) => l.ecart !== 0) : inv.lignes;
  const somme = (f: (l: LigneInventaire) => number) => inv.lignes.reduce((s, l) => s + f(l), 0);
  const avecEcart = inv.lignes.filter((l) => l.ecart !== 0).length;
  const nonComptes = inv.lignes.filter((l) => !l.comptee).length;
  const erreur = erreurComptage ?? retrait.error ?? etape.error ?? fin.error;
  const scanner = () => {
    if (!code.trim()) return;
    compterEnFile({ code: code.trim(), quantite: Number(quantite) || 1 });
    setCode("");
    setQuantite("1");
    reprendreScan();
  };

  return (
    <Stack spacing={1.5}>
      <Bandeau titre={`Inventaire ${inv.numero}`} />
      <Typography>
        {inv.magasin} · <strong>{inv.perimetre}</strong> · créé le {new Date(inv.cree_le).toLocaleString("fr-FR")} par{" "}
        {inv.cree_par}
        {inv.observation && ` · ${inv.observation}`}
      </Typography>
      {inv.statut !== "annule" && (
        <Stepper activeStep={enCours ? 0 : aVerifier ? 1 : 3} sx={{ maxWidth: 760 }}>
          {["Comptage", "Vérification et correction", "Validation finale"].map((t) => (
            <Step key={t}>
              <StepLabel>{t}</StepLabel>
            </Step>
          ))}
        </Stepper>
      )}
      <Typography
        color={enCours || aVerifier ? "warning.main" : inv.statut === "valide" ? "success.main" : "text.secondary"}
        sx={{ fontWeight: 700 }}
      >
        {enCours
          ? "Comptage en cours. Un article en stock non compté sera mis à 0 à la validation."
          : aVerifier
            ? `Comptage terminé le ${new Date(inv.comptage_termine_le!).toLocaleString("fr-FR")} par ${inv.comptage_termine_par} : vérifiez les écarts, corrigez les quantités recomptées et notez les observations.`
            : inv.statut === "valide"
              ? `Validé le ${new Date(inv.valide_le!).toLocaleString("fr-FR")} par ${inv.valide_par} : le stock a été corrigé.`
              : "Inventaire annulé : le stock n'a pas été modifié."}
      </Typography>
      {inv.observation_validation && (
        <Typography variant="body2">
          <strong>Observation de validation :</strong> {inv.observation_validation}
        </Typography>
      )}
      {peutCompter && (
        <Stack direction="row" spacing={1.5} useFlexGap sx={{ flexWrap: "wrap", alignItems: "center" }}>
          <TextField
            size="small"
            autoFocus
            inputRef={champScan}
            label="Code barre ou référence"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                scanner();
              }
            }}
            sx={{ width: 260, bgcolor: "#fffde7" }}
          />
          <TextField
            size="small"
            label="Quantité"
            value={quantite}
            onChange={(e) => setQuantite(e.target.value.replace(/\D/g, ""))}
            slotProps={{ htmlInput: { inputMode: "numeric" } }}
            sx={{ width: 90 }}
          />
          <Button variant="contained" disabled={!code.trim()} onClick={scanner}>
            Compter
          </Button>
          <Box sx={{ flex: 1, minWidth: 300 }}>
            <AjoutArticle
              magasin={inv.magasin_id}
              famille={inv.famille}
              avecStock
              onAjoute={(a) => {
                compterEnFile({ article: a.id, quantite: Number(quantite) || 1 });
                setQuantite("1");
                reprendreScan();
              }}
            />
          </Box>
        </Stack>
      )}
      {dernier && peutCompter && !erreurComptage && (
        <Typography variant="body2" color="success.main">
          {dernier}
          {enAttente > 0 && ` · ${enAttente} scan(s) en cours d'enregistrement`}
        </Typography>
      )}
      {erreur && <Alert severity="error">{erreur.message}</Alert>}
      <FormControlLabel
        control={<Checkbox size="small" checked={ecartsSeuls} onChange={(e) => setEcartsSeuls(e.target.checked)} />}
        label="Afficher seulement les écarts"
      />
      <TableContainer sx={{ maxHeight: 520, border: 1, borderColor: "grey.400", borderRadius: 1 }}>
        <Table stickyHeader size="small" aria-label="Articles de l'inventaire">
          <TableHead>
            <TableRow>
              <TableCell sx={ENTETE}>Code</TableCell>
              <TableCell sx={ENTETE}>Article</TableCell>
              <TableCell sx={ENTETE} align="right">
                Ancienne qté
              </TableCell>
              <TableCell sx={ENTETE} align="right">
                Quantité
              </TableCell>
              <TableCell sx={ENTETE} align="right">
                Écart
              </TableCell>
              <TableCell sx={ENTETE}>Observation</TableCell>
              {peutCompter && <TableCell sx={ENTETE} />}
            </TableRow>
          </TableHead>
          <TableBody>
            {lignes.map((l) => (
              <TableRow key={l.article} sx={l.comptee ? undefined : { bgcolor: "#fff3e0" }}>
                <TableCell>{l.code_barres || l.reference}</TableCell>
                <TableCell>
                  {l.libelle}
                  {!l.comptee && (
                    <Typography component="span" variant="caption" color="warning.main" sx={{ ml: 1 }}>
                      (non compté)
                    </Typography>
                  )}
                </TableCell>
                <TableCell align="right">{l.stock_theorique}</TableCell>
                <TableCell align="right">
                  <CaseComptee
                    ligne={l}
                    actif={peutCompter}
                    onCorrige={(q) => compterEnFile({ article: l.article, quantite: q, remplacer: true })}
                  />
                </TableCell>
                <TableCell align="right" sx={{ color: couleurEcart(l.ecart), fontWeight: 700 }}>
                  {signe(l.ecart)}
                </TableCell>
                <TableCell>
                  <CaseObservation
                    ligne={l}
                    actif={peutCompter}
                    onCorrige={(observation) =>
                      compterEnFile({
                        article: l.article,
                        quantite: l.quantite_comptee,
                        remplacer: true,
                        observation,
                      })
                    }
                  />
                </TableCell>
                {peutCompter && (
                  <TableCell padding="checkbox">
                    {l.comptee && (
                      <IconButton
                        size="small"
                        aria-label={`Retirer ${l.libelle}`}
                        onClick={() => retrait.mutate(l.article)}
                      >
                        <Delete fontSize="small" />
                      </IconButton>
                    )}
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
          {inv.lignes.length > 0 && (
            <TableFooter>
              <TableRow sx={{ "& td": { fontWeight: 700, color: "text.primary", fontSize: 14, bgcolor: "grey.100" } }}>
                <TableCell colSpan={2}>
                  {inv.lignes.length} article(s) · {avecEcart} avec écart
                  {enCours && nonComptes > 0 && ` · ${nonComptes} non compté(s)`}
                </TableCell>
                <TableCell align="right">{somme((l) => l.stock_theorique)}</TableCell>
                <TableCell align="right">{somme((l) => l.quantite_comptee)}</TableCell>
                <TableCell align="right">{signe(somme((l) => l.ecart))}</TableCell>
                <TableCell />
                {peutCompter && <TableCell />}
              </TableRow>
            </TableFooter>
          )}
        </Table>
        {inv.lignes.length === 0 && (
          <Box sx={{ p: 2 }}>
            <Typography color="text.secondary">Aucun article en stock ni compté.</Typography>
          </Box>
        )}
      </TableContainer>
      <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end" }}>
        <Button sx={BOUTON} onClick={onRetour}>
          Retour à la liste
        </Button>
        <Button startIcon={<Print />} onClick={() => imprimer(pageInventaire(inv))}>
          Imprimer
        </Button>
        {(enCours || aVerifier) && droits.valider && (
          <Button color="error" onClick={() => setConfirmer("annuler")}>
            Annuler l'inventaire
          </Button>
        )}
        {enCours && droits.valider && (
          <Button variant="contained" disabled={etape.isPending} onClick={() => etape.mutate("terminer")}>
            Terminer le comptage
          </Button>
        )}
        {aVerifier && droits.valider && (
          <>
            <Button sx={BOUTON} disabled={etape.isPending} onClick={() => etape.mutate("reprendre")}>
              Reprendre le comptage
            </Button>
            <Button variant="contained" onClick={() => setConfirmer("valider")}>
              Validation finale
            </Button>
          </>
        )}
      </Stack>
      {confirmer && (
        <Dialog open onClose={() => setConfirmer(null)}>
          <DialogTitle>{confirmer === "valider" ? "Validation finale" : "Annuler l'inventaire ?"}</DialogTitle>
          <DialogContent>
            <Stack spacing={2}>
              <Typography>
                {confirmer === "valider"
                  ? `Le stock de ${inv.magasin} sera corrigé pour ${avecEcart} article(s) avec écart${nonComptes ? `, dont ${nonComptes} non compté(s) mis à 0` : ""}. Cette opération est définitive.`
                  : "Le comptage sera abandonné ; le stock ne change pas."}
              </Typography>
              {confirmer === "valider" && (
                <TextField
                  label="Observation de validation"
                  required
                  multiline
                  minRows={3}
                  value={observationFinale}
                  onChange={(e) => setObservationFinale(e.target.value)}
                  helperText="Obligatoire : explication des écarts, recomptages, articles abîmés…"
                />
              )}
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setConfirmer(null)}>Retour</Button>
            <Button
              variant="contained"
              color={confirmer === "valider" ? "primary" : "error"}
              disabled={fin.isPending || (confirmer === "valider" && !observationFinale.trim())}
              onClick={() => fin.mutate(confirmer)}
            >
              {confirmer === "valider" ? "Valider et corriger le stock" : "Annuler l'inventaire"}
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </Stack>
  );
}

/** « Inventaire » : créer un comptage (magasin ou dépôt ; tout le stock, une famille, une marque, une nature de
 * monture ou un fournisseur) et suivre les inventaires. */
export function Inventaire({ droits }: { droits: DroitsInventaire }) {
  const queryClient = useQueryClient();
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const liste = magasins.data ? depotDabord(magasins.data) : undefined;
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = liste?.find((m) => m.id === magasinChoisi) ?? liste?.[0];
  const [famille, setFamille] = useState<Famille | "">("");
  const [marque, setMarque] = useState("");
  const [nature, setNature] = useState<NatureMonture | "">("");
  const [fournisseur, setFournisseur] = useState("");
  const [observation, setObservation] = useState("");
  const choix = useQuery({ queryKey: ["inventaires", "choix"], queryFn: lireChoixInventaire, enabled: droits.ouvrir });
  const montures = Boolean(marque.trim() || nature);
  const [ouvert, setOuvert] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const inventaires = useQuery({
    queryKey: ["inventaires", "liste", page],
    queryFn: () => listerInventaires(page),
    placeholderData: keepPreviousData,
  });
  const ouverture = useMutation({
    mutationFn: () =>
      ouvrirInventaire({
        magasin: magasin!.id,
        famille: montures ? "monture" : famille,
        marque: marque.trim(),
        nature,
        fournisseur: fournisseur || null,
        observation,
      }),
    onSuccess: (inv) => {
      queryClient.setQueryData(["inventaires", inv.id], inv);
      void queryClient.invalidateQueries({ queryKey: ["inventaires", "liste"] });
      setObservation("");
      setMarque("");
      setNature("");
      setFournisseur("");
      setOuvert(inv.id);
    },
  });
  if (ouvert) return <Comptage id={ouvert} droits={droits} onRetour={() => setOuvert(null)} />;
  const pages = Math.max(1, Math.ceil((inventaires.data?.count ?? 0) / 50));

  return (
    <Stack spacing={1.5}>
      <Bandeau titre="Liste des Inventaires" />
      {droits.ouvrir && (
        <Stack direction="row" spacing={1.5} useFlexGap sx={{ flexWrap: "wrap", alignItems: "center" }}>
          <TextField
            select
            size="small"
            label="Magasin"
            value={magasin?.id ?? ""}
            onChange={(e) => setMagasin(e.target.value)}
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
            label="Famille"
            value={montures ? "monture" : famille}
            disabled={montures}
            onChange={(e) => setFamille(e.target.value as Famille | "")}
            sx={{ width: 200 }}
            slotProps={{ select: { displayEmpty: true }, inputLabel: { shrink: true } }}
          >
            <MenuItem value="">Tout le stock</MenuItem>
            {FAMILLES.map((f) => (
              <MenuItem key={f.valeur} value={f.valeur}>
                {f.libelle}
              </MenuItem>
            ))}
          </TextField>
          <Autocomplete
            freeSolo
            size="small"
            options={choix.data?.marques ?? []}
            inputValue={marque}
            onInputChange={(_, texte) => setMarque(texte)}
            renderInput={(params) => <TextField {...params} label="Marque monture" />}
            sx={{ width: 200 }}
          />
          <TextField
            select
            size="small"
            label="Nature"
            value={nature}
            onChange={(e) => setNature(e.target.value as NatureMonture | "")}
            sx={{ width: 180 }}
            slotProps={{ select: { displayEmpty: true }, inputLabel: { shrink: true } }}
          >
            <MenuItem value="">Toutes</MenuItem>
            {NATURES.map((n) => (
              <MenuItem key={n.valeur} value={n.valeur}>
                {n.libelle}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            size="small"
            label="Fournisseur"
            value={fournisseur}
            onChange={(e) => setFournisseur(e.target.value)}
            sx={{ width: 200 }}
            slotProps={{ select: { displayEmpty: true }, inputLabel: { shrink: true } }}
          >
            <MenuItem value="">Tous</MenuItem>
            {(choix.data?.fournisseurs ?? []).map((f) => (
              <MenuItem key={f.id} value={f.id}>
                {f.nom}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            size="small"
            label="Observation"
            value={observation}
            onChange={(e) => setObservation(e.target.value)}
            sx={{ width: 300 }}
          />
          <Button variant="contained" disabled={!magasin || ouverture.isPending} onClick={() => ouverture.mutate()}>
            Créer un inventaire
          </Button>
        </Stack>
      )}
      {ouverture.isError && <Alert severity="error">{ouverture.error.message}</Alert>}
      {inventaires.isError && <Alert severity="error">{inventaires.error.message}</Alert>}
      <TableContainer sx={{ maxHeight: 520, border: 1, borderColor: "grey.400", borderRadius: 1 }}>
        <Table stickyHeader size="small" aria-label="Inventaires">
          <TableHead>
            <TableRow>
              {[
                "Numéro inventaire",
                "Création",
                "Magasin",
                "Périmètre",
                "Statut",
                "Articles comptés",
                "Créé par",
                "Validé par",
              ].map((t) => (
                <TableCell key={t} sx={ENTETE}>
                  {t}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {inventaires.data?.results.map((i) => (
              <TableRow
                key={i.id}
                hover
                onClick={() => setOuvert(i.id)}
                sx={{ cursor: "pointer", "& td": { borderColor: "#d9a3a3", whiteSpace: "nowrap" } }}
              >
                <TableCell>{i.numero}</TableCell>
                <TableCell>{new Date(i.cree_le).toLocaleString("fr-FR")}</TableCell>
                <TableCell>{i.magasin}</TableCell>
                <TableCell>{i.perimetre}</TableCell>
                <TableCell
                  sx={{
                    color:
                      i.statut === "en_cours" || i.statut === "a_verifier"
                        ? "warning.main"
                        : i.statut === "valide"
                          ? "success.main"
                          : undefined,
                    fontWeight: 700,
                  }}
                >
                  {i.statut_libelle}
                </TableCell>
                <TableCell align="right">{i.articles_comptes}</TableCell>
                <TableCell>{i.cree_par}</TableCell>
                <TableCell>{i.valide_par}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {inventaires.data?.count === 0 && (
          <Box sx={{ p: 2 }}>
            <Typography color="text.secondary">Aucun inventaire.</Typography>
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
    </Stack>
  );
}
