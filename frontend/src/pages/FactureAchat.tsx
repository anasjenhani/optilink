import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
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
import TableFooter from "@mui/material/TableFooter";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Tabs from "@mui/material/Tabs";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import Download from "@mui/icons-material/Download";
import Print from "@mui/icons-material/Print";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { derniersPrix, type Fournisseur } from "../api/achats";
import {
  apercuFacture,
  bonsAFacturer,
  type BonFacture,
  enregistrerFacture,
  type FactureAchat as Facture,
  type LigneFacture,
  type LigneTva,
  type SaisieFactureAchat,
  type Totaux,
} from "../api/facturesAchat";
import { listerMagasins } from "../api/magasins";
import { formaterTexte, type Monnaie } from "../api/monnaie";
import { ChoixFournisseur } from "./BonReception";
import { BANDEAU, BORDEAUX, BOUTON, useApaise } from "./RechercheClients";

const ONGLETS = [
  { famille: "monture", libelle: "Monture" },
  { famille: "lentille", libelle: "Lentille" },
  { famille: "divers", libelle: "Article Divers / Produit" },
  { famille: "verre", libelle: "Verre" },
  { famille: "supplement", libelle: "Suppléments Verres" },
] as const;

const aujourdhui = () => new Date().toISOString().slice(0, 10);
export const dateCourte = (iso: string) =>
  iso ? new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString("fr-FR") : "";
const nombre = (texte: string) => texte.replace(",", ".").trim();

const ENTETE = { color: BORDEAUX, fontWeight: 700, bgcolor: "grey.100", whiteSpace: "nowrap" } as const;

/** BL du fournisseur pas encore facturés, à cocher (« Importer BL »). */
function ImportBl({
  magasin,
  fournisseur,
  deja,
  monnaie,
  onImporte,
  onFerme,
}: {
  magasin: string;
  fournisseur: Fournisseur;
  deja: Set<string>;
  monnaie: Monnaie;
  onImporte: (bons: BonFacture[], timbre: string) => void;
  onFerme: () => void;
}) {
  const liste = useQuery({
    queryKey: ["factures-achat", "a-facturer", magasin, fournisseur.id],
    queryFn: () => bonsAFacturer(magasin, fournisseur.id),
  });
  const disponibles = (liste.data?.bons ?? []).filter((b) => !deja.has(b.id));
  const [choisis, setChoisis] = useState<Set<string>>(new Set());
  const basculer = (id: string) =>
    setChoisis((c) => {
      const suite = new Set(c);
      if (suite.has(id)) suite.delete(id);
      else suite.add(id);
      return suite;
    });
  return (
    <Dialog open onClose={onFerme} maxWidth="md" fullWidth>
      <DialogTitle>BL de {fournisseur.nom} à facturer</DialogTitle>
      <DialogContent>
        {liste.isError && <Alert severity="error">{liste.error.message}</Alert>}
        {liste.data && disponibles.length === 0 && (
          <Typography color="text.secondary">Aucun bon de réception de ce fournisseur à facturer.</Typography>
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
                    onChange={(e) => setChoisis(new Set(e.target.checked ? disponibles.map((b) => b.id) : []))}
                  />
                </TableCell>
                <TableCell>N° BL</TableCell>
                <TableCell>Bon de réception</TableCell>
                <TableCell>Date BL</TableCell>
                <TableCell align="right">Net HT</TableCell>
                <TableCell align="right">TTC</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {disponibles.map((b) => (
                <TableRow key={b.id} hover onClick={() => basculer(b.id)} sx={{ cursor: "pointer" }}>
                  <TableCell padding="checkbox">
                    <Checkbox
                      size="small"
                      checked={choisis.has(b.id)}
                      slotProps={{ input: { "aria-label": `BL ${b.numero_bl}` } }}
                    />
                  </TableCell>
                  <TableCell>{b.numero_bl}</TableCell>
                  <TableCell>{b.numero}</TableCell>
                  <TableCell>{dateCourte(b.date_bl)}</TableCell>
                  <TableCell align="right">{formaterTexte(b.total_net_ht, monnaie)}</TableCell>
                  <TableCell align="right">{formaterTexte(b.total_ttc, monnaie)}</TableCell>
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
            onImporte(
              disponibles.filter((b) => choisis.has(b.id)),
              liste.data?.timbre_fiscal ?? "0",
            );
            onFerme();
          }}
        >
          Importer
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export function TableBons({
  bons,
  monnaie,
  onRetirer,
}: {
  bons: BonFacture[];
  monnaie: Monnaie;
  onRetirer?: (id: string) => void;
}) {
  const m = (v: string) => formaterTexte(v, monnaie);
  const somme = (cle: keyof BonFacture) => bons.reduce((s, b) => s + Number(b[cle]), 0).toFixed(monnaie.decimales);
  return (
    <TableContainer sx={{ border: 1, borderColor: "grey.400", borderRadius: 1, maxHeight: 220 }}>
      <Table size="small" stickyHeader aria-label="Bons de livraison">
        <TableHead>
          <TableRow>
            <TableCell sx={ENTETE}>Référence</TableCell>
            <TableCell sx={ENTETE}>Bon Livraison</TableCell>
            <TableCell sx={ENTETE}>Date</TableCell>
            <TableCell sx={ENTETE} align="right">
              Remise Ex
            </TableCell>
            <TableCell sx={ENTETE} align="right">
              Total Fodec
            </TableCell>
            <TableCell sx={ENTETE} align="right">
              Total Net HT
            </TableCell>
            <TableCell sx={ENTETE} align="right">
              Total TVA
            </TableCell>
            <TableCell sx={ENTETE} align="right">
              Total TTC
            </TableCell>
            {onRetirer && <TableCell sx={ENTETE} />}
          </TableRow>
        </TableHead>
        <TableBody>
          {bons.map((b) => (
            <TableRow key={b.id}>
              <TableCell>{b.numero_bl}</TableCell>
              <TableCell>{b.numero}</TableCell>
              <TableCell>{dateCourte(b.date_bl)}</TableCell>
              <TableCell align="right">{m(b.remise_ex)}</TableCell>
              <TableCell align="right">{m(b.total_fodec)}</TableCell>
              <TableCell align="right">{m(b.total_net_ht)}</TableCell>
              <TableCell align="right">{m(b.total_tva)}</TableCell>
              <TableCell align="right">{m(b.total_ttc)}</TableCell>
              {onRetirer && (
                <TableCell>
                  <Button size="small" onClick={() => onRetirer(b.id)}>
                    Retirer
                  </Button>
                </TableCell>
              )}
            </TableRow>
          ))}
        </TableBody>
        {bons.length > 0 && (
          <TableFooter>
            <TableRow sx={{ "& td": { fontWeight: 700, color: "text.primary", bgcolor: "grey.100" } }}>
              <TableCell colSpan={3}>{bons.length} BL</TableCell>
              <TableCell align="right">{m(somme("remise_ex"))}</TableCell>
              <TableCell align="right">{m(somme("total_fodec"))}</TableCell>
              <TableCell align="right">{m(somme("total_net_ht"))}</TableCell>
              <TableCell align="right">{m(somme("total_tva"))}</TableCell>
              <TableCell align="right">{m(somme("total_ttc"))}</TableCell>
              {onRetirer && <TableCell />}
            </TableRow>
          </TableFooter>
        )}
      </Table>
    </TableContainer>
  );
}

export function TableLignes({
  lignes,
  monnaie,
  magasin,
}: {
  lignes: LigneFacture[];
  monnaie: Monnaie;
  magasin?: string;
}) {
  const [onglet, setOnglet] = useState(() =>
    Math.max(
      0,
      ONGLETS.findIndex((o) => o.famille === lignes[0]?.famille),
    ),
  );
  const [choisie, setChoisie] = useState<number | null>(null);
  const famille = ONGLETS[onglet].famille;
  const visibles = lignes.filter((l) => l.famille === famille);
  const ligne = choisie === null ? undefined : visibles[choisie];
  const prix = useQuery({
    queryKey: ["derniers-prix", magasin, ligne?.article],
    queryFn: () => derniersPrix(magasin as string, [ligne!.article]),
    enabled: Boolean(magasin && ligne),
  });
  const m = (v: string) => formaterTexte(v, monnaie);
  const dernier = ligne && prix.data?.[ligne.article]?.dernier_prix_achat;
  return (
    <Stack spacing={1}>
      <Tabs
        value={onglet}
        onChange={(_, o: number) => {
          setOnglet(o);
          setChoisie(null);
        }}
        variant="scrollable"
      >
        {ONGLETS.map((o) => {
          const n = lignes.filter((l) => l.famille === o.famille).length;
          return <Tab key={o.famille} label={n ? `${o.libelle} (${n})` : o.libelle} />;
        })}
      </Tabs>
      <TableContainer sx={{ border: 1, borderColor: "grey.400", borderRadius: 1, maxHeight: 300 }}>
        <Table size="small" stickyHeader aria-label="Lignes de la facture">
          <TableHead>
            <TableRow>
              {[
                "Code",
                "Désignation",
                "Etui",
                "Quantité",
                "Prix Achat HT",
                "Montant HT",
                "Taux Remise",
                "Montant Remise",
                "Montant Net HT",
                "Taux TVA",
                "Montant TTC",
                "N° Série",
              ].map((t, i) => (
                <TableCell key={t} sx={ENTETE} align={i >= 3 && i <= 10 ? "right" : "left"}>
                  {t}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {visibles.map((l, i) => (
              <TableRow
                key={`${l.bon}-${i}`}
                hover
                selected={choisie === i}
                onClick={() => setChoisie(i)}
                sx={{ cursor: "pointer" }}
              >
                <TableCell>{l.code}</TableCell>
                <TableCell>{l.designation}</TableCell>
                <TableCell>{l.etui ? "Oui" : ""}</TableCell>
                <TableCell align="right">{l.quantite}</TableCell>
                <TableCell align="right">{m(l.prix_achat_ht)}</TableCell>
                <TableCell align="right">{m(l.montant_ht)}</TableCell>
                <TableCell align="right">{Number(l.taux_remise).toFixed(2)}</TableCell>
                <TableCell align="right">{m(l.montant_remise)}</TableCell>
                <TableCell align="right">{m(l.net_ht)}</TableCell>
                <TableCell align="right">{Number(l.taux_tva).toFixed(2)}</TableCell>
                <TableCell align="right">{m(l.montant_ttc)}</TableCell>
                <TableCell>{l.numero_serie}</TableCell>
              </TableRow>
            ))}
          </TableBody>
          {visibles.length > 0 && (
            <TableFooter>
              <TableRow sx={{ "& td": { fontWeight: 700, color: "text.primary", bgcolor: "grey.100" } }}>
                <TableCell colSpan={3} />
                <TableCell align="right">{visibles.reduce((s, l) => s + l.quantite, 0)}</TableCell>
                <TableCell colSpan={8} />
              </TableRow>
            </TableFooter>
          )}
        </Table>
        {visibles.length === 0 && (
          <Box sx={{ p: 2 }}>
            <Typography color="text.secondary">Aucun article dans cet onglet.</Typography>
          </Box>
        )}
      </TableContainer>
      {magasin && (
        <Typography>
          Dernier prix d'achat HT :{" "}
          <Box component="strong" sx={{ color: "error.main" }}>
            {ligne ? (dernier ? m(dernier) : "—") : "choisir une ligne"}
          </Box>
          {ligne && ` · remise ${Number(ligne.taux_remise).toFixed(2)} %`}
        </Typography>
      )}
    </Stack>
  );
}

export function TableTva({ lignes, monnaie }: { lignes: LigneTva[]; monnaie: Monnaie }) {
  return (
    <Table size="small" aria-label="Détail TVA" sx={{ maxWidth: 380, "& td, & th": { p: 0.5 } }}>
      <TableHead>
        <TableRow>
          <TableCell sx={ENTETE} align="right">
            Base HT
          </TableCell>
          <TableCell sx={ENTETE} align="right">
            Taux TVA
          </TableCell>
          <TableCell sx={ENTETE} align="right">
            Montant TVA
          </TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {lignes.map((t) => (
          <TableRow key={t.taux}>
            <TableCell align="right">{formaterTexte(t.base_ht, monnaie)}</TableCell>
            <TableCell align="right">{Number(t.taux).toFixed(2)}</TableCell>
            <TableCell align="right">{formaterTexte(t.montant_tva, monnaie)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

const lectureSeule = { htmlInput: { readOnly: true } };

/** Totaux à droite : comme l'onglet « Information » de l'ancien logiciel. */
export function BlocTotaux({
  totaux,
  monnaie,
  saisie,
}: {
  totaux: Totaux | undefined;
  monnaie: Monnaie;
  saisie: {
    tauxRemiseEx: string;
    frais: string;
    timbre: string;
    onTauxRemiseEx?: (v: string) => void;
    onFrais?: (v: string) => void;
    onTimbre?: (v: string) => void;
  };
}) {
  const m = (v: string | undefined) => (v === undefined ? "" : formaterTexte(v, monnaie));
  const champ = (label: string, valeur: string, onChange?: (v: string) => void, rouge = false) => (
    <TextField
      size="small"
      label={label}
      value={valeur}
      onChange={onChange ? (e) => onChange(e.target.value) : undefined}
      slotProps={onChange ? { htmlInput: { inputMode: "decimal" } } : lectureSeule}
      sx={{
        width: 210,
        ...(onChange ? {} : { bgcolor: "grey.100" }),
        ...(rouge ? { "& input": { color: BORDEAUX, fontWeight: 700 } } : {}),
      }}
    />
  );
  return (
    <Stack direction="row" spacing={3} useFlexGap sx={{ flexWrap: "wrap" }}>
      <Stack spacing={1.5}>
        {champ("Total HT", m(totaux?.total_ht))}
        {champ("Total Remise", m(totaux?.total_remise))}
        {champ("Taux Remise Ex %", saisie.tauxRemiseEx, saisie.onTauxRemiseEx)}
        {champ("Remise Ex", m(totaux?.remise_ex))}
        {champ("Frais Supplémentaires", saisie.onFrais ? saisie.frais : m(saisie.frais), saisie.onFrais)}
      </Stack>
      <Stack spacing={1.5}>
        {champ("Total Net HT", m(totaux?.total_net_ht))}
        {champ("Total TVA", m(totaux?.total_tva))}
        {champ("Total Fodec", m(totaux?.total_fodec))}
        {champ("Timbre Fiscal", saisie.onTimbre ? saisie.timbre : m(saisie.timbre), saisie.onTimbre)}
        {champ("Total TTC", m(totaux?.total_ttc), undefined, true)}
      </Stack>
    </Stack>
  );
}

/** « Facture Achat » : la facture du fournisseur regroupe ses BL déjà reçus (bons de réception). */
export function FactureAchat() {
  const queryClient = useQueryClient();
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = magasins.data?.find((m) => m.id === magasinChoisi) ?? magasins.data?.[0];
  const monnaie: Monnaie = { devise: magasin?.pays.devise ?? "TND", decimales: magasin?.pays.decimales ?? 3 };
  const [fournisseur, setFournisseur] = useState<Fournisseur | null>(null);
  const [reference, setReference] = useState("");
  const [dateReference, setDateReference] = useState("");
  const [bons, setBons] = useState<BonFacture[]>([]);
  const [tauxRemiseEx, setTauxRemiseEx] = useState("0");
  const [frais, setFrais] = useState("0");
  const [timbre, setTimbre] = useState("0");
  const [ajustement, setAjustement] = useState("0");
  const [totalPapier, setTotalPapier] = useState("");
  const [observation, setObservation] = useState("");
  const [ongletBas, setOngletBas] = useState(0);
  const [ongletHaut, setOngletHaut] = useState(0);
  const [importer, setImporter] = useState(false);
  const [message, setMessage] = useState("");

  const saisie: SaisieFactureAchat | null =
    magasin && fournisseur
      ? {
          magasin: magasin.id,
          fournisseur: fournisseur.id,
          reference_fournisseur: reference,
          date_reference: dateReference,
          bons: bons.map((b) => b.id),
          taux_remise_ex: nombre(tauxRemiseEx) || "0",
          frais_supplementaires: nombre(frais) || "0",
          timbre_fiscal: nombre(timbre) || "0",
          ajustement: nombre(ajustement) || "0",
          observation,
        }
      : null;
  // Texte stable : l'aperçu ne se recalcule qu'après une pause dans la saisie.
  const calcul = useApaise(JSON.stringify(saisie));
  const apercu = useQuery({
    queryKey: ["factures-achat", "apercu", calcul],
    queryFn: () => apercuFacture(JSON.parse(calcul) as SaisieFactureAchat),
    enabled: Boolean(saisie && bons.length && calcul !== "null"),
    placeholderData: keepPreviousData,
  });
  const totaux = bons.length ? apercu.data : undefined;

  const vider = () => {
    setFournisseur(null);
    setReference("");
    setDateReference("");
    setBons([]);
    setTauxRemiseEx("0");
    setFrais("0");
    setTimbre("0");
    setAjustement("0");
    setTotalPapier("");
    setObservation("");
  };
  const validation = useMutation({
    mutationFn: () => enregistrerFacture(saisie!),
    onSuccess: (facture) => {
      setMessage(
        `Facture achat ${facture.numero} enregistrée (${facture.reference_fournisseur}, ${formaterTexte(facture.total_ttc, monnaie)} TTC, ${facture.bons.length} BL).`,
      );
      vider();
      for (const cle of ["factures-achat", "bons-reception"]) void queryClient.invalidateQueries({ queryKey: [cle] });
    },
  });
  const manque = !fournisseur
    ? "Choisissez le fournisseur."
    : !reference.trim()
      ? "Saisissez la référence fournisseur (n° de sa facture)."
      : !dateReference
        ? "Saisissez la date de la facture fournisseur."
        : bons.length === 0
          ? "Importez au moins un BL."
          : "";

  return (
    <Stack spacing={1.5}>
      <Box sx={{ px: 3, py: 1, borderRadius: 1, background: BANDEAU }}>
        <Typography variant="h5" component="h3" sx={{ color: "common.white", fontWeight: 500 }}>
          Facture Achat
        </Typography>
      </Box>

      <Stack spacing={1.5}>
        <Stack direction="row" spacing={1.5} useFlexGap sx={{ flexWrap: "wrap", alignItems: "center" }}>
          <Stack direction="row" spacing={1.5}>
            <TextField
              size="small"
              label="Numéro Facture Achat"
              value="Attribué à la validation"
              slotProps={lectureSeule}
              sx={{ width: 200 }}
            />
            <TextField
              size="small"
              type="date"
              label="Date d'entrée"
              value={aujourdhui()}
              slotProps={{ inputLabel: { shrink: true }, htmlInput: { readOnly: true } }}
            />
          </Stack>
          <ChoixFournisseur
            valeur={fournisseur}
            onChange={(f) => {
              setFournisseur(f);
              setBons([]);
            }}
            libelle="Code Fournisseur / Raison sociale"
          />
          <TextField
            size="small"
            label="Référence Fournisseur"
            placeholder="N° de sa facture"
            value={reference}
            onChange={(e) => setReference(e.target.value)}
            sx={{ bgcolor: "#fffde7", width: 200 }}
          />
          <Stack direction="row" spacing={1.5}>
            <TextField
              size="small"
              type="date"
              label="Date Référence"
              value={dateReference}
              onChange={(e) => setDateReference(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            {magasins.data && (
              <TextField
                select
                size="small"
                label="Magasin"
                value={magasin?.id ?? ""}
                onChange={(e) => {
                  setMagasin(e.target.value);
                  setBons([]);
                }}
                sx={{ width: 200 }}
              >
                {magasins.data.map((m) => (
                  <MenuItem key={m.id} value={m.id}>
                    {m.nom}
                  </MenuItem>
                ))}
              </TextField>
            )}
          </Stack>
        </Stack>

        <Stack spacing={1} sx={{ flex: 1, minWidth: 0, width: "100%" }}>
          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            <Tabs value={ongletHaut} onChange={(_, o: number) => setOngletHaut(o)} sx={{ flex: 1 }}>
              <Tab label={`Bon Livraison${bons.length ? ` (${bons.length})` : ""}`} />
              <Tab label="Bon Retour" />
            </Tabs>
            <Button
              startIcon={<Download sx={{ color: "success.main" }} />}
              sx={BOUTON}
              disabled={!fournisseur || !magasin}
              onClick={() => setImporter(true)}
            >
              Importer BL
            </Button>
            <Button sx={BOUTON} disabled title="À venir">
              Importer BR
            </Button>
          </Stack>
          {ongletHaut === 0 ? (
            <TableBons
              bons={bons}
              monnaie={monnaie}
              onRetirer={(id) => setBons((bs) => bs.filter((b) => b.id !== id))}
            />
          ) : (
            <Typography color="text.secondary">Bons de retour fournisseur : à venir.</Typography>
          )}
        </Stack>
      </Stack>

      <TableLignes
        key={bons.map((b) => b.id).join()}
        lignes={totaux ? apercu.data!.lignes : []}
        monnaie={monnaie}
        magasin={magasin?.id}
      />

      <Stack direction={{ xs: "column", lg: "row" }} spacing={2} sx={{ alignItems: "flex-start" }}>
        <TableTva lignes={totaux ? apercu.data!.detail_tva : []} monnaie={monnaie} />
        <Box sx={{ flex: 1, border: 1, borderColor: "grey.300", borderRadius: 1, p: 1.5 }}>
          <Tabs value={ongletBas} onChange={(_, o: number) => setOngletBas(o)} sx={{ mb: 1.5 }}>
            <Tab label="Information" />
            <Tab label="Observation" />
            <Tab label="Ajustement des Totaux" />
          </Tabs>
          {ongletBas === 0 && (
            <BlocTotaux
              totaux={totaux}
              monnaie={monnaie}
              saisie={{
                tauxRemiseEx,
                frais,
                timbre,
                onTauxRemiseEx: setTauxRemiseEx,
                onFrais: setFrais,
                onTimbre: setTimbre,
              }}
            />
          )}
          {ongletBas === 1 && (
            <TextField
              label="Observation"
              multiline
              minRows={4}
              value={observation}
              onChange={(e) => setObservation(e.target.value)}
              sx={{ width: "100%", maxWidth: 700 }}
            />
          )}
          {ongletBas === 2 && (
            <Stack spacing={1.5}>
              <Typography variant="body2" color="text.secondary">
                Si le total de la facture papier diffère de quelques millimes (arrondis), saisissez-le : l'écart est
                ajouté en ajustement.
              </Typography>
              <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
                <TextField
                  size="small"
                  label="Total TTC de la facture papier"
                  value={totalPapier}
                  onChange={(e) => {
                    setTotalPapier(e.target.value);
                    const papier = Number(nombre(e.target.value));
                    if (e.target.value.trim() && !Number.isNaN(papier) && totaux) {
                      const sansAjustement = Number(totaux.total_ttc) - Number(nombre(ajustement) || 0);
                      setAjustement((papier - sansAjustement).toFixed(monnaie.decimales));
                    }
                  }}
                  sx={{ width: 230 }}
                />
                <TextField
                  size="small"
                  label="Ajustement"
                  value={ajustement}
                  onChange={(e) => setAjustement(e.target.value)}
                  sx={{ width: 160 }}
                />
              </Stack>
            </Stack>
          )}
        </Box>
      </Stack>

      {apercu.isError && <Alert severity="error">{apercu.error.message}</Alert>}
      {validation.isError && <Alert severity="error">{validation.error.message}</Alert>}
      {message && (
        <Alert severity="success" onClose={() => setMessage("")}>
          {message}
        </Alert>
      )}
      <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end", alignItems: "center" }}>
        <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
          Facture Achat : Non payé
        </Typography>
        {manque && (fournisseur || bons.length > 0) && (
          <Typography variant="body2" color="text.secondary">
            {manque}
          </Typography>
        )}
        <Button sx={BOUTON} disabled title="À venir">
          Détail Paiement
        </Button>
        <Button sx={BOUTON} onClick={vider} disabled={validation.isPending}>
          Annuler
        </Button>
        <Button
          variant="contained"
          disabled={Boolean(manque) || validation.isPending}
          onClick={() => {
            setMessage("");
            validation.mutate();
          }}
        >
          Valider
        </Button>
      </Stack>

      {importer && fournisseur && magasin && (
        <ImportBl
          magasin={magasin.id}
          fournisseur={fournisseur}
          deja={new Set(bons.map((b) => b.id))}
          monnaie={monnaie}
          onImporte={(nouveaux, timbreParDefaut) => {
            if (bons.length === 0) setTimbre(timbreParDefaut);
            setBons((bs) => [...bs, ...nouveaux]);
          }}
          onFerme={() => setImporter(false)}
        />
      )}
    </Stack>
  );
}

/** Page imprimable (A4) d'une facture achat enregistrée. */
export function pageFacture(f: Facture, monnaie: Monnaie) {
  const m = (v: string) => formaterTexte(v, monnaie);
  const e = (t: string) =>
    t.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] as string);
  const lignes = f.lignes
    .map(
      (l) =>
        `<tr><td>${e(l.code)}</td><td>${e(l.designation)}</td><td class="n">${l.quantite}</td><td class="n">${m(l.prix_achat_ht)}</td><td class="n">${Number(l.taux_remise).toFixed(2)}</td><td class="n">${m(l.net_ht)}</td><td class="n">${Number(l.taux_tva).toFixed(2)}</td><td class="n">${m(l.montant_ttc)}</td></tr>`,
    )
    .join("");
  const tva = f.detail_tva
    .filter((t) => Number(t.base_ht) || Number(t.montant_tva))
    .map(
      (t) =>
        `<tr><td class="n">${m(t.base_ht)}</td><td class="n">${Number(t.taux).toFixed(2)}</td><td class="n">${m(t.montant_tva)}</td></tr>`,
    )
    .join("");
  const total = (libelle: string, valeur: string) => `<tr><td>${libelle}</td><td class="n">${m(valeur)}</td></tr>`;
  return `<!doctype html><html><head><meta charset="utf-8"><title>${e(f.numero)}</title><style>
@page { size: A4; margin: 12mm; }
body { font-family: Arial, sans-serif; font-size: 10pt; }
h1 { font-size: 16pt; margin: 0 0 4mm; }
table { border-collapse: collapse; width: 100%; margin: 3mm 0; }
th, td { border: 1px solid #999; padding: 1mm 1.5mm; }
th { background: #eee; text-align: left; }
.n { text-align: right; }
.bas { display: flex; gap: 8mm; align-items: flex-start; }
.bas table { width: auto; }
</style></head><body>
<h1>Facture Achat ${e(f.numero)}</h1>
<p>Fournisseur : <strong>${f.fournisseur_code} · ${e(f.fournisseur)}</strong> · Référence fournisseur : <strong>${e(f.reference_fournisseur)}</strong> du ${dateCourte(f.date_reference)}<br>
Magasin : ${e(f.magasin)} · Date d'entrée : ${dateCourte(f.date_entree)} · BL : ${f.bons.map((b) => e(b.numero_bl)).join(", ")}</p>
<table><thead><tr><th>Code</th><th>Désignation</th><th class="n">Qté</th><th class="n">Prix achat HT</th><th class="n">Remise %</th><th class="n">Net HT</th><th class="n">TVA %</th><th class="n">TTC</th></tr></thead><tbody>${lignes}</tbody></table>
<div class="bas"><table><thead><tr><th class="n">Base HT</th><th class="n">Taux TVA</th><th class="n">Montant TVA</th></tr></thead><tbody>${tva}</tbody></table>
<table><tbody>${total("Total HT", f.total_ht)}${total("Total remise", f.total_remise)}${total("Remise exceptionnelle", f.remise_ex)}${total("Total net HT", f.total_net_ht)}${total("Total FODEC", f.total_fodec)}${total("Total TVA", f.total_tva)}${total("Timbre fiscal", f.timbre_fiscal)}${total("Frais supplémentaires", f.frais_supplementaires)}${Number(f.ajustement) ? total("Ajustement", f.ajustement) : ""}<tr><th>Total TTC</th><th class="n">${m(f.total_ttc)}</th></tr></tbody></table></div>
<p>Créé par ${e(f.cree_par)} le ${dateCourte(f.cree_le)} · Facture achat : ${e(f.paiement_libelle)}</p>
</body></html>`;
}

export function imprimer(html: string) {
  const cadre = document.createElement("iframe");
  cadre.setAttribute("aria-hidden", "true");
  cadre.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0";
  document.body.appendChild(cadre);
  const doc = cadre.contentDocument;
  if (!doc || !cadre.contentWindow) return;
  doc.open();
  doc.write(html);
  doc.close();
  const fenetre = cadre.contentWindow;
  fenetre.onafterprint = () => cadre.remove();
  setTimeout(() => {
    fenetre.focus();
    fenetre.print();
  }, 100);
}

export function BoutonImprimer({ facture, monnaie }: { facture: Facture; monnaie: Monnaie }) {
  return (
    <Button sx={BOUTON} startIcon={<Print />} onClick={() => imprimer(pageFacture(facture, monnaie))}>
      Imprimer
    </Button>
  );
}
