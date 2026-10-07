import ContentCopy from "@mui/icons-material/ContentCopy";
import Search from "@mui/icons-material/Search";
import Alert from "@mui/material/Alert";
import Autocomplete from "@mui/material/Autocomplete";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import FormControlLabel from "@mui/material/FormControlLabel";
import IconButton from "@mui/material/IconButton";
import MenuItem from "@mui/material/MenuItem";
import Paper from "@mui/material/Paper";
import Radio from "@mui/material/Radio";
import RadioGroup from "@mui/material/RadioGroup";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import {
  chercherArticles,
  listerLunettesClient,
  VISIONS,
  type Article,
  type Famille,
  type RoleLigne,
  type SaisieLunette,
  type Vision,
} from "../api/caisse";
import {
  listerPrescriptions,
  saisirPrescription,
  type Client,
  type MesureOeil,
  type Prescription,
} from "../api/clients";
import { enUnites, formater, type Monnaie } from "../api/monnaie";
import { RechercheVerres } from "./RechercheVerres";

/** Article placé dans une lunette (monture, verre d'un œil ou supplément). */
export type ArticleLunette = {
  article: Article;
  role: RoleLigne;
  remise_pct: string;
};

const BORDEAUX = "#8b1414";
export const NOUVELLE = "nouvelle";

type Correction = {
  sphere: string;
  cylindre: string;
  axe: string;
  addition: string;
};
const CORRECTION_VIDE: Correction = {
  sphere: "",
  cylindre: "",
  axe: "",
  addition: "",
};
type Montage = { ecart: string; hauteur: string; ecart_pres: string };
const MONTAGE_VIDE: Montage = { ecart: "", hauteur: "", ecart_pres: "" };

const versCorrection = (m: MesureOeil): Correction => ({
  sphere: m.sphere ?? "",
  cylindre: m.cylindre ?? "",
  axe: m.axe == null ? "" : String(m.axe),
  addition: m.addition ?? "",
});

/** Correction de près : la sphère de loin plus l'addition, même cylindre et même axe. */
function pres(c: Correction) {
  if (!c.sphere || !c.addition) return null;
  const sphere = Number(c.sphere) + Number(c.addition);
  return { ...c, sphere: (sphere > 0 ? "+" : "") + sphere.toFixed(2) };
}

export const signe = (valeur: string) =>
  valeur && Number(valeur) > 0 && !valeur.startsWith("+") ? `+${valeur}` : valeur;
const ou = (valeur: string) => (valeur.trim() === "" ? null : valeur.trim());

/** Code-barres tapé ou lu à la douchette (qui finit par Entrée) : l'article est choisi aussitôt. */
export function CodeBarres({
  magasin,
  famille,
  onTrouve,
}: {
  magasin: string;
  famille: Famille;
  onTrouve: (article: Article) => void;
}) {
  const [code, setCode] = useState("");
  const [introuvable, setIntrouvable] = useState(false);

  async function scanner() {
    const saisi = code.trim();
    if (!saisi) return;
    const trouves = await chercherArticles(magasin, saisi, famille);
    const article = trouves.find((a) => a.code_barres === saisi || a.reference === saisi);
    setIntrouvable(!article);
    if (article) {
      onTrouve(article);
      setCode("");
    }
  }

  return (
    <TextField
      size="small"
      label="Code"
      value={code}
      error={introuvable}
      helperText={introuvable ? "Code inconnu" : "Douchette ou saisie + Entrée"}
      onChange={(e) => {
        setCode(e.target.value);
        setIntrouvable(false);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          void scanner();
        }
      }}
      sx={{ width: 170, bgcolor: "#fffde7" }}
    />
  );
}

/** Choix d'un article d'une famille par sa référence, son libellé ou sa marque. */
export function ChoixArticle({
  magasin,
  famille,
  label,
  valeur,
  onChange,
  monnaie,
}: {
  magasin: string;
  famille: Famille;
  label: string;
  valeur: Article | null;
  onChange: (article: Article | null) => void;
  monnaie: Monnaie;
}) {
  const [saisie, setSaisie] = useState("");
  const articles = useQuery({
    queryKey: ["articles", magasin, famille, saisie],
    queryFn: () => chercherArticles(magasin, saisie, famille),
    enabled: Boolean(magasin),
  });

  return (
    <Autocomplete
      size="small"
      options={articles.data ?? []}
      value={valeur}
      onChange={(_, article) => onChange(article)}
      inputValue={saisie}
      onInputChange={(_, texte) => setSaisie(texte)}
      filterOptions={(options) => options}
      getOptionLabel={(a) => a.libelle}
      isOptionEqualToValue={(a, b) => a.id === b.id}
      getOptionDisabled={(a) => !a.sur_commande && !a.stock}
      renderOption={({ key, ...props }, a) => (
        <li key={key} {...props}>
          <Stack sx={{ width: "100%" }}>
            <Typography variant="body2">
              {a.libelle} · {formater(enUnites(a.prix_vente_ttc, monnaie.decimales), monnaie)}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {[a.reference, a.description, a.sur_commande ? "sur commande" : `stock ${a.stock ?? "?"}`]
                .filter(Boolean)
                .join(" · ")}
            </Typography>
          </Stack>
        </li>
      )}
      noOptionsText="Aucun article"
      renderInput={(params) => <TextField {...params} label={label} />}
      sx={{ flex: 1, minWidth: 220, bgcolor: "#fffde7" }}
    />
  );
}

export function Champ({
  label,
  valeur,
  onChange,
  largeur = 72,
  lectureSeule = false,
}: {
  label: string;
  valeur: string;
  onChange?: (valeur: string) => void;
  largeur?: number;
  lectureSeule?: boolean;
}) {
  return (
    <TextField
      size="small"
      label={label}
      value={valeur}
      onChange={(e) => onChange?.(e.target.value)}
      slotProps={{
        htmlInput: { readOnly: lectureSeule, inputMode: "decimal" },
      }}
      sx={{ width: largeur, bgcolor: lectureSeule ? "grey.100" : "#fffde7" }}
    />
  );
}

export function Cadre({ titre, children }: { titre: ReactNode; children: ReactNode }) {
  return (
    <Paper variant="outlined" sx={{ p: 1.5, flex: 1, minWidth: 0 }}>
      <Typography
        variant="subtitle1"
        sx={{
          color: "error.main",
          fontWeight: 600,
          textAlign: "center",
          mb: 1,
        }}
      >
        {titre}
      </Typography>
      {children}
    </Paper>
  );
}

/** Une ligne de correction (loin ou près) d'un œil, puis les mesures de montage. */
function Oeil({
  titre,
  correction,
  onCorrection,
  montage,
  onMontage,
  saisieLibre,
  hauteur,
}: {
  titre: string;
  correction: Correction;
  onCorrection: (c: Correction) => void;
  montage: Montage;
  onMontage: (m: Montage) => void;
  saisieLibre: boolean;
  hauteur: string;
}) {
  const p = pres(correction);
  const changer = (cle: keyof Correction) => (v: string) => onCorrection({ ...correction, [cle]: v });
  return (
    <Cadre titre={titre}>
      <Stack spacing={1.5}>
        <Stack direction="row" useFlexGap spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
          <Typography sx={{ width: 34, color: "text.secondary" }}>Loin</Typography>
          <Champ
            label="Sph"
            valeur={signe(correction.sphere)}
            onChange={changer("sphere")}
            lectureSeule={!saisieLibre}
          />
          <Champ
            label="Cyl"
            valeur={signe(correction.cylindre)}
            onChange={changer("cylindre")}
            lectureSeule={!saisieLibre}
          />
          <Champ
            label="Axe"
            valeur={correction.axe}
            onChange={changer("axe")}
            largeur={56}
            lectureSeule={!saisieLibre}
          />
          <Champ
            label="Add"
            valeur={signe(correction.addition)}
            onChange={changer("addition")}
            lectureSeule={!saisieLibre}
          />
          <Champ label="E.I.P" valeur={montage.ecart} onChange={(v) => onMontage({ ...montage, ecart: v })} />
          <Champ label={hauteur} valeur={montage.hauteur} onChange={(v) => onMontage({ ...montage, hauteur: v })} />
        </Stack>
        <Box sx={{ height: 4, bgcolor: "#40d9d0", borderRadius: 1 }} />
        <Stack direction="row" useFlexGap spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
          <Typography sx={{ width: 34, color: "text.secondary" }}>Près</Typography>
          <Champ label="Sph" valeur={p ? p.sphere : ""} lectureSeule />
          <Champ label="Cyl" valeur={p ? signe(p.cylindre) : ""} lectureSeule />
          <Champ label="Axe" valeur={p ? p.axe : ""} largeur={56} lectureSeule />
          <Champ
            label="E.I.P près"
            valeur={montage.ecart_pres}
            largeur={96}
            onChange={(v) => onMontage({ ...montage, ecart_pres: v })}
          />
        </Stack>
      </Stack>
    </Cadre>
  );
}

/** Verre d'un œil : le verre, ses suppléments (traitements…), la remise et le total. */
function Verre({
  titre,
  magasin,
  monnaie,
  verre,
  onVerre,
  supplements,
  onSupplements,
  remise,
  onRemise,
  peutRemiser,
  copier,
  correction,
}: {
  titre: string;
  magasin: string;
  monnaie: Monnaie;
  verre: Article | null;
  onVerre: (a: Article | null) => void;
  supplements: Article[];
  onSupplements: (a: Article[]) => void;
  remise: string;
  onRemise: (r: string) => void;
  peutRemiser: boolean;
  copier?: () => void;
  /** Correction de l'œil : la recherche ne garde que les plages de verres qui la couvrent. */
  correction: Correction;
}) {
  const [ajout, setAjout] = useState<Article | null>(null);
  const [recherche, setRecherche] = useState(false);
  const unites = (a: Article | null) => (a ? enUnites(a.prix_vente_ttc, monnaie.decimales) : 0);
  const prixTraitement = supplements.reduce((s, a) => s + unites(a), 0);
  const total = Math.round((unites(verre) + prixTraitement) * (1 - Number(remise || 0) / 100));
  return (
    <Cadre titre={titre}>
      <Stack spacing={1}>
        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <ChoixArticle
            magasin={magasin}
            famille="verre"
            label="Verre"
            valeur={verre}
            onChange={onVerre}
            monnaie={monnaie}
          />
          <Tooltip title="Recherche des verres : stock fournisseur, prescription et stock du magasin">
            <IconButton aria-label={`Rechercher le ${titre.toLowerCase()}`} onClick={() => setRecherche(true)}>
              <Search />
            </IconButton>
          </Tooltip>
          {copier && (
            <Tooltip title="Même verre et mêmes suppléments que l'œil droit">
              <IconButton aria-label="Copier le verre droit" onClick={copier}>
                <ContentCopy />
              </IconButton>
            </Tooltip>
          )}
        </Stack>
        <ChoixArticle
          magasin={magasin}
          famille="supplement"
          label="Ajouter un supplément"
          valeur={ajout}
          monnaie={monnaie}
          onChange={(a) => {
            if (a && !supplements.some((s) => s.id === a.id)) onSupplements([...supplements, a]);
            setAjout(null);
          }}
        />
        {supplements.length > 0 && (
          <Stack direction="row" sx={{ flexWrap: "wrap", gap: 0.5 }}>
            {supplements.map((s) => (
              <Button
                key={s.id}
                size="small"
                variant="outlined"
                onClick={() => onSupplements(supplements.filter((x) => x.id !== s.id))}
                title="Retirer ce supplément"
              >
                {s.libelle} ✕
              </Button>
            ))}
          </Stack>
        )}
        <Stack direction="row" useFlexGap spacing={1} sx={{ flexWrap: "wrap" }}>
          <Champ label="Prix verre" valeur={formater(unites(verre), monnaie)} largeur={128} lectureSeule />
          <Champ label="Prix trait." valeur={formater(prixTraitement, monnaie)} largeur={128} lectureSeule />
          {peutRemiser && <Champ label="Rem. %" valeur={remise} onChange={onRemise} largeur={80} />}
          <Champ label="Total" valeur={formater(total, monnaie)} largeur={128} lectureSeule />
        </Stack>
        {verre?.plage && (
          <Typography variant="caption" color="text.secondary">
            {verre.description}
          </Typography>
        )}
      </Stack>
      <RechercheVerres
        ouvert={recherche}
        titre={titre}
        magasin={magasin}
        monnaie={monnaie}
        correction={{ sphere: correction.sphere, cylindre: correction.cylindre }}
        onChoisir={onVerre}
        onFerme={() => setRecherche(false)}
      />
    </Cadre>
  );
}

/**
 * Fiche « Montures + Verres » : la correction de chaque œil (reprise d'une ordonnance ou saisie),
 * les mesures de montage, la monture (scannée ou cherchée), les verres et leurs suppléments.
 * « Valider la lunette » l'ajoute à la visite ; on peut en faire plusieurs.
 */
export function FicheLunette({
  magasin,
  client,
  monnaie,
  numero,
  solaireParDefaut = false,
  droits,
  onValider,
}: {
  magasin: string;
  client: Client | null;
  monnaie: Monnaie;
  numero: number;
  solaireParDefaut?: boolean;
  droits: {
    remise: boolean;
    voirOrdonnances: boolean;
    saisirOrdonnance: boolean;
  };
  onValider: (lunette: SaisieLunette, articles: ArticleLunette[]) => void;
}) {
  const ordonnances = useQuery({
    queryKey: ["prescriptions", client?.id],
    queryFn: () => listerPrescriptions(client!.id),
    enabled: Boolean(client) && droits.voirOrdonnances,
  });
  const lunettesVendues = useQuery({
    queryKey: ["lunettes", client?.id],
    queryFn: () => listerLunettesClient(client!.id),
    enabled: Boolean(client),
  });
  const ordonnancesLunettes = (ordonnances.data ?? []).filter((o) => o.type === "lunettes");

  const [vision, setVision] = useState<Vision | "">("");
  const [solaire, setSolaire] = useState(solaireParDefaut);
  const [inadaptation, setInadaptation] = useState(false);
  const [observation, setObservation] = useState("");
  const [clientAbsent, setClientAbsent] = useState(false);
  const [ordonnance, setOrdonnance] = useState("");
  const [prescripteur, setPrescripteur] = useState("");
  const [dateOrdonnance, setDateOrdonnance] = useState("");
  const [od, setOd] = useState<Correction>(CORRECTION_VIDE);
  const [og, setOg] = useState<Correction>(CORRECTION_VIDE);
  const [montageD, setMontageD] = useState<Montage>(MONTAGE_VIDE);
  const [montageG, setMontageG] = useState<Montage>(MONTAGE_VIDE);
  const [oeilDirecteur, setOeilDirecteur] = useState<"" | "droit" | "gauche">("");
  const [monture, setMonture] = useState<Article | null>(null);
  const [remiseMonture, setRemiseMonture] = useState("");
  const [verreD, setVerreD] = useState<Article | null>(null);
  const [verreG, setVerreG] = useState<Article | null>(null);
  const [supplementsD, setSupplementsD] = useState<Article[]>([]);
  const [supplementsG, setSupplementsG] = useState<Article[]>([]);
  const [remiseD, setRemiseD] = useState("");
  const [remiseG, setRemiseG] = useState("");
  const [erreur, setErreur] = useState("");
  const [envoi, setEnvoi] = useState(false);

  const saisieLibre = ordonnance === NOUVELLE;
  const unites = (a: Article | null) => (a ? enUnites(a.prix_vente_ttc, monnaie.decimales) : 0);
  const apresRemise = (montant: number, remise: string) => Math.round(montant * (1 - Number(remise || 0) / 100));
  const totalD = apresRemise(unites(verreD) + supplementsD.reduce((s, a) => s + unites(a), 0), remiseD);
  const totalG = apresRemise(unites(verreG) + supplementsG.reduce((s, a) => s + unites(a), 0), remiseG);
  const totalMonture = apresRemise(unites(monture), remiseMonture);
  const avecVerres = Boolean(verreD || verreG);

  function choisirOrdonnance(id: string) {
    setOrdonnance(id);
    const choisie = ordonnancesLunettes.find((o) => o.id === id);
    if (choisie) {
      setOd(versCorrection(choisie.mesures.od));
      setOg(versCorrection(choisie.mesures.og));
      if (choisie.mesures.ecart_pupillaire && !montageD.ecart && !montageG.ecart) {
        const demi = (Number(choisie.mesures.ecart_pupillaire) / 2).toFixed(1);
        setMontageD({ ...montageD, ecart: demi });
        setMontageG({ ...montageG, ecart: demi });
      }
    } else {
      setOd(CORRECTION_VIDE);
      setOg(CORRECTION_VIDE);
    }
  }

  function copierVerreDroit() {
    setVerreG(verreD);
    setSupplementsG(supplementsD);
    setRemiseG(remiseD);
  }

  async function enregistrerOrdonnance(): Promise<Prescription> {
    const oeil = (c: Correction): MesureOeil => ({
      sphere: c.sphere || "0",
      cylindre: c.cylindre || "0",
      axe: c.axe ? Number(c.axe) : null,
      addition: c.addition || null,
    });
    return saisirPrescription({
      client: client!.id,
      magasin_saisie: magasin,
      type: "lunettes",
      date_prescription: dateOrdonnance,
      prescripteur,
      prescripteur_identifiant: "",
      mesures: { od: oeil(od), og: oeil(og) },
    });
  }

  async function valider() {
    setErreur("");
    if (!monture && !avecVerres) return setErreur("Choisir au moins une monture ou un verre.");
    if (avecVerres && !solaire && !ordonnance)
      return setErreur(
        client
          ? "Choisir l'ordonnance du client, ou saisir une nouvelle ordonnance."
          : "Choisir d'abord le client : la correction va sur sa fiche.",
      );
    if (saisieLibre && (!prescripteur || !dateOrdonnance || !od.sphere || !og.sphere))
      return setErreur("Nouvelle ordonnance : ophtalmologiste, date et sphère de chaque œil.");
    setEnvoi(true);
    try {
      const prescription = saisieLibre ? (await enregistrerOrdonnance()).id : ordonnance || null;
      const articles: ArticleLunette[] = [];
      const ajouter = (article: Article | null, role: RoleLigne, remise: string) => {
        if (article) articles.push({ article, role, remise_pct: remise || "0" });
      };
      ajouter(monture, "monture", remiseMonture);
      ajouter(verreD, "verre_d", remiseD);
      ajouter(verreG, "verre_g", remiseG);
      if (verreD) supplementsD.forEach((a) => ajouter(a, "supplement_d", remiseD));
      if (verreG) supplementsG.forEach((a) => ajouter(a, "supplement_g", remiseG));
      onValider(
        {
          vision,
          solaire,
          inadaptation,
          prescription,
          oeil_directeur: oeilDirecteur,
          ecart_d: ou(montageD.ecart),
          ecart_g: ou(montageG.ecart),
          ecart_pres_d: ou(montageD.ecart_pres),
          ecart_pres_g: ou(montageG.ecart_pres),
          hauteur_d: ou(montageD.hauteur),
          hauteur_g: ou(montageG.hauteur),
          observation,
          client_absent: clientAbsent,
        },
        articles,
      );
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <Stack spacing={2} aria-label="Montures et verres">
      <Paper variant="outlined" sx={{ p: 1, bgcolor: "#fff9c4" }}>
        <Stack direction="row" sx={{ alignItems: "center", flexWrap: "wrap", columnGap: 2 }}>
          <Typography sx={{ fontWeight: 700, color: "text.secondary" }}>Vision</Typography>
          <RadioGroup row value={vision} onChange={(e) => setVision(e.target.value as Vision)} aria-label="Vision">
            {VISIONS.map((v) => (
              <FormControlLabel key={v.valeur} value={v.valeur} control={<Radio size="small" />} label={v.libelle} />
            ))}
          </RadioGroup>
        </Stack>
      </Paper>

      <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ alignItems: { md: "flex-start" } }}>
        <Stack spacing={1.5} sx={{ flex: 1 }}>
          <Typography variant="h6" component="h3" sx={{ color: BORDEAUX }}>
            Lunette n° {numero}
          </Typography>
          {droits.voirOrdonnances ? (
            <TextField
              select
              size="small"
              label="Ordonnance (ophtalmo)"
              value={ordonnance}
              onChange={(e) => choisirOrdonnance(e.target.value)}
              disabled={!client}
              helperText={client ? undefined : "Choisir un client pour reprendre ou saisir son ordonnance"}
            >
              <MenuItem value="">Sans ordonnance</MenuItem>
              {ordonnancesLunettes.map((o) => (
                <MenuItem key={o.id} value={o.id}>
                  {o.prescripteur} · {new Date(o.date_prescription).toLocaleDateString("fr-FR")}
                </MenuItem>
              ))}
              {droits.saisirOrdonnance && <MenuItem value={NOUVELLE}>Nouvelle ordonnance…</MenuItem>}
            </TextField>
          ) : (
            <Typography color="text.secondary">Votre rôle ne donne pas accès aux ordonnances.</Typography>
          )}
          {saisieLibre && (
            <Stack direction="row" spacing={1}>
              <TextField
                size="small"
                label="Ophtalmologiste"
                value={prescripteur}
                onChange={(e) => setPrescripteur(e.target.value)}
                sx={{ flex: 1 }}
              />
              <TextField
                size="small"
                type="date"
                label="Date ord."
                value={dateOrdonnance}
                onChange={(e) => setDateOrdonnance(e.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
              />
            </Stack>
          )}
        </Stack>
        <Stack spacing={1} sx={{ minWidth: 220 }}>
          <RadioGroup
            row
            value={solaire ? "solaire" : "optique"}
            onChange={(e) => setSolaire(e.target.value === "solaire")}
            aria-label="Solaire ou optique"
          >
            <FormControlLabel value="solaire" control={<Radio size="small" />} label="Solaire" />
            <FormControlLabel value="optique" control={<Radio size="small" />} label="Optique" />
          </RadioGroup>
          <FormControlLabel
            control={
              <Checkbox size="small" checked={inadaptation} onChange={(e) => setInadaptation(e.target.checked)} />
            }
            label="Inadaptation"
          />
        </Stack>
        <TextField
          size="small"
          label="Obs."
          multiline
          minRows={2}
          value={observation}
          onChange={(e) => setObservation(e.target.value)}
          sx={{ flex: 1 }}
        />
      </Stack>

      <Stack direction={{ xs: "column", lg: "row" }} spacing={2}>
        <Oeil
          titre="Œil droit"
          correction={od}
          onCorrection={setOd}
          montage={montageD}
          onMontage={setMontageD}
          saisieLibre={saisieLibre}
          hauteur="HD"
        />
        <Oeil
          titre="Œil gauche"
          correction={og}
          onCorrection={setOg}
          montage={montageG}
          onMontage={setMontageG}
          saisieLibre={saisieLibre}
          hauteur="HG"
        />
      </Stack>

      <Stack direction="row" sx={{ alignItems: "center", flexWrap: "wrap", columnGap: 2 }}>
        <Typography color="text.secondary">Œil directeur</Typography>
        <RadioGroup
          row
          value={oeilDirecteur}
          onChange={(e) => setOeilDirecteur(e.target.value as "droit" | "gauche")}
          aria-label="Œil directeur"
        >
          <FormControlLabel value="droit" control={<Radio size="small" />} label="Droit" />
          <FormControlLabel value="gauche" control={<Radio size="small" />} label="Gauche" />
        </RadioGroup>
      </Stack>

      <Stack direction="row" useFlexGap spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
        <CodeBarres magasin={magasin} famille="monture" onTrouve={setMonture} />
        <ChoixArticle
          magasin={magasin}
          famille="monture"
          label="Monture"
          valeur={monture}
          onChange={setMonture}
          monnaie={monnaie}
        />
        <Champ label="Prix" valeur={formater(unites(monture), monnaie)} largeur={130} lectureSeule />
        {droits.remise && <Champ label="Remise %" valeur={remiseMonture} onChange={setRemiseMonture} largeur={96} />}
      </Stack>

      <Stack direction={{ xs: "column", lg: "row" }} spacing={2}>
        <Verre
          titre="Verre droit"
          magasin={magasin}
          monnaie={monnaie}
          verre={verreD}
          onVerre={setVerreD}
          supplements={supplementsD}
          onSupplements={setSupplementsD}
          remise={remiseD}
          onRemise={setRemiseD}
          peutRemiser={droits.remise}
          correction={od}
        />
        <Verre
          titre="Verre gauche"
          magasin={magasin}
          monnaie={monnaie}
          verre={verreG}
          onVerre={setVerreG}
          supplements={supplementsG}
          onSupplements={setSupplementsG}
          remise={remiseG}
          onRemise={setRemiseG}
          peutRemiser={droits.remise}
          copier={verreD ? copierVerreDroit : undefined}
          correction={og}
        />
      </Stack>

      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ alignItems: { sm: "center" } }}>
        <FormControlLabel
          control={<Checkbox size="small" checked={clientAbsent} onChange={(e) => setClientAbsent(e.target.checked)} />}
          label="Client absent"
        />
        <Box sx={{ flex: 1 }} />
        <Typography sx={{ color: "error.main", fontWeight: 600 }}>
          Total verres : {formater(totalD + totalG, monnaie)}
        </Typography>
        <Typography variant="h6" sx={{ color: "error.main" }}>
          Total lunette : {formater(totalMonture + totalD + totalG, monnaie)}
        </Typography>
        <Button variant="contained" size="large" disabled={envoi} onClick={() => void valider()}>
          Valider la lunette
        </Button>
      </Stack>
      {erreur && <Alert severity="error">{erreur}</Alert>}

      {lunettesVendues.data && lunettesVendues.data.length > 0 && (
        <Stack spacing={1}>
          <Typography variant="subtitle2" color="primary">
            Lunettes déjà vendues à ce client
          </Typography>
          <Table size="small" aria-label="Lunettes du client">
            <TableHead>
              <TableRow>
                {["N° lunette", "Date", "Monture", "Verre droit", "Verre gauche", "Péniche", "Inadaptation"].map(
                  (t) => (
                    <TableCell key={t} sx={{ color: BORDEAUX, fontWeight: 700 }}>
                      {t}
                    </TableCell>
                  ),
                )}
              </TableRow>
            </TableHead>
            <TableBody>
              {lunettesVendues.data.map((l) => (
                <TableRow key={l.id}>
                  <TableCell>{l.id}</TableCell>
                  <TableCell>{new Date(l.date).toLocaleDateString("fr-FR")}</TableCell>
                  <TableCell>{l.monture ?? ""}</TableCell>
                  <TableCell>{l.verre_d ?? ""}</TableCell>
                  <TableCell>{l.verre_g ?? ""}</TableCell>
                  <TableCell>{l.peniche ?? ""}</TableCell>
                  <TableCell>{l.inadaptation ? "Oui" : ""}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Stack>
      )}
    </Stack>
  );
}
