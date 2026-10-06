import Alert from "@mui/material/Alert";
import Autocomplete from "@mui/material/Autocomplete";
import Box from "@mui/material/Box";
import Dialog from "@mui/material/Dialog";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import {
  CATEGORIES,
  type FicheMonture as Monture,
  GENRES,
  lireSuggestions,
  MATIERES,
  type Suggestions,
  TRANCHES_AGE,
  TYPES_MONTURE,
} from "../api/fiches";
import { formaterTexte } from "../api/monnaie";
import { ChoixFournisseur } from "./BonReception";
import { EtiquetteCodeBarres } from "./EtiquetteCodeBarres";
import { OngletDetailPrix, OngletStock, PiedFiche, useFicheArticle } from "./FicheArticleCommun";
import { BORDEAUX } from "./RechercheClients";

const MONTURE_VIDE: Monture = {
  categorie: "optique",
  marque: "",
  modele: "",
  couleur: "",
  couleur_verres: "",
  matiere: "",
  type: "",
  forme: "",
  genre: "",
  tranche_age: "",
  calibre: null,
  pont: null,
  branche: null,
};

/**
 * Fiche monture, comme dans l'ancien logiciel : en-tête (code, fournisseur, matière, famille…) puis
 * onglets Détail prix, Code à barre, Observation et Stock. Les prix sont ceux du pays du magasin.
 */
export function FicheMonture({
  article,
  magasin,
  monnaie,
  tauxTva,
  lectureSeule = false,
  onFerme,
}: {
  /** Identifiant de l'article ; null pour une nouvelle monture. */
  article: string | null;
  magasin: string;
  monnaie: { devise: string; decimales: number };
  tauxTva: string[];
  lectureSeule?: boolean;
  onFerme: () => void;
}) {
  const suggestions = useQuery({ queryKey: ["fiche", "suggestions"], queryFn: lireSuggestions });
  const [monture, setMonture] = useState<Monture>(MONTURE_VIDE);
  const [onglet, setOnglet] = useState(0);
  const { fiche, entete, fournisseur, setFournisseur, prix, setPrix, enregistrement, peutValider, texte, case_ } =
    useFicheArticle({
      article,
      magasin,
      tauxTva,
      famille: "monture",
      lectureSeule,
      complement: () => ({ monture }),
      onFerme,
    });

  // Fiche existante : les caractéristiques de la monture une fois chargée.
  const charge = fiche.data;
  useEffect(() => {
    if (charge) setMonture({ ...MONTURE_VIDE, ...charge.monture });
  }, [charge]);

  const changerMonture = <K extends keyof Monture>(cle: K, valeur: Monture[K]) =>
    setMonture((m) => ({ ...m, [cle]: valeur }));

  const liste = (
    cle: keyof Monture,
    label: string,
    options: readonly { valeur: string; libelle: string }[],
    largeur = 200,
  ) => (
    <TextField
      select
      size="small"
      label={label}
      value={monture[cle] ?? ""}
      onChange={(e) => changerMonture(cle, e.target.value as never)}
      slotProps={{ select: { readOnly: lectureSeule, displayEmpty: true }, inputLabel: { shrink: true } }}
      sx={{ width: largeur }}
    >
      {options.map((o) => (
        <MenuItem key={o.valeur} value={o.valeur}>
          {o.libelle}
        </MenuItem>
      ))}
    </TextField>
  );
  const propose = (cle: keyof Suggestions, label: string, largeur = 200) => (
    <Autocomplete
      freeSolo
      size="small"
      options={suggestions.data?.[cle] ?? []}
      inputValue={(monture[cle] as string) ?? ""}
      onInputChange={(_, texte) => changerMonture(cle, texte)}
      readOnly={lectureSeule}
      renderInput={(params) => <TextField {...params} label={label} />}
      sx={{ width: largeur }}
    />
  );
  const mesure = (cle: "calibre" | "pont" | "branche", label: string) => (
    <TextField
      size="small"
      label={label}
      value={monture[cle] ?? ""}
      onChange={(e) => {
        const n = e.target.value.replace(/\D/g, "");
        changerMonture(cle, n ? Number(n) : null);
      }}
      slotProps={{ htmlInput: { inputMode: "numeric", readOnly: lectureSeule } }}
      sx={{ width: 95 }}
    />
  );
  const aVenir = (titre: string) => (
    <Typography color="text.secondary" sx={{ py: 3 }}>
      {titre} : à venir.
    </Typography>
  );
  const chargee = fiche.data;

  return (
    <Dialog open onClose={onFerme} maxWidth="lg" fullWidth>
      <DialogTitle sx={{ textAlign: "center", fontWeight: 700, color: BORDEAUX }}>Fiche Monture</DialogTitle>
      <DialogContent>
        {fiche.isError && <Alert severity="error">{fiche.error.message}</Alert>}
        {article && fiche.isPending ? (
          <Typography color="text.secondary">Chargement…</Typography>
        ) : (
          <Stack spacing={2} sx={{ pt: 1 }}>
            <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap", alignItems: "center" }}>
              {texte("code_barres", "Code Monture", 220, {
                placeholder: "attribué à la validation",
                sx: { width: 220, bgcolor: "#fff59d" },
              })}
              <Box sx={{ width: 420 }}>
                <ChoixFournisseur valeur={fournisseur} onChange={setFournisseur} libelle="Fournisseur" minWidth={300} />
              </Box>
              {liste("categorie", "Famille", CATEGORIES)}
            </Stack>
            <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap" }}>
              {liste("matiere", "Matière", [{ valeur: "", libelle: "—" }, ...MATIERES])}
              {liste("type", "Type", TYPES_MONTURE)}
              {propose("forme", "Forme")}
              {liste("tranche_age", "Tranche Age", TRANCHES_AGE, 150)}
              {liste("genre", "Genre", GENRES, 130)}
            </Stack>
            <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap" }}>
              {propose("marque", "Marque")}
              {propose("modele", "Modèle")}
              {propose("couleur", "Couleur Monture")}
              {propose("couleur_verres", "Couleur Verres")}
            </Stack>
            <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap" }}>
              {texte("reference", "Référence", 220, { placeholder: "attribuée si vide" })}
              {mesure("calibre", "Taille")}
              {mesure("pont", "Pont")}
              {mesure("branche", "Branche")}
              {texte("reference_fournisseur", "Code chez Fournisseur")}
              {texte("libelle", "Désignation", 300, { placeholder: "marque, modèle, couleur, taille" })}
            </Stack>

            <Tabs value={onglet} onChange={(_, o: number) => setOnglet(o)} variant="scrollable">
              <Tab label="Détail prix" />
              <Tab label="Détail Prix Achat Etranger" />
              <Tab label="Code A Barre" />
              <Tab label="Observation" />
              <Tab label="Stock" />
              <Tab label="Garantie" />
              <Tab label="Article lié" />
              <Tab label="Article SAV" />
            </Tabs>

            {onglet === 0 && (
              <OngletDetailPrix
                cases={
                  <>
                    {case_("est_actif", "Actif")}
                    {case_("stockable", "Stockable")}
                    {case_("suivi_numero_serie", "Numéro Série")}
                    {case_("promotion", "Promotion")}
                    {case_("etui_special", "Etui Spécial")}
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
            {onglet === 1 && aVenir("Détail prix achat étranger (devise, frais d'approche)")}
            {onglet === 2 && (
              <EtiquetteCodeBarres
                code={chargee?.code_barres ?? ""}
                titre={[monture.marque, monture.modele, monture.couleur].filter(Boolean).join(" ")}
                reference={chargee?.reference ?? ""}
                prix={chargee?.prix ? formaterTexte(chargee.prix.prix_vente_ttc, monnaie) : ""}
              />
            )}
            {onglet === 3 && texte("observation", "Observation", 700, { multiline: true, minRows: 4 })}
            {onglet === 4 && <OngletStock chargee={chargee} />}
            {onglet === 5 && aVenir("Garantie")}
            {onglet === 6 && aVenir("Article lié")}
            {onglet === 7 && aVenir("Article SAV")}
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
