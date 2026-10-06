import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import FormControlLabel from "@mui/material/FormControlLabel";
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
import { type Dispatch, type ReactNode, type SetStateAction, useEffect, useState } from "react";

import type { Fournisseur } from "../api/achats";
import {
  calculerPrix,
  enregistrerFiche,
  type FicheArticle,
  lireFiche,
  lireMouvements,
  type SaisieFiche,
  venteTTCDepuisHT,
  venteTTCDepuisMarge,
} from "../api/fiches";

/** Parties communes aux fiches article (monture, verre, lentille, divers) : en-tête, prix, stock, pied. */

export type Entete = {
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

export const ENTETE_VIDE: Entete = {
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

export type SaisiePrix = { achatHT: string; remise: string; tva: string; venteTTC: string };

export const nombre = (texte: string) => {
  const n = Number(texte.replace(",", ".").trim());
  return texte.trim() === "" || Number.isNaN(n) ? null : n;
};
export const arrondi = (n: number, decimales: number) => n.toFixed(decimales);

/** Champ calculé qu'on peut aussi saisir (marge, prix HT) : la saisie s'applique en sortant du champ. */
export function ChampCalcule({
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
 * État d'une fiche article : chargement, en-tête, fournisseur et prix dans le pays du magasin, enregistrement
 * (bouton Valider ou F4). `complement` donne ce qui est propre à la famille (caractéristiques).
 */
export function useFicheArticle({
  article,
  magasin,
  tauxTva,
  famille,
  lectureSeule,
  complet,
  complement,
  onFerme,
}: {
  article: string | null;
  magasin: string;
  tauxTva: string[];
  famille: FicheArticle["famille"];
  lectureSeule: boolean;
  /** Fiche assez remplie pour être validée (géométrie d'un verre…), en plus du fournisseur. */
  complet?: (entete: Entete) => boolean;
  complement: () => Partial<SaisieFiche>;
  onFerme: () => void;
}) {
  const queryClient = useQueryClient();
  const fiche = useQuery({
    queryKey: ["fiche", article, magasin],
    queryFn: () => lireFiche(article as string, magasin),
    enabled: Boolean(article),
  });
  const tvaParDefaut = tauxTva.length ? String(Math.max(...tauxTva.map(Number))) : "19";
  const [entete, setEntete] = useState<Entete>(ENTETE_VIDE);
  const [fournisseur, setFournisseur] = useState<Fournisseur | null>(null);
  const [prix, setPrix] = useState<SaisiePrix>({ achatHT: "", remise: "0", tva: tvaParDefaut, venteTTC: "" });

  // Fiche existante : on remplit le formulaire une fois chargée.
  const charge = fiche.data;
  useEffect(() => {
    if (!charge) return;
    const { prix: p, dernier_achat: dernier } = charge;
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

  const enregistrement = useMutation({
    mutationFn: () => {
      const saisie: SaisieFiche = { ...entete, famille, fournisseur: fournisseur?.id, ...complement() };
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
  const peutValider = !lectureSeule && Boolean(fournisseur) && (complet?.(entete) ?? true) && !enregistrement.isPending;

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

  const changerEntete = <K extends keyof Entete>(cle: K, valeur: Entete[K]) =>
    setEntete((e) => ({ ...e, [cle]: valeur }));

  /** Champ texte et case à cocher de l'en-tête. */
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

  return { fiche, entete, fournisseur, setFournisseur, prix, setPrix, enregistrement, peutValider, texte, case_ };
}

/** Onglet « Détail prix » : cases de l'article, prix d'achat, TVA, marge et prix de vente. */
export function OngletDetailPrix({
  cases,
  prix,
  setPrix,
  fodec,
  tauxTva,
  monnaie,
  dernier,
  lectureSeule,
}: {
  cases: ReactNode;
  prix: SaisiePrix;
  setPrix: Dispatch<SetStateAction<SaisiePrix>>;
  fodec: boolean;
  tauxTva: string[];
  monnaie: { devise: string; decimales: number };
  dernier: FicheArticle["dernier_achat"] | undefined;
  lectureSeule: boolean;
}) {
  const calcul = calculerPrix({
    achatHT: nombre(prix.achatHT) ?? 0,
    remise: nombre(prix.remise) ?? 0,
    tva: nombre(prix.tva) ?? 0,
    venteTTC: nombre(prix.venteTTC) ?? 0,
    fodec,
  });
  const d = monnaie.decimales;
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
  return (
    <Stack direction="row" spacing={4} useFlexGap sx={{ flexWrap: "wrap", alignItems: "flex-start" }}>
      <Stack>{cases}</Stack>
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
          onSaisi={(ht) => setPrix((p) => ({ ...p, venteTTC: arrondi(venteTTCDepuisHT(ht, nombre(p.tva) ?? 0), d) }))}
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
  );
}

/** Onglet « Stock » : stock par magasin d'une fiche enregistrée. */
export function OngletStock({ chargee }: { chargee: FicheArticle | undefined }) {
  return chargee ? (
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
  );
}

/** Pied de fiche : auteur, détail des mouvements, Annuler et Valider [F4]. */
export function PiedFiche({
  article,
  chargee,
  lectureSeule,
  peutValider,
  onValider,
  onFerme,
}: {
  article: string | null;
  chargee: FicheArticle | undefined;
  lectureSeule: boolean;
  peutValider: boolean;
  onValider: () => void;
  onFerme: () => void;
}) {
  const [voirMouvements, setVoirMouvements] = useState(false);
  return (
    <>
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
          <Button variant="contained" disabled={!peutValider} onClick={onValider}>
            Valider [F4]
          </Button>
        )}
      </DialogActions>
      {voirMouvements && article && <Mouvements article={article} onFerme={() => setVoirMouvements(false)} />}
    </>
  );
}
