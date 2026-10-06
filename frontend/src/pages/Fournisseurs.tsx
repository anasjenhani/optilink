import AddCircle from "@mui/icons-material/AddCircle";
import Edit from "@mui/icons-material/Edit";
import Info from "@mui/icons-material/Info";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import FormControlLabel from "@mui/material/FormControlLabel";
import MenuItem from "@mui/material/MenuItem";
import Radio from "@mui/material/Radio";
import RadioGroup from "@mui/material/RadioGroup";
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
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  chercherFournisseurs,
  creerFournisseur,
  FORMES_JURIDIQUES,
  modifierFournisseur,
  type FiltresFournisseurs,
  type Fournisseur,
  type SaisieFournisseur,
} from "../api/achats";
import { ChampVille } from "./ChampVille";
import { BoutonImport } from "./Imports";
import { BANDEAU, BORDEAUX, BOUTON, useApaise } from "./RechercheClients";

const COLONNES: { cle: keyof FiltresFournisseurs; titre: string; largeur?: number }[] = [
  { cle: "code", titre: "Code Fournisseur", largeur: 150 },
  { cle: "nom", titre: "Raison Sociale" },
  { cle: "adresse", titre: "Adresse" },
  { cle: "ville", titre: "Ville", largeur: 140 },
  { cle: "telephone", titre: "Téléphone", largeur: 150 },
];

const VIDE: SaisieFournisseur = {
  nom: "",
  notre_code: "",
  responsable: "",
  fournisseur_verres: false,
  matricule_fiscal: "",
  registre_commerce: "",
  code_douane: "",
  forme_juridique: "",
  capital_social: null,
  timbre_fiscal: true,
  assujetti: true,
  fodec: false,
  regime_tva: "assujetti",
  numero_exoneration: "",
  exoneration_du: null,
  exoneration_au: null,
  adresse: "",
  code_postal: "",
  ville: "",
  telephone: "",
  telephone_2: "",
  fax: "",
  email: "",
  site_web: "",
  banque: "",
  rib: "",
  observation: "",
  est_actif: true,
};

/** Fiche fournisseur en onglets, comme dans l'ancien logiciel. */
export function FicheFournisseur({
  fournisseur,
  lectureSeule = false,
  onFerme,
  onEnregistre,
}: {
  fournisseur: Fournisseur | null;
  lectureSeule?: boolean;
  onFerme: () => void;
  onEnregistre?: (fournisseur: Fournisseur) => void;
}) {
  const queryClient = useQueryClient();
  const [fiche, setFiche] = useState<SaisieFournisseur>(() => {
    if (!fournisseur) return VIDE;
    const { id: _id, code: _code, pays: _pays, ...reste } = fournisseur;
    return reste;
  });
  const [onglet, setOnglet] = useState(0);
  const changer = <K extends keyof SaisieFournisseur>(cle: K, valeur: SaisieFournisseur[K]) =>
    setFiche((f) => ({ ...f, [cle]: valeur }));

  const enregistrement = useMutation({
    mutationFn: () => {
      const corps = { ...fiche, capital_social: fiche.capital_social || null };
      return fournisseur ? modifierFournisseur(fournisseur.id, corps) : creerFournisseur(corps);
    },
    onSuccess: (enregistre) => {
      void queryClient.invalidateQueries({ queryKey: ["fournisseurs"] });
      onEnregistre?.(enregistre);
      onFerme();
    },
  });

  const texte = (cle: keyof SaisieFournisseur, label: string, props: { largeur?: number; lignes?: number } = {}) => (
    <TextField
      size="small"
      label={label}
      value={(fiche[cle] as string | null) ?? ""}
      onChange={(e) => changer(cle, e.target.value as never)}
      multiline={Boolean(props.lignes)}
      minRows={props.lignes}
      slotProps={{ htmlInput: { readOnly: lectureSeule } }}
      sx={{ width: props.largeur ?? 260 }}
    />
  );
  const case_ = (cle: keyof SaisieFournisseur, label: string) => (
    <FormControlLabel
      label={label}
      control={
        <Checkbox
          size="small"
          checked={Boolean(fiche[cle])}
          disabled={lectureSeule}
          onChange={(e) => changer(cle, e.target.checked as never)}
        />
      }
    />
  );

  return (
    <Dialog open onClose={onFerme} maxWidth="lg" fullWidth>
      <DialogTitle sx={{ textAlign: "center", fontWeight: 700 }}>Fournisseur</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap", alignItems: "center" }}>
            <TextField
              size="small"
              label="Code Fournisseur"
              value={fournisseur?.code ?? "Attribué à l'enregistrement"}
              slotProps={{ htmlInput: { readOnly: true } }}
              sx={{ width: 200, bgcolor: "#fffde7" }}
            />
            {texte("notre_code", "Notre code chez le fournisseur")}
            {texte("nom", "Raison sociale", { largeur: 360 })}
            {texte("responsable", "Responsable")}
            {case_("fournisseur_verres", "Fournisseur Verre")}
            {case_("est_actif", "Actif")}
          </Stack>
          <Tabs value={onglet} onChange={(_, o: number) => setOnglet(o)} variant="scrollable">
            <Tab label="Information Financière" />
            <Tab label="Adresse" />
            <Tab label="Identité Bancaire" />
            <Tab label="Observation" />
          </Tabs>
          {onglet === 0 && (
            <Stack spacing={2}>
              <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap" }}>
                {texte("matricule_fiscal", "Matricule fiscal")}
                {texte("registre_commerce", "Registre de commerce")}
                {texte("code_douane", "Code douane")}
              </Stack>
              <Stack direction="row" spacing={3} useFlexGap sx={{ flexWrap: "wrap", alignItems: "flex-start" }}>
                <Stack>
                  {case_("timbre_fiscal", "Timbre fiscal")}
                  {case_("assujetti", "Assujetti")}
                  {case_("fodec", "FODEC (1 %)")}
                </Stack>
                <RadioGroup
                  value={fiche.regime_tva}
                  onChange={(e) => changer("regime_tva", e.target.value as SaisieFournisseur["regime_tva"])}
                >
                  <FormControlLabel
                    value="assujetti"
                    control={<Radio size="small" disabled={lectureSeule} />}
                    label="Payer TVA"
                  />
                  <FormControlLabel
                    value="export"
                    control={<Radio size="small" disabled={lectureSeule} />}
                    label="Export"
                  />
                  <FormControlLabel
                    value="exoneration"
                    control={<Radio size="small" disabled={lectureSeule} />}
                    label="Exonération"
                  />
                </RadioGroup>
                {fiche.regime_tva === "exoneration" && (
                  <Stack spacing={1.5}>
                    {texte("numero_exoneration", "Numéro d'exonération")}
                    <TextField
                      size="small"
                      type="date"
                      label="Début d'exonération"
                      value={fiche.exoneration_du ?? ""}
                      onChange={(e) => changer("exoneration_du", e.target.value || null)}
                      slotProps={{ inputLabel: { shrink: true }, htmlInput: { readOnly: lectureSeule } }}
                    />
                    <TextField
                      size="small"
                      type="date"
                      label="Fin d'exonération"
                      value={fiche.exoneration_au ?? ""}
                      onChange={(e) => changer("exoneration_au", e.target.value || null)}
                      slotProps={{ inputLabel: { shrink: true }, htmlInput: { readOnly: lectureSeule } }}
                    />
                  </Stack>
                )}
                <Stack spacing={1.5}>
                  <TextField
                    select
                    size="small"
                    label="Forme juridique"
                    value={fiche.forme_juridique}
                    onChange={(e) => changer("forme_juridique", e.target.value as SaisieFournisseur["forme_juridique"])}
                    disabled={lectureSeule}
                    sx={{ width: 220 }}
                  >
                    <MenuItem value="">—</MenuItem>
                    {FORMES_JURIDIQUES.map((f) => (
                      <MenuItem key={f.valeur} value={f.valeur}>
                        {f.libelle}
                      </MenuItem>
                    ))}
                  </TextField>
                  {texte("capital_social", "Capital social", { largeur: 220 })}
                </Stack>
              </Stack>
            </Stack>
          )}
          {onglet === 1 && (
            <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap" }}>
              {texte("adresse", "Adresse", { largeur: 540, lignes: 2 })}
              {texte("code_postal", "Code postal", { largeur: 140 })}
              <ChampVille
                valeur={fiche.ville ?? ""}
                changer={(ville) => changer("ville", ville)}
                lectureSeule={lectureSeule}
              />
              {texte("telephone", "Téléphone")}
              {texte("telephone_2", "Téléphone 2")}
              {texte("fax", "Fax")}
              {texte("email", "E-mail", { largeur: 320 })}
              {texte("site_web", "Site web", { largeur: 320 })}
            </Stack>
          )}
          {onglet === 2 && (
            <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap" }}>
              {texte("banque", "Banque")}
              {texte("rib", "RIB", { largeur: 320 })}
            </Stack>
          )}
          {onglet === 3 && texte("observation", "Observation", { largeur: 700, lignes: 4 })}
          {enregistrement.isError && <Alert severity="error">{enregistrement.error.message}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onFerme}>{lectureSeule ? "Fermer" : "Annuler"}</Button>
        {!lectureSeule && (
          <Button
            variant="contained"
            disabled={!fiche.nom.trim() || enregistrement.isPending}
            onClick={() => enregistrement.mutate()}
          >
            Valider
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}

/**
 * « Recherche d'un fournisseur » : un filtre sous chaque colonne. Dans un bon de réception,
 * un clic choisit le fournisseur ; sinon, les boutons ouvrent sa fiche.
 */
export function Fournisseurs({
  onChoisi,
  droits,
}: {
  onChoisi?: (fournisseur: Fournisseur) => void;
  droits: { creer: boolean; modifier: boolean };
}) {
  const [filtres, setFiltres] = useState<Record<string, string>>({});
  const [page, setPage] = useState(1);
  const [selection, setSelection] = useState<Fournisseur | null>(null);
  const [fiche, setFiche] = useState<{ fournisseur: Fournisseur | null; lecture: boolean } | null>(null);
  const recherche = useApaise(filtres);
  const fournisseurs = useQuery({
    queryKey: ["fournisseurs", "tableau", recherche, page],
    queryFn: () => chercherFournisseurs(recherche, page),
    placeholderData: keepPreviousData,
  });
  const lignes = fournisseurs.data?.results ?? [];
  const pages = Math.max(1, Math.ceil((fournisseurs.data?.count ?? 0) / 50));

  return (
    <Stack spacing={1}>
      <Box sx={{ px: 3, py: 1, borderRadius: 1, background: BANDEAU }}>
        <Typography variant="h5" component="h3" sx={{ color: "common.white", fontWeight: 500 }}>
          Recherche d'un fournisseur
        </Typography>
      </Box>
      {fournisseurs.isError && <Alert severity="error">{fournisseurs.error.message}</Alert>}
      <TableContainer sx={{ maxHeight: 480, border: 1, borderColor: "grey.400", borderRadius: 1 }}>
        <Table stickyHeader size="small" aria-label="Recherche fournisseurs">
          <TableHead>
            <TableRow>
              {COLONNES.map((c) => (
                <TableCell key={c.cle} sx={{ width: c.largeur, color: BORDEAUX, fontWeight: 700, bgcolor: "grey.100" }}>
                  {c.titre}
                </TableCell>
              ))}
            </TableRow>
            <TableRow>
              {COLONNES.map((c) => (
                <TableCell key={c.cle} sx={{ top: 37, p: 0.5, bgcolor: "grey.300" }}>
                  <TextField
                    size="small"
                    fullWidth
                    autoFocus={c.cle === "nom"}
                    value={filtres[c.cle] ?? ""}
                    onChange={(e) => {
                      setFiltres((f) => ({ ...f, [c.cle]: e.target.value }));
                      setPage(1);
                    }}
                    slotProps={{
                      htmlInput: { "aria-label": `Filtrer ${c.titre}` },
                      input: { sx: { bgcolor: "common.white", height: 28, fontSize: 14 } },
                    }}
                  />
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {lignes.map((f) => (
              <TableRow
                key={f.id}
                hover
                selected={selection?.id === f.id}
                onClick={() => (onChoisi ? onChoisi(f) : setSelection(f))}
                onDoubleClick={() => !onChoisi && setFiche({ fournisseur: f, lecture: !droits.modifier })}
                sx={{ cursor: "pointer", "& td": { borderColor: "#d9a3a3", fontWeight: 600 } }}
              >
                <TableCell>{f.code}</TableCell>
                <TableCell>{f.nom}</TableCell>
                <TableCell>{f.adresse}</TableCell>
                <TableCell>{f.ville}</TableCell>
                <TableCell>{f.telephone}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {fournisseurs.data?.count === 0 && (
          <Box sx={{ p: 2 }}>
            <Typography color="text.secondary">Aucun fournisseur ne correspond.</Typography>
          </Box>
        )}
      </TableContainer>
      <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: "center", flexWrap: "wrap" }}>
        {droits.creer && (
          <Button
            startIcon={<AddCircle sx={{ color: "success.main" }} />}
            sx={BOUTON}
            onClick={() => setFiche({ fournisseur: null, lecture: false })}
          >
            Ajouter
          </Button>
        )}
        {!onChoisi && droits.modifier && (
          <Button
            startIcon={<Edit sx={{ color: "info.main" }} />}
            sx={BOUTON}
            disabled={!selection}
            onClick={() => setFiche({ fournisseur: selection, lecture: false })}
          >
            Modifier
          </Button>
        )}
        {!onChoisi && (
          <Button
            startIcon={<Info sx={{ color: "secondary.main" }} />}
            sx={BOUTON}
            disabled={!selection}
            onClick={() => setFiche({ fournisseur: selection, lecture: true })}
          >
            Consulter
          </Button>
        )}
        {!onChoisi && droits.creer && droits.modifier && <BoutonImport type="fournisseurs" />}
        <Typography variant="body2" color="text.secondary" sx={{ flex: 1, textAlign: "right" }}>
          {fournisseurs.data ? `${fournisseurs.data.count} fournisseur${fournisseurs.data.count > 1 ? "s" : ""}` : ""}
        </Typography>
        {pages > 1 && (
          <>
            <Button size="small" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Précédente
            </Button>
            <Typography variant="body2">
              Page {page} / {pages}
            </Typography>
            <Button size="small" disabled={page >= pages} onClick={() => setPage(page + 1)}>
              Suivante
            </Button>
          </>
        )}
      </Stack>
      {fiche && (
        <FicheFournisseur
          key={fiche.fournisseur?.id ?? "nouveau"}
          fournisseur={fiche.fournisseur}
          lectureSeule={fiche.lecture}
          onFerme={() => setFiche(null)}
          onEnregistre={(f) => (onChoisi ? onChoisi(f) : setSelection(f))}
        />
      )}
    </Stack>
  );
}
