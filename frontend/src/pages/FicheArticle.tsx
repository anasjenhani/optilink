import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Checkbox from "@mui/material/Checkbox";
import Dialog from "@mui/material/Dialog";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import FormControlLabel from "@mui/material/FormControlLabel";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useEffect, useState } from "react";

import {
  type FicheArticle as Fiche,
  FABRICATIONS_VERRE,
  GEOMETRIES,
  MATIERES_VERRE,
  RENOUVELLEMENTS,
  type SaisieFiche,
  TYPES_LENTILLE,
} from "../api/fiches";
import { formaterTexte } from "../api/monnaie";
import { ChoixFournisseur } from "./BonReception";
import { EtiquetteCodeBarres } from "./EtiquetteCodeBarres";
import { nombre, OngletDetailPrix, OngletStock, PiedFiche, useFicheArticle } from "./FicheArticleCommun";
import { BORDEAUX } from "./RechercheClients";

/** Familles sans fiche monture : verres, lentilles, articles divers et suppléments verre. */
export type FamilleArticle = Exclude<Fiche["famille"], "monture">;

type Champ = {
  cle: string;
  label: string;
  nature: "texte" | "decimal" | "entier" | "case";
  options?: readonly { valeur: string; libelle: string }[];
  requis?: boolean;
  largeur?: number;
  /** Valeur d'un nouvel article. */
  defaut?: string;
};

/** Caractéristiques propres aux verres et aux lentilles, dans l'ordre de la fiche. */
const CHAMPS: Partial<Record<FamilleArticle, Champ[]>> = {
  verre: [
    { cle: "marque", label: "Marque", nature: "texte" },
    { cle: "gamme", label: "Gamme", nature: "texte", largeur: 240 },
    { cle: "geometrie", label: "Géométrie", nature: "texte", options: GEOMETRIES, requis: true, largeur: 160 },
    { cle: "indice", label: "Indice", nature: "decimal", largeur: 110 },
    { cle: "matiere", label: "Matière", nature: "texte", options: MATIERES_VERRE, largeur: 160 },
    { cle: "traitements", label: "Traitements", nature: "texte", largeur: 260 },
    { cle: "teinte", label: "Teinte", nature: "texte", largeur: 160 },
    { cle: "diametre", label: "Diamètre", nature: "entier", largeur: 110 },
    { cle: "diametre_commercial", label: "Diamètre commercial", nature: "texte", largeur: 170 },
    {
      cle: "fabrication",
      label: "Verre sur commande",
      nature: "texte",
      options: FABRICATIONS_VERRE,
      requis: true,
      largeur: 260,
      defaut: "prescription",
    },
    { cle: "photochromique", label: "Photochromique", nature: "case" },
  ],
  lentille: [
    { cle: "marque", label: "Marque", nature: "texte" },
    { cle: "modele", label: "Modèle", nature: "texte" },
    {
      cle: "renouvellement",
      label: "Renouvellement",
      nature: "texte",
      options: RENOUVELLEMENTS,
      requis: true,
      largeur: 170,
    },
    { cle: "type", label: "Type", nature: "texte", options: TYPES_LENTILLE, largeur: 150, defaut: "spherique" },
    { cle: "rayon", label: "Rayon", nature: "decimal", largeur: 100 },
    { cle: "diametre", label: "Diamètre", nature: "decimal", largeur: 100 },
    { cle: "puissance", label: "Puissance", nature: "decimal", largeur: 110 },
    { cle: "cylindre", label: "Cylindre", nature: "decimal", largeur: 100 },
    { cle: "axe", label: "Axe", nature: "entier", largeur: 90 },
    { cle: "addition", label: "Addition", nature: "decimal", largeur: 100 },
    { cle: "lentilles_par_boite", label: "Lentilles par boîte", nature: "entier", largeur: 150 },
  ],
};

const TITRES: Record<FamilleArticle, string> = {
  verre: "Fiche Verre",
  lentille: "Fiche Lentille",
  divers: "Fiche Article",
  supplement: "Fiche Supplément Verre",
};

const DESIGNATIONS: Partial<Record<FamilleArticle, string>> = {
  verre: "marque, gamme, géométrie, indice",
  lentille: "marque, modèle, renouvellement",
};

type Saisie = Record<string, string | boolean>;

const vide = (champs: Champ[]): Saisie =>
  Object.fromEntries(champs.map((c) => [c.cle, c.nature === "case" ? false : (c.defaut ?? "")]));

/**
 * Fiche d'un verre, d'une lentille ou d'un article divers, sur le modèle de la fiche monture : en-tête,
 * caractéristiques de la famille, puis onglets Détail prix, Code A Barre, Observation et Stock. Un article
 * ne se supprime pas (ventes, stock) : décocher « Actif » le retire du catalogue.
 */
export function FicheArticle({
  famille,
  article,
  magasin,
  monnaie,
  tauxTva,
  lectureSeule = false,
  onFerme,
}: {
  famille: FamilleArticle;
  /** Identifiant de l'article ; null pour un nouvel article. */
  article: string | null;
  magasin: string;
  monnaie: { devise: string; decimales: number };
  tauxTva: string[];
  lectureSeule?: boolean;
  onFerme: () => void;
}) {
  const champs = CHAMPS[famille] ?? [];
  const [carac, setCarac] = useState<Saisie>(() => vide(champs));
  const [onglet, setOnglet] = useState(0);

  const complement = (): Partial<SaisieFiche> => {
    if (!champs.length) return {};
    const valeurs = Object.fromEntries(
      champs.map((c) => {
        const v = carac[c.cle];
        if (c.nature === "case") return [c.cle, Boolean(v)];
        const texte = String(v).trim();
        if (c.nature === "decimal") return [c.cle, nombre(texte) === null ? null : texte.replace(",", ".")];
        if (c.nature === "entier") return [c.cle, texte ? Number(texte) : null];
        return [c.cle, texte];
      }),
    );
    return { [famille]: valeurs };
  };
  // Champs obligatoires de la famille ; la désignation pour un article sans caractéristiques.
  const complet = (entete: { libelle: string }) =>
    champs.every((c) => !c.requis || Boolean(carac[c.cle])) && (champs.length > 0 || Boolean(entete.libelle.trim()));

  const { fiche, entete, fournisseur, setFournisseur, prix, setPrix, enregistrement, peutValider, texte, case_ } =
    useFicheArticle({ article, magasin, tauxTva, famille, lectureSeule, complet, complement, onFerme });

  // Fiche existante : les caractéristiques de la famille une fois chargée.
  const charge = fiche.data;
  useEffect(() => {
    const valeurs = charge && (charge[famille as "verre" | "lentille"] as Record<string, unknown> | null);
    if (!valeurs) return;
    setCarac((c) => ({
      ...c,
      ...Object.fromEntries(
        Object.entries(valeurs).map(([cle, v]) => [cle, typeof v === "boolean" ? v : v === null ? "" : String(v)]),
      ),
    }));
  }, [charge, famille]);

  const champ = (c: Champ) => {
    const changer = (valeur: string | boolean) => setCarac((s) => ({ ...s, [c.cle]: valeur }));
    if (c.nature === "case")
      return (
        <FormControlLabel
          key={c.cle}
          label={c.label}
          control={
            <Checkbox
              size="small"
              checked={Boolean(carac[c.cle])}
              disabled={lectureSeule}
              onChange={(e) => changer(e.target.checked)}
            />
          }
        />
      );
    return (
      <TextField
        key={c.cle}
        select={Boolean(c.options)}
        size="small"
        label={c.label}
        required={c.requis}
        value={carac[c.cle]}
        onChange={(e) => {
          const v = e.target.value;
          changer(
            c.nature === "entier" ? v.replace(/\D/g, "") : c.nature === "decimal" ? v.replace(/[^\d.,-]/g, "") : v,
          );
        }}
        slotProps={{
          select: { readOnly: lectureSeule, displayEmpty: true },
          inputLabel: c.options ? { shrink: true } : undefined,
          htmlInput: c.options
            ? undefined
            : { readOnly: lectureSeule, inputMode: c.nature === "texte" ? undefined : "decimal" },
        }}
        sx={{ width: c.largeur ?? 200 }}
      >
        {c.options?.map((o) => (
          <MenuItem key={o.valeur} value={o.valeur}>
            {o.libelle}
          </MenuItem>
        ))}
      </TextField>
    );
  };
  const chargee = fiche.data;

  return (
    <Dialog open onClose={onFerme} maxWidth="lg" fullWidth>
      <DialogTitle sx={{ textAlign: "center", fontWeight: 700, color: BORDEAUX }}>{TITRES[famille]}</DialogTitle>
      <DialogContent>
        {fiche.isError && <Alert severity="error">{fiche.error.message}</Alert>}
        {article && fiche.isPending ? (
          <Typography color="text.secondary">Chargement…</Typography>
        ) : (
          <Stack spacing={2} sx={{ pt: 1 }}>
            <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap", alignItems: "center" }}>
              {texte("code_barres", "Code A Barre", 220, { sx: { width: 220, bgcolor: "#fff59d" } })}
              <Box sx={{ width: 420 }}>
                <ChoixFournisseur valeur={fournisseur} onChange={setFournisseur} libelle="Fournisseur" minWidth={300} />
              </Box>
            </Stack>
            {champs.length > 0 && (
              <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap", alignItems: "center" }}>
                {champs.map(champ)}
              </Stack>
            )}
            <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap" }}>
              {texte("reference", "Référence", 220, { placeholder: "attribuée si vide" })}
              {texte("reference_fournisseur", "Code chez Fournisseur")}
              {texte("libelle", "Désignation", 360, {
                placeholder: DESIGNATIONS[famille] ?? "",
                required: !champs.length,
              })}
            </Stack>

            <Tabs value={onglet} onChange={(_, o: number) => setOnglet(o)} variant="scrollable">
              <Tab label="Détail prix" />
              <Tab label="Code A Barre" />
              <Tab label="Observation" />
              <Tab label="Stock" />
            </Tabs>

            {onglet === 0 && (
              <OngletDetailPrix
                cases={
                  <>
                    {case_("est_actif", "Actif")}
                    {case_("stockable", "Stockable")}
                    {case_("suivi_numero_serie", "Numéro Série")}
                    {case_("promotion", "Promotion")}
                    {case_("fodec", "Fodec")}
                  </>
                }
                prix={prix}
                setPrix={setPrix}
                fodec={entete.fodec}
                tauxTva={tauxTva}
                monnaie={monnaie}
                dernier={chargee?.dernier_achat}
                lectureSeule={lectureSeule}
              />
            )}
            {onglet === 1 &&
              (chargee?.code_barres ? (
                <EtiquetteCodeBarres
                  code={chargee.code_barres}
                  titre={chargee.libelle}
                  reference={chargee.reference}
                  prix={chargee.prix ? formaterTexte(chargee.prix.prix_vente_ttc, monnaie) : ""}
                />
              ) : (
                <Typography color="text.secondary">
                  Pas de code-barres : saisissez-le dans l'en-tête et validez la fiche, puis rouvrez-la pour imprimer.
                </Typography>
              ))}
            {onglet === 2 && texte("observation", "Observation", 700, { multiline: true, minRows: 4 })}
            {onglet === 3 && <OngletStock chargee={chargee} />}
            {enregistrement.isError && <Alert severity="error">{enregistrement.error.message}</Alert>}
          </Stack>
        )}
      </DialogContent>
      <PiedFiche
        article={article}
        chargee={chargee}
        lectureSeule={lectureSeule}
        peutValider={peutValider}
        onValider={() => enregistrement.mutate()}
        onFerme={onFerme}
      />
    </Dialog>
  );
}
