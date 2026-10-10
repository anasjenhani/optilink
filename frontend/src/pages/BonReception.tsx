import Delete from "@mui/icons-material/Delete";
import Download from "@mui/icons-material/Download";
import Search from "@mui/icons-material/Search";
import Alert from "@mui/material/Alert";
import Autocomplete from "@mui/material/Autocomplete";
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
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  chercherFournisseurs,
  derniersPrix,
  enregistrerReception,
  listerARecevoir,
  type ArticleResume,
  type Fournisseur,
  type LigneARecevoir,
} from "../api/achats";
import { chercherArticles, type Article, type Famille } from "../api/caisse";
import { listerMagasins } from "../api/magasins";
import { formater, type Monnaie } from "../api/monnaie";
import { Fournisseurs } from "./Fournisseurs";
import { BANDEAU, BORDEAUX, BOUTON } from "./RechercheClients";

/** Onglets du bon : « Article divers » et « Produit » sont la même famille dans OptiLink. */
const ONGLETS: { famille: Famille | null; libelle: string }[] = [
  { famille: "monture", libelle: "Monture" },
  { famille: "lentille", libelle: "Lentille" },
  { famille: "divers", libelle: "Article Divers / Produit" },
  { famille: "verre", libelle: "Verre" },
  { famille: "supplement", libelle: "Suppléments Verres" },
  { famille: null, libelle: "Pièce jointe" },
];

const TAUX_COURANTS = [7, 13, 19];
const TAUX_FODEC = 1;

export type LigneSaisie = {
  cle: number;
  article: ArticleResume;
  ligne_commande: number | null;
  commande: string;
  oeil: "" | "D" | "G";
  designation: string;
  quantite: string;
  prix_achat_ht: string;
  taux_remise: string;
  taux_tva: string;
  non_conforme: boolean;
  motif: string;
  numero_lot: string;
  date_peremption: string;
  dernier_prix: string | null;
};

const nombre = (texte: string) => Number(texte.replace(",", ".")) || 0;
const arrondi = (montant: number, decimales: number) => Math.round(montant * 10 ** decimales) / 10 ** decimales;
const aujourdhui = () => new Date().toISOString().slice(0, 10);

/** Même calcul que le serveur : tout le livré compte, non conformes compris (ils se renvoient
 * par un bon retour, déduit de la facture achat ; ils n'entrent pas en stock). */
export function calculerBon(lignes: LigneSaisie[], tauxRemiseEx: number, fodec: boolean, decimales: number) {
  let totalHt = 0;
  let totalRemise = 0;
  let totalNet = 0;
  const bases = new Map<number, number>();
  for (const l of lignes) {
    const brut = nombre(l.prix_achat_ht) * nombre(l.quantite);
    const remise = (brut * nombre(l.taux_remise)) / 100;
    totalHt += brut;
    totalRemise += remise;
    totalNet += brut - remise;
    const taux = nombre(l.taux_tva);
    bases.set(taux, (bases.get(taux) ?? 0) + brut - remise);
  }
  const coefficient = (1 - tauxRemiseEx / 100) * (1 + (fodec ? TAUX_FODEC : 0) / 100);
  const tva = [...new Set([...TAUX_COURANTS, ...bases.keys()])]
    .sort((a, b) => a - b)
    .map((taux) => ({
      taux,
      base: arrondi((bases.get(taux) ?? 0) * (1 - tauxRemiseEx / 100), decimales),
      montant: arrondi(((bases.get(taux) ?? 0) * coefficient * taux) / 100, decimales),
    }));
  const remiseEx = arrondi((totalNet * tauxRemiseEx) / 100, decimales);
  const netHt = arrondi(totalNet, decimales) - remiseEx;
  const totalFodec = fodec ? arrondi((netHt * TAUX_FODEC) / 100, decimales) : 0;
  const totalTva = tva.reduce((somme, t) => somme + t.montant, 0);
  return {
    totalHt: arrondi(totalHt, decimales),
    totalRemise: arrondi(totalRemise, decimales),
    remiseEx,
    netHt,
    totalFodec,
    tva,
    totalTva,
    totalTtc: netHt + totalFodec + totalTva,
  };
}

const montantLigne = (l: LigneSaisie) => {
  const net = nombre(l.prix_achat_ht) * nombre(l.quantite) * (1 - nombre(l.taux_remise) / 100);
  return { net, ttc: net * (1 + nombre(l.taux_tva) / 100) };
};

/** Fournisseur par son code ou sa raison sociale. */
export function ChoixFournisseur({
  valeur,
  onChange,
  onRechercher,
  libelle = "Code fournisseur / Raison sociale",
  minWidth = 320,
}: {
  valeur: Fournisseur | null;
  onChange: (fournisseur: Fournisseur | null) => void;
  onRechercher?: () => void;
  libelle?: string;
  minWidth?: number;
}) {
  const [saisie, setSaisie] = useState("");
  const recherche = saisie.trim();
  const fournisseurs = useQuery({
    queryKey: ["fournisseurs", "choix", recherche],
    queryFn: () => chercherFournisseurs(/^\d+$/.test(recherche) ? { code: recherche } : { nom: recherche }),
  });
  return (
    <Stack direction="row" spacing={0.5} sx={{ alignItems: "center", flex: 1, minWidth }}>
      <Autocomplete
        size="small"
        options={fournisseurs.data?.results ?? []}
        value={valeur}
        onChange={(_, f) => onChange(f)}
        inputValue={saisie}
        onInputChange={(_, texte) => setSaisie(texte)}
        filterOptions={(options) => options}
        getOptionLabel={(f) => `${f.code} · ${f.nom}`}
        isOptionEqualToValue={(a, b) => a.id === b.id}
        noOptionsText="Aucun fournisseur"
        renderInput={(params) => <TextField {...params} label={libelle} />}
        sx={{ flex: 1, bgcolor: "#fffde7" }}
      />
      {onRechercher && (
        <IconButton aria-label="Rechercher un fournisseur" onClick={onRechercher}>
          <Search />
        </IconButton>
      )}
    </Stack>
  );
}

/** Ajout d'un article du stock (les verres et suppléments viennent du bon de commande). */
export function AjoutArticle({
  magasin,
  famille,
  onAjoute,
  avecStock = false,
  depot = "",
}: {
  magasin: string;
  famille: Famille | "";
  onAjoute: (article: Article) => void;
  /** Affiche le stock du magasin sous chaque article (transfert, bon retour). */
  avecStock?: boolean;
  /** Stock de ce dépôt du magasin (par défaut : son dépôt de vente). */
  depot?: string;
}) {
  const [saisie, setSaisie] = useState("");
  const articles = useQuery({
    queryKey: ["articles", magasin, famille, saisie, "reception", depot],
    queryFn: () => chercherArticles(magasin, saisie, famille, "", false, depot),
    enabled: Boolean(magasin),
  });
  return (
    <Autocomplete
      size="small"
      options={(articles.data ?? []).filter((a) => !a.sur_commande)}
      value={null}
      onChange={(_, article) => {
        if (article) onAjoute(article);
        setSaisie("");
      }}
      inputValue={saisie}
      onInputChange={(_, texte, raison) => raison !== "reset" && setSaisie(texte)}
      filterOptions={(options) => options}
      getOptionLabel={(a) => a.libelle}
      renderOption={({ key, ...props }, a) => (
        <li key={key} {...props}>
          <Stack>
            <Typography variant="body2">{a.libelle}</Typography>
            <Typography variant="caption" color="text.secondary">
              {[a.reference, a.code_barres, a.description, avecStock && a.stock !== null && `stock ${a.stock}`]
                .filter(Boolean)
                .join(" · ")}
            </Typography>
          </Stack>
        </li>
      )}
      noOptionsText="Aucun article"
      renderInput={(params) => <TextField {...params} label="Ajouter un article (code barre, référence, libellé)" />}
      sx={{ maxWidth: 520, bgcolor: "#fffde7" }}
    />
  );
}

/** « Importer Bon Commande » : verres commandés à ce fournisseur et pas encore reçus. */
function ImportCommande({
  magasin,
  fournisseur,
  dejaImportees,
  onImporte,
  onFerme,
}: {
  magasin: string;
  fournisseur: Fournisseur;
  dejaImportees: Set<number>;
  onImporte: (lignes: LigneARecevoir[]) => void;
  onFerme: () => void;
}) {
  const aRecevoir = useQuery({
    queryKey: ["a-recevoir", magasin, fournisseur.id],
    queryFn: () => listerARecevoir(magasin, fournisseur.id),
  });
  const lignes = (aRecevoir.data ?? []).filter((l) => !dejaImportees.has(l.ligne_commande));
  const [choisies, setChoisies] = useState<Set<number>>(new Set());
  const tout = lignes.length > 0 && lignes.every((l) => choisies.has(l.ligne_commande));

  return (
    <Dialog open onClose={onFerme} maxWidth="md" fullWidth>
      <DialogTitle>Bons de commande envoyés à {fournisseur.nom}</DialogTitle>
      <DialogContent>
        {aRecevoir.isError && <Alert severity="error">{aRecevoir.error.message}</Alert>}
        {aRecevoir.data && lignes.length === 0 && (
          <Typography color="text.secondary">Aucun verre commandé à ce fournisseur n'attend de réception.</Typography>
        )}
        {lignes.length > 0 && (
          <Table size="small" aria-label="Lignes de commande à recevoir">
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox">
                  <Checkbox
                    checked={tout}
                    onChange={() => setChoisies(tout ? new Set() : new Set(lignes.map((l) => l.ligne_commande)))}
                    slotProps={{ input: { "aria-label": "Tout choisir" } }}
                  />
                </TableCell>
                <TableCell>Bon commande</TableCell>
                <TableCell>Commande client</TableCell>
                <TableCell>Œil</TableCell>
                <TableCell>Désignation</TableCell>
                <TableCell align="right">Qté</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {lignes.map((l) => (
                <TableRow key={l.ligne_commande}>
                  <TableCell padding="checkbox">
                    <Checkbox
                      checked={choisies.has(l.ligne_commande)}
                      onChange={() =>
                        setChoisies((c) => {
                          const suivantes = new Set(c);
                          if (suivantes.has(l.ligne_commande)) suivantes.delete(l.ligne_commande);
                          else suivantes.add(l.ligne_commande);
                          return suivantes;
                        })
                      }
                      slotProps={{ input: { "aria-label": `Importer ${l.commande} ${l.designation}` } }}
                    />
                  </TableCell>
                  <TableCell>{l.commande}</TableCell>
                  <TableCell>
                    {l.commande_client}
                    {l.client && (
                      <Typography variant="body2" color="text.secondary">
                        {l.client}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>{l.oeil}</TableCell>
                  <TableCell>{l.designation}</TableCell>
                  <TableCell align="right">{l.quantite}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onFerme}>Annuler</Button>
        <Button
          variant="contained"
          disabled={choisies.size === 0}
          onClick={() => {
            onImporte(lignes.filter((l) => choisies.has(l.ligne_commande)));
            onFerme();
          }}
        >
          Importer
        </Button>
      </DialogActions>
    </Dialog>
  );
}

const cellule = { p: 0.5 } as const;
const petit = (largeur: number) => ({ width: largeur, "& input": { py: 0.5, px: 1, fontSize: 14 } });

/**
 * Bon de réception : la marchandise livrée par un fournisseur, avec son bon de livraison (BL).
 * Les verres se reçoivent depuis le bon de commande ; les autres articles entrent en stock.
 */
export function BonReception({ droitsFournisseurs }: { droitsFournisseurs: { creer: boolean; modifier: boolean } }) {
  const queryClient = useQueryClient();
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = magasins.data?.find((m) => m.id === magasinChoisi) ?? magasins.data?.[0];
  const monnaie: Monnaie = magasin
    ? { devise: magasin.pays.devise, decimales: magasin.pays.decimales }
    : { devise: "TND", decimales: 3 };
  const montant = (valeur: number) => formater(Math.round(valeur * 10 ** monnaie.decimales), monnaie);

  const [fournisseur, setFournisseur] = useState<Fournisseur | null>(null);
  const [numeroBl, setNumeroBl] = useState("");
  const [dateBl, setDateBl] = useState(aujourdhui());
  const [observation, setObservation] = useState("");
  const [tauxRemiseEx, setTauxRemiseEx] = useState("0");
  const [remiseTous, setRemiseTous] = useState("0");
  const [lignes, setLignes] = useState<LigneSaisie[]>([]);
  const [selection, setSelection] = useState<number | null>(null);
  const [onglet, setOnglet] = useState(3);
  const [dialogue, setDialogue] = useState<"fournisseur" | "import" | null>(null);
  const [message, setMessage] = useState("");
  const [compteur, setCompteur] = useState(1);

  const famille = ONGLETS[onglet].famille;
  const visibles = lignes.filter((l) => l.article.famille === famille);
  const totaux = calculerBon(lignes, nombre(tauxRemiseEx), Boolean(fournisseur?.fodec), monnaie.decimales);
  const choisie = lignes.find((l) => l.cle === selection);
  const parFamille = (f: Famille | null) => lignes.filter((l) => l.article.famille === f).length;

  const changer = (cle: number, modification: Partial<LigneSaisie>) =>
    setLignes((ls) => ls.map((l) => (l.cle === cle ? { ...l, ...modification } : l)));
  const ajouter = (nouvelles: Omit<LigneSaisie, "cle">[]) => {
    setLignes((ls) => [...ls, ...nouvelles.map((l, i) => ({ ...l, cle: compteur + i }))]);
    setSelection(compteur + nouvelles.length - 1);
    setCompteur((c) => c + nouvelles.length);
  };
  const vider = () => {
    setLignes([]);
    setNumeroBl("");
    setDateBl(aujourdhui());
    setObservation("");
    setTauxRemiseEx("0");
    setSelection(null);
  };

  const ajouterArticle = async (article: Article) => {
    const prix = magasin ? await derniersPrix(magasin.id, [article.id]).catch(() => ({})) : {};
    const connu = (prix as Record<string, { dernier_prix_achat: string | null; taux_tva: string }>)[article.id];
    ajouter([
      {
        article: { ...article },
        ligne_commande: null,
        commande: "",
        oeil: "",
        designation: article.libelle,
        quantite: "1",
        prix_achat_ht: connu?.dernier_prix_achat ?? "",
        taux_remise: remiseTous,
        taux_tva: connu?.taux_tva ?? article.taux_tva,
        non_conforme: false,
        motif: "",
        numero_lot: "",
        date_peremption: "",
        dernier_prix: connu?.dernier_prix_achat ?? null,
      },
    ]);
  };
  const importer = (importees: LigneARecevoir[]) => {
    ajouter(
      importees.map((l) => ({
        article: l.article,
        ligne_commande: l.ligne_commande,
        commande: l.commande,
        oeil: l.oeil,
        designation: l.designation,
        quantite: String(l.quantite),
        prix_achat_ht: l.dernier_prix_achat ?? "",
        taux_remise: remiseTous,
        taux_tva: l.taux_tva,
        non_conforme: false,
        motif: "",
        numero_lot: "",
        date_peremption: "",
        dernier_prix: l.dernier_prix_achat,
      })),
    );
    setOnglet(ONGLETS.findIndex((o) => o.famille === (importees[0]?.article.famille ?? "verre")));
  };

  const manque = (() => {
    if (!fournisseur) return "Choisissez le fournisseur.";
    if (!numeroBl.trim()) return "Saisissez le numéro du BL fournisseur.";
    if (lignes.length === 0) return "Ajoutez au moins un article.";
    if (lignes.some((l) => nombre(l.quantite) < 1)) return "Chaque ligne doit avoir une quantité.";
    if (lignes.some((l) => l.prix_achat_ht.trim() === "")) return "Chaque ligne doit avoir un prix d'achat HT.";
    if (lignes.some((l) => l.non_conforme && !l.motif.trim()))
      return "Le motif est obligatoire pour un article non conforme.";
    return "";
  })();

  const validation = useMutation({
    mutationFn: () =>
      enregistrerReception({
        magasin: magasin!.id,
        fournisseur: fournisseur!.id,
        numero_bl: numeroBl.trim(),
        date_bl: dateBl,
        taux_remise_ex: String(nombre(tauxRemiseEx)),
        observation,
        lignes: lignes.map((l) => ({
          article: l.article.id,
          ligne_commande: l.ligne_commande,
          oeil: l.oeil,
          quantite: nombre(l.quantite),
          prix_achat_ht: String(nombre(l.prix_achat_ht)),
          taux_remise: String(nombre(l.taux_remise)),
          taux_tva: String(nombre(l.taux_tva)),
          non_conforme: l.non_conforme,
          motif: l.motif,
          numero_lot: l.numero_lot,
          date_peremption: l.date_peremption || null,
        })),
      }),
    onSuccess: (bon) => {
      setMessage(
        `Bon de réception ${bon.numero} enregistré (BL ${bon.numero_bl}, ${montant(Number(bon.total_ttc))} TTC).`,
      );
      vider();
      for (const cle of ["bons-reception", "a-recevoir", "commandes-fournisseurs", "commandes", "articles"]) {
        void queryClient.invalidateQueries({ queryKey: [cle] });
      }
    },
  });

  return (
    <Stack spacing={1.5}>
      <Box sx={{ px: 3, py: 1, borderRadius: 1, background: BANDEAU }}>
        <Typography variant="h5" component="h3" sx={{ color: "common.white", fontWeight: 500 }}>
          Bon de Réception
        </Typography>
      </Box>

      <Stack direction="row" spacing={1.5} useFlexGap sx={{ flexWrap: "wrap", alignItems: "center" }}>
        {magasins.data && magasins.data.length > 1 && (
          <TextField
            select
            size="small"
            label="Magasin"
            value={magasin?.id ?? ""}
            onChange={(e) => {
              setMagasin(e.target.value);
              setLignes([]);
            }}
            sx={{ width: 220 }}
          >
            {magasins.data.map((m) => (
              <MenuItem key={m.id} value={m.id}>
                {m.nom}
              </MenuItem>
            ))}
          </TextField>
        )}
        <TextField
          size="small"
          label="Numéro"
          value="Attribué à la validation"
          slotProps={{ htmlInput: { readOnly: true } }}
          sx={{ width: 200 }}
        />
        <TextField
          size="small"
          type="date"
          label="Date saisie"
          value={aujourdhui()}
          slotProps={{ inputLabel: { shrink: true }, htmlInput: { readOnly: true } }}
        />
        <TextField
          size="small"
          label="N° BL fournisseur"
          value={numeroBl}
          onChange={(e) => setNumeroBl(e.target.value)}
          sx={{ width: 180, bgcolor: "#fffde7" }}
        />
        <TextField
          size="small"
          type="date"
          label="Date BL"
          value={dateBl}
          onChange={(e) => setDateBl(e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
        />
      </Stack>
      <Stack direction="row" spacing={1.5} useFlexGap sx={{ flexWrap: "wrap", alignItems: "center" }}>
        <ChoixFournisseur
          valeur={fournisseur}
          onChange={(f) => {
            setFournisseur(f);
            setLignes((ls) => ls.filter((l) => l.ligne_commande === null));
          }}
          onRechercher={() => setDialogue("fournisseur")}
        />
        <Button
          startIcon={<Download sx={{ color: "success.main" }} />}
          sx={BOUTON}
          disabled={!fournisseur || !magasin}
          onClick={() => setDialogue("import")}
        >
          Importer Bon Commande
        </Button>
        <TextField
          size="small"
          label="Observation"
          value={observation}
          onChange={(e) => setObservation(e.target.value)}
          sx={{ flex: 1, minWidth: 220 }}
        />
      </Stack>
      {fournisseur && (fournisseur.fodec || fournisseur.regime_tva !== "assujetti") && (
        <Typography variant="body2" color="text.secondary">
          {[
            fournisseur.fodec && "Fournisseur soumis au FODEC (1 %)",
            fournisseur.regime_tva === "export" && "Fournisseur export",
            fournisseur.regime_tva === "exoneration" && `Exonération n° ${fournisseur.numero_exoneration}`,
          ]
            .filter(Boolean)
            .join(" · ")}
        </Typography>
      )}

      <Tabs value={onglet} onChange={(_, o: number) => setOnglet(o)} variant="scrollable">
        {ONGLETS.map((o) => {
          const nombreLignes = parFamille(o.famille);
          return <Tab key={o.libelle} label={nombreLignes ? `${o.libelle} (${nombreLignes})` : o.libelle} />;
        })}
      </Tabs>

      {famille === null ? (
        <Typography color="text.secondary">Pièce jointe (scan du BL) : à venir.</Typography>
      ) : (
        <>
          {magasin && (famille === "verre" || famille === "supplement") ? (
            <Typography variant="body2" color="text.secondary">
              Les verres sont commandés pour un client : utilisez « Importer Bon Commande ».
            </Typography>
          ) : (
            magasin && <AjoutArticle magasin={magasin.id} famille={famille} onAjoute={(a) => void ajouterArticle(a)} />
          )}
          <TableContainer sx={{ maxHeight: 360, border: 1, borderColor: "grey.400", borderRadius: 1 }}>
            <Table stickyHeader size="small" aria-label={`Lignes ${ONGLETS[onglet].libelle}`}>
              <TableHead>
                <TableRow
                  sx={{
                    "& th": { color: BORDEAUX, fontWeight: 700, bgcolor: "grey.100", p: 0.5, whiteSpace: "nowrap" },
                  }}
                >
                  <TableCell>Bon Commande</TableCell>
                  <TableCell>Code barre</TableCell>
                  {famille === "verre" && <TableCell>Œil</TableCell>}
                  <TableCell>Code</TableCell>
                  <TableCell>Désignation</TableCell>
                  <TableCell>Qté</TableCell>
                  <TableCell>Prix achat HT</TableCell>
                  <TableCell>Taux remise</TableCell>
                  <TableCell>Net HT</TableCell>
                  <TableCell>Taux TVA</TableCell>
                  <TableCell>Montant TTC</TableCell>
                  {famille === "lentille" && <TableCell>N° lot</TableCell>}
                  {famille === "lentille" && <TableCell>Péremption</TableCell>}
                  <TableCell>Non conforme</TableCell>
                  <TableCell>Motif</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {visibles.map((l) => {
                  const { net, ttc } = montantLigne(l);
                  return (
                    <TableRow
                      key={l.cle}
                      hover
                      selected={l.cle === selection}
                      onClick={() => setSelection(l.cle)}
                      sx={{ "& td": cellule, ...(l.non_conforme && { bgcolor: "#fdecea" }) }}
                    >
                      <TableCell sx={{ whiteSpace: "nowrap" }}>{l.commande}</TableCell>
                      <TableCell>{l.article.code_barres}</TableCell>
                      {famille === "verre" && <TableCell>{l.oeil}</TableCell>}
                      <TableCell sx={{ whiteSpace: "nowrap" }}>{l.article.reference}</TableCell>
                      <TableCell sx={{ minWidth: 200 }}>{l.designation}</TableCell>
                      <TableCell>
                        <TextField
                          size="small"
                          value={l.quantite}
                          onChange={(e) => changer(l.cle, { quantite: e.target.value })}
                          slotProps={{ htmlInput: { inputMode: "numeric", "aria-label": `Quantité ${l.designation}` } }}
                          sx={petit(56)}
                        />
                      </TableCell>
                      <TableCell>
                        <TextField
                          size="small"
                          value={l.prix_achat_ht}
                          onChange={(e) => changer(l.cle, { prix_achat_ht: e.target.value })}
                          slotProps={{
                            htmlInput: { inputMode: "decimal", "aria-label": `Prix achat HT ${l.designation}` },
                          }}
                          sx={petit(100)}
                        />
                      </TableCell>
                      <TableCell>
                        <TextField
                          size="small"
                          value={l.taux_remise}
                          onChange={(e) => changer(l.cle, { taux_remise: e.target.value })}
                          slotProps={{
                            htmlInput: { inputMode: "decimal", "aria-label": `Taux remise ${l.designation}` },
                          }}
                          sx={petit(64)}
                        />
                      </TableCell>
                      <TableCell sx={{ whiteSpace: "nowrap" }}>{montant(net)}</TableCell>
                      <TableCell>
                        <TextField
                          size="small"
                          value={l.taux_tva}
                          onChange={(e) => changer(l.cle, { taux_tva: e.target.value })}
                          slotProps={{ htmlInput: { inputMode: "decimal", "aria-label": `Taux TVA ${l.designation}` } }}
                          sx={petit(64)}
                        />
                      </TableCell>
                      <TableCell sx={{ whiteSpace: "nowrap" }}>{montant(ttc)}</TableCell>
                      {famille === "lentille" && (
                        <TableCell>
                          <TextField
                            size="small"
                            value={l.numero_lot}
                            onChange={(e) => changer(l.cle, { numero_lot: e.target.value })}
                            slotProps={{ htmlInput: { "aria-label": `N° lot ${l.designation}` } }}
                            sx={petit(100)}
                          />
                        </TableCell>
                      )}
                      {famille === "lentille" && (
                        <TableCell>
                          <TextField
                            size="small"
                            type="date"
                            value={l.date_peremption}
                            onChange={(e) => changer(l.cle, { date_peremption: e.target.value })}
                            slotProps={{ htmlInput: { "aria-label": `Péremption ${l.designation}` } }}
                            sx={petit(150)}
                          />
                        </TableCell>
                      )}
                      <TableCell align="center">
                        <Checkbox
                          size="small"
                          checked={l.non_conforme}
                          onChange={(e) => changer(l.cle, { non_conforme: e.target.checked })}
                          slotProps={{ input: { "aria-label": `Non conforme ${l.designation}` } }}
                        />
                      </TableCell>
                      <TableCell>
                        <TextField
                          size="small"
                          value={l.motif}
                          disabled={!l.non_conforme}
                          placeholder={l.non_conforme ? "Choix obligatoire" : ""}
                          error={l.non_conforme && !l.motif.trim()}
                          onChange={(e) => changer(l.cle, { motif: e.target.value })}
                          slotProps={{ htmlInput: { "aria-label": `Motif ${l.designation}` } }}
                          sx={petit(170)}
                        />
                      </TableCell>
                      <TableCell>
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
            </Table>
            {visibles.length === 0 && (
              <Box sx={{ p: 2 }}>
                <Typography color="text.secondary">Aucun article dans cet onglet.</Typography>
              </Box>
            )}
          </TableContainer>
        </>
      )}

      <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ alignItems: "flex-start" }}>
        <Stack spacing={1.5} sx={{ minWidth: 260 }}>
          <TextField
            size="small"
            label="Dernier prix d'achat HT"
            value={choisie?.dernier_prix ? montant(Number(choisie.dernier_prix)) : choisie ? "Premier achat" : ""}
            slotProps={{ htmlInput: { readOnly: true } }}
          />
          <Stack direction="row" spacing={1}>
            <TextField
              size="small"
              label="Taux remise %"
              value={remiseTous}
              onChange={(e) => setRemiseTous(e.target.value)}
              sx={{ width: 120 }}
            />
            <Button
              sx={BOUTON}
              disabled={lignes.length === 0}
              onClick={() => setLignes((ls) => ls.map((l) => ({ ...l, taux_remise: remiseTous })))}
            >
              Appliquer à tous
            </Button>
          </Stack>
        </Stack>
        <Table size="small" aria-label="Détail TVA" sx={{ maxWidth: 360, "& td, & th": { p: 0.5 } }}>
          <TableHead>
            <TableRow>
              <TableCell>Taux TVA</TableCell>
              <TableCell align="right">Base HT</TableCell>
              <TableCell align="right">Montant TVA</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {totaux.tva.map((t) => (
              <TableRow key={t.taux}>
                <TableCell>{t.taux} %</TableCell>
                <TableCell align="right">{montant(t.base)}</TableCell>
                <TableCell align="right">{montant(t.montant)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Box sx={{ flex: 1 }} />
        <Table size="small" aria-label="Totaux du bon" sx={{ maxWidth: 340, "& td": { p: 0.5 } }}>
          <TableBody>
            {[
              ["Total HT", totaux.totalHt],
              ["Remise", totaux.totalRemise],
              ["Remise exceptionnelle", totaux.remiseEx],
              ["Net HT", totaux.netHt],
              ["FODEC", totaux.totalFodec],
              ["TVA", totaux.totalTva],
            ].map(([libelle, valeur]) => (
              <TableRow key={libelle}>
                <TableCell>{libelle}</TableCell>
                <TableCell align="right">{montant(valeur as number)}</TableCell>
              </TableRow>
            ))}
            <TableRow>
              <TableCell>Taux remise exceptionnelle %</TableCell>
              <TableCell align="right">
                <TextField
                  size="small"
                  value={tauxRemiseEx}
                  onChange={(e) => setTauxRemiseEx(e.target.value)}
                  slotProps={{ htmlInput: { "aria-label": "Taux remise exceptionnelle" } }}
                  sx={petit(80)}
                />
              </TableCell>
            </TableRow>
            <TableRow sx={{ "& td": { fontWeight: 700, fontSize: 16, color: BORDEAUX } }}>
              <TableCell>Total TTC</TableCell>
              <TableCell align="right">{montant(totaux.totalTtc)}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </Stack>

      {validation.isError && <Alert severity="error">{validation.error.message}</Alert>}
      {message && (
        <Alert severity="success" onClose={() => setMessage("")}>
          {message}
        </Alert>
      )}
      <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end", alignItems: "center" }}>
        {manque && lignes.length > 0 && (
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
            setMessage("");
            validation.mutate();
          }}
        >
          Valider
        </Button>
      </Stack>

      {dialogue === "fournisseur" && (
        <Dialog open onClose={() => setDialogue(null)} maxWidth="lg" fullWidth>
          <DialogContent>
            <Fournisseurs
              droits={{ creer: droitsFournisseurs.creer, modifier: false }}
              onChoisi={(f) => {
                setFournisseur(f);
                setLignes((ls) => ls.filter((l) => l.ligne_commande === null));
                setDialogue(null);
              }}
            />
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDialogue(null)}>Fermer</Button>
          </DialogActions>
        </Dialog>
      )}
      {dialogue === "import" && fournisseur && magasin && (
        <ImportCommande
          magasin={magasin.id}
          fournisseur={fournisseur}
          dejaImportees={new Set(lignes.flatMap((l) => (l.ligne_commande === null ? [] : [l.ligne_commande])))}
          onImporte={importer}
          onFerme={() => setDialogue(null)}
        />
      )}
    </Stack>
  );
}
