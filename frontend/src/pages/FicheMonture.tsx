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
import { useEffect, useState } from "react";

import type { Fournisseur } from "../api/achats";
import {
  calculerPrix,
  CATEGORIES,
  enregistrerFiche,
  type FicheMonture as Monture,
  GENRES,
  lireFiche,
  lireMouvements,
  lireSuggestions,
  MATIERES,
  type SaisieFiche,
  type Suggestions,
  TRANCHES_AGE,
  TYPES_MONTURE,
  venteTTCDepuisHT,
  venteTTCDepuisMarge,
} from "../api/fiches";
import { formaterTexte } from "../api/monnaie";
import { ChoixFournisseur } from "./BonReception";
import { EtiquetteCodeBarres } from "./EtiquetteCodeBarres";
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

type Entete = {
  reference: string;
  libelle: string;
  code_barres: string;
  reference_fournisseur: string;
  observation: string;
  est_actif: boolean;
  stockable: boolean;
  suivi_numero_serie: boolean;
  promotion: boolean;
  etui_special: boolean;
  fodec: boolean;
};

const ENTETE_VIDE: Entete = {
  reference: "",
  libelle: "",
  code_barres: "",
  reference_fournisseur: "",
  observation: "",
  est_actif: true,
  stockable: true,
  suivi_numero_serie: false,
  promotion: false,
  etui_special: false,
  fodec: false,
};

type SaisiePrix = { achatHT: string; remise: string; tva: string; venteTTC: string };

const nombre = (texte: string) => {
  const n = Number(texte.replace(",", ".").trim());
  return texte.trim() === "" || Number.isNaN(n) ? null : n;
};
const arrondi = (n: number, decimales: number) => n.toFixed(decimales);

/** Champ calculé qu'on peut aussi saisir (marge, prix HT) : la saisie s'applique en sortant du champ. */
function ChampCalcule({
  label,
  valeur,
  decimales,
  suffixe,
  onSaisi,
  lectureSeule,
}: {
  label: string;
  valeur: number | null;
  decimales: number;
  suffixe?: string;
  onSaisi?: (n: number) => void;
  lectureSeule?: boolean;
}) {
  const [texte, setTexte] = useState<string | null>(null);
  const affiche = valeur === null ? "" : arrondi(valeur, decimales);
  const appliquer = () => {
    const n = texte === null ? null : nombre(texte);
    if (n !== null) onSaisi?.(n);
    setTexte(null);
  };
  return (
    <TextField
      size="small"
      label={label}
      value={texte ?? affiche}
      onChange={(e) => setTexte(e.target.value)}
      onBlur={appliquer}
      onKeyDown={(e) => e.key === "Enter" && appliquer()}
      slotProps={{
        htmlInput: { readOnly: lectureSeule || !onSaisi, inputMode: "decimal" },
        input: suffixe ? { endAdornment: suffixe } : undefined,
      }}
      sx={{ width: 190, ...(lectureSeule || !onSaisi ? { bgcolor: "grey.100" } : {}) }}
    />
  );
}

function Mouvements({ article, onFerme }: { article: string; onFerme: () => void }) {
  const mouvements = useQuery({ queryKey: ["fiche", article, "mouvements"], queryFn: () => lireMouvements(article) });
  return (
    <Dialog open onClose={onFerme} maxWidth="md" fullWidth>
      <DialogTitle>Détail des mouvements</DialogTitle>
      <DialogContent>
        {mouvements.isError && <Alert severity="error">{mouvements.error.message}</Alert>}
        {mouvements.data?.length === 0 && <Typography color="text.secondary">Aucun mouvement.</Typography>}
        {Boolean(mouvements.data?.length) && (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Date</TableCell>
                <TableCell>Magasin</TableCell>
                <TableCell>Mouvement</TableCell>
                <TableCell>Pièce</TableCell>
                <TableCell>Par</TableCell>
                <TableCell align="right">Quantité</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {mouvements.data?.map((m, i) => (
                <TableRow key={i}>
                  <TableCell>{new Date(m.horodatage).toLocaleString("fr-FR")}</TableCell>
                  <TableCell>{m.magasin}</TableCell>
                  <TableCell>{m.type}</TableCell>
                  <TableCell>{m.reference}</TableCell>
                  <TableCell>{m.utilisateur}</TableCell>
                  <TableCell align="right">{m.quantite > 0 ? `+${m.quantite}` : m.quantite}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onFerme}>Fermer</Button>
      </DialogActions>
    </Dialog>
  );
}

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
  const queryClient = useQueryClient();
  const fiche = useQuery({
    queryKey: ["fiche", article, magasin],
    queryFn: () => lireFiche(article as string, magasin),
    enabled: Boolean(article),
  });
  const suggestions = useQuery({ queryKey: ["fiche", "suggestions"], queryFn: lireSuggestions });
  const tvaParDefaut = tauxTva.length ? String(Math.max(...tauxTva.map(Number))) : "19";
  const [entete, setEntete] = useState<Entete>(ENTETE_VIDE);
  const [monture, setMonture] = useState<Monture>(MONTURE_VIDE);
  const [fournisseur, setFournisseur] = useState<Fournisseur | null>(null);
  const [prix, setPrix] = useState<SaisiePrix>({ achatHT: "", remise: "0", tva: tvaParDefaut, venteTTC: "" });
  const [onglet, setOnglet] = useState(0);
  const [voirMouvements, setVoirMouvements] = useState(false);

  // Fiche existante : on remplit le formulaire une fois chargée.
  const charge = fiche.data;
  useEffect(() => {
    if (!charge) return;
    const { monture: m, prix: p, dernier_achat: dernier } = charge;
    setEntete({
      reference: charge.reference,
      libelle: charge.libelle,
      code_barres: charge.code_barres,
      reference_fournisseur: charge.reference_fournisseur,
      observation: charge.observation,
      est_actif: charge.est_actif,
      stockable: charge.stockable,
      suivi_numero_serie: charge.suivi_numero_serie,
      promotion: charge.promotion,
      etui_special: charge.etui_special,
      fodec: charge.fodec,
    });
    setMonture({ ...MONTURE_VIDE, ...m });
    setFournisseur({
      id: charge.fournisseur,
      code: charge.fournisseur_code,
      nom: charge.fournisseur_nom,
    } as Fournisseur);
    setPrix({
      achatHT: p?.prix_achat_ht ?? dernier?.prix_achat_ht ?? "",
      remise: p && p.prix_achat_ht !== null ? p.taux_remise_achat : (dernier?.taux_remise ?? "0"),
      tva: p ? String(Number(p.taux_tva)) : tvaParDefaut,
      venteTTC: p?.prix_vente_ttc ?? "",
    });
  }, [charge, tvaParDefaut]);

  const calcul = calculerPrix({
    achatHT: nombre(prix.achatHT) ?? 0,
    remise: nombre(prix.remise) ?? 0,
    tva: nombre(prix.tva) ?? 0,
    venteTTC: nombre(prix.venteTTC) ?? 0,
    fodec: entete.fodec,
  });
  const d = monnaie.decimales;

  const enregistrement = useMutation({
    mutationFn: () => {
      const saisie: SaisieFiche = {
        ...entete,
        famille: "monture",
        fournisseur: fournisseur?.id,
        monture,
      };
      if (prix.venteTTC.trim()) {
        saisie.nouveau_prix = {
          prix_achat_ht: nombre(prix.achatHT) === null ? null : prix.achatHT.replace(",", "."),
          taux_remise_achat: String(nombre(prix.remise) ?? 0),
          taux_tva: prix.tva,
          prix_vente_ttc: prix.venteTTC.replace(",", "."),
        };
      }
      return enregistrerFiche(article, magasin, saisie);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["catalogue"] });
      void queryClient.invalidateQueries({ queryKey: ["fiche"] });
      onFerme();
    },
  });
  const peutValider = !lectureSeule && Boolean(fournisseur) && !enregistrement.isPending;

  // F4 valide, comme dans l'ancien logiciel.
  useEffect(() => {
    const touche = (e: KeyboardEvent) => {
      if (e.key === "F4" && peutValider) {
        e.preventDefault();
        enregistrement.mutate();
      }
    };
    window.addEventListener("keydown", touche);
    return () => window.removeEventListener("keydown", touche);
  }, [peutValider, enregistrement]);

  const changerMonture = <K extends keyof Monture>(cle: K, valeur: Monture[K]) =>
    setMonture((m) => ({ ...m, [cle]: valeur }));
  const changerEntete = <K extends keyof Entete>(cle: K, valeur: Entete[K]) =>
    setEntete((e) => ({ ...e, [cle]: valeur }));

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
  const texte = (cle: keyof Entete, label: string, largeur = 200, props: object = {}) => (
    <TextField
      size="small"
      label={label}
      value={entete[cle] as string}
      onChange={(e) => changerEntete(cle, e.target.value as never)}
      slotProps={{ htmlInput: { readOnly: lectureSeule } }}
      sx={{ width: largeur }}
      {...props}
    />
  );
  const case_ = (cle: keyof Entete, label: string) => (
    <FormControlLabel
      label={label}
      control={
        <Checkbox
          size="small"
          checked={Boolean(entete[cle])}
          disabled={lectureSeule}
          onChange={(e) => changerEntete(cle, e.target.checked as never)}
        />
      }
    />
  );
  const champPrix = (cle: keyof SaisiePrix, label: string, suffixe?: string) => (
    <TextField
      size="small"
      label={label}
      value={prix[cle]}
      onChange={(e) => setPrix((p) => ({ ...p, [cle]: e.target.value }))}
      slotProps={{
        htmlInput: { inputMode: "decimal", readOnly: lectureSeule },
        input: suffixe ? { endAdornment: suffixe } : undefined,
      }}
      sx={{ width: 190 }}
    />
  );
  const aVenir = (titre: string) => (
    <Typography color="text.secondary" sx={{ py: 3 }}>
      {titre} : à venir.
    </Typography>
  );
  const chargee = fiche.data;
  const dernier = chargee?.dernier_achat;

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
              <Stack direction="row" spacing={4} useFlexGap sx={{ flexWrap: "wrap", alignItems: "flex-start" }}>
                <Stack>
                  {case_("est_actif", "Actif")}
                  {case_("stockable", "Stockable")}
                  {case_("suivi_numero_serie", "Numéro Série")}
                  {case_("promotion", "Promotion")}
                  {case_("etui_special", "Etui Spécial")}
                  {case_("fodec", "Fodec")}
                </Stack>
                <Stack spacing={2}>
                  {champPrix("achatHT", "Prix Achat HT")}
                  <ChampCalcule
                    label="Dernier P.Achat Net HT"
                    valeur={dernier ? Number(dernier.net_ht) : null}
                    decimales={d}
                    lectureSeule
                  />
                  <TextField
                    select
                    size="small"
                    label="TVA"
                    value={prix.tva}
                    onChange={(e) => setPrix((p) => ({ ...p, tva: e.target.value }))}
                    slotProps={{ select: { readOnly: lectureSeule } }}
                    sx={{ width: 190 }}
                  >
                    {(tauxTva.length ? tauxTva : [prix.tva]).map((t) => (
                      <MenuItem key={t} value={String(Number(t))}>
                        {Number(t)} %
                      </MenuItem>
                    ))}
                  </TextField>
                  <ChampCalcule
                    label="Prix Achat Net TTC"
                    valeur={nombre(prix.achatHT) === null ? null : calcul.achatNetTTC}
                    decimales={d}
                    lectureSeule
                  />
                </Stack>
                <Stack spacing={2}>
                  {champPrix("remise", "Dernier Tx.Remise", "%")}
                  <ChampCalcule
                    label="Marge"
                    valeur={nombre(prix.venteTTC) === null ? null : calcul.marge}
                    decimales={2}
                    suffixe="%"
                    lectureSeule={lectureSeule || !nombre(prix.achatHT)}
                    onSaisi={(marge) =>
                      setPrix((p) => ({
                        ...p,
                        venteTTC: arrondi(venteTTCDepuisMarge(nombre(p.achatHT) ?? 0, marge, nombre(p.tva) ?? 0), d),
                      }))
                    }
                  />
                  <ChampCalcule
                    label="Prix Vente HT"
                    valeur={nombre(prix.venteTTC) === null ? null : calcul.venteHT}
                    decimales={d}
                    lectureSeule={lectureSeule}
                    onSaisi={(ht) =>
                      setPrix((p) => ({ ...p, venteTTC: arrondi(venteTTCDepuisHT(ht, nombre(p.tva) ?? 0), d) }))
                    }
                  />
                  {champPrix("venteTTC", "Prix Vente TTC", monnaie.devise)}
                </Stack>
                {dernier && (
                  <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 220 }}>
                    Dernier achat : BL {dernier.numero_bl} du {new Date(dernier.date_bl).toLocaleDateString("fr-FR")},{" "}
                    {dernier.prix_achat_ht} HT, remise {Number(dernier.taux_remise)} %.
                  </Typography>
                )}
              </Stack>
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
            {onglet === 4 &&
              (chargee ? (
                <Table size="small" sx={{ maxWidth: 400 }}>
                  <TableHead>
                    <TableRow>
                      <TableCell>Magasin</TableCell>
                      <TableCell align="right">Stock</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {chargee.stocks.map((s) => (
                      <TableRow key={s.magasin}>
                        <TableCell>{s.magasin}</TableCell>
                        <TableCell align="right">{s.stock}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <Typography color="text.secondary">Le stock vient avec les bons de réception.</Typography>
              ))}
            {onglet === 5 && aVenir("Garantie")}
            {onglet === 6 && aVenir("Article lié")}
            {onglet === 7 && aVenir("Article SAV")}
            {enregistrement.isError && <Alert severity="error">{enregistrement.error.message}</Alert>}
          </Stack>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3 }}>
        {chargee && (
          <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
            Créé par : {chargee.cree_par ?? "—"} · Le : {new Date(chargee.cree_le).toLocaleDateString("fr-FR")}
          </Typography>
        )}
        {article && (
          <Button onClick={() => setVoirMouvements(true)} sx={{ mr: "auto" }}>
            Détail Mouvement
          </Button>
        )}
        <Button onClick={onFerme}>{lectureSeule ? "Fermer" : "Annuler"}</Button>
        {!lectureSeule && (
          <Button variant="contained" disabled={!peutValider} onClick={() => enregistrement.mutate()}>
            Valider [F4]
          </Button>
        )}
      </DialogActions>
      {voirMouvements && article && <Mouvements article={article} onFerme={() => setVoirMouvements(false)} />}
    </Dialog>
  );
}
