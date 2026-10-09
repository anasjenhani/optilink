import UploadFile from "@mui/icons-material/UploadFile";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Link from "@mui/material/Link";
import List from "@mui/material/List";
import ListItemText from "@mui/material/ListItemText";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { importer, urlModele, type RapportImport, type TypeImport } from "../api/imports";
import { listerMagasins } from "../api/magasins";

function Alertes({ rapport }: { rapport: RapportImport }) {
  if (rapport.alertes.length === 0) return null;
  return (
    <Alert severity="warning">
      {rapport.alertes.length} ligne(s) à regarder avant d'importer :
      <List dense>
        {rapport.alertes.slice(0, 100).map((a) => (
          <ListItemText key={`${a.ligne}-${a.message}`} primary={`Ligne ${a.ligne} : ${a.message}`} />
        ))}
      </List>
    </Alert>
  );
}

function Rapport({ rapport }: { rapport: RapportImport }) {
  if (rapport.erreurs.length > 0) {
    return (
      <Alert severity="error">
        {rapport.erreurs.length} ligne(s) à corriger. Rien n'a été enregistré.
        <List dense>
          {rapport.erreurs.slice(0, 50).map((e) => (
            <ListItemText key={`${e.ligne}-${e.message}`} primary={`Ligne ${e.ligne} : ${e.message}`} />
          ))}
        </List>
      </Alert>
    );
  }
  const quoi = `${rapport.crees} créé(s)${rapport.modifies ? `, ${rapport.modifies} mis à jour` : ""}`;
  return (
    <>
      <Alert severity={rapport.apercu ? "info" : "success"}>
        {rapport.apercu
          ? `Fichier vérifié : ${rapport.lignes} ligne(s), ${quoi} à l'import.`
          : `Import terminé : ${quoi}.`}
      </Alert>
      {rapport.apercu && <Alertes rapport={rapport} />}
    </>
  );
}

/** Ce que chaque import explique, et s'il se fait pour un magasin. */
const IMPORTS: Record<TypeImport, { titre: string; aide: string; magasin?: boolean; piece?: boolean }> = {
  catalogue: {
    titre: "Catalogue",
    aide: "Une ligne par article, mise à jour par référence. Fournisseur obligatoire (code ou raison sociale d'un fournisseur déjà créé) ; prix_ttc et tva pour la Tunisie.",
  },
  verres: {
    titre: "Verres",
    aide: "Une ligne par verre, mis à jour par référence. Fournisseur (code ou raison sociale) et géométrie obligatoires.",
  },
  stock: {
    titre: "Entrées de stock",
    aide: "Une ligne par article reçu : code_barres (ou reference) et quantite.",
    magasin: true,
    piece: true,
  },
  clients: {
    titre: "Clients d'un autre logiciel",
    aide: "Export Excel ou CSV de l'ancien logiciel, une ligne par client. Les noms de colonnes courants sont reconnus (N° fiche, Nom, Prénom, Tél, GSM, Date de naissance…). L'ancien n° de fiche est gardé : réimporter le même fichier met les fiches à jour sans doublon.",
    magasin: true,
  },
  fournisseurs: {
    titre: "Fournisseurs",
    aide: "Une ligne par fournisseur. Le code est attribué automatiquement ; un fournisseur déjà créé (même code, matricule fiscal ou raison sociale) est signalé puis mis à jour.",
  },
  receptions: {
    titre: "Bons de réception",
    aide: "Une ligne par article reçu ; les lignes d'un même n° de BL et fournisseur forment un bon. Un BL déjà saisi est refusé. Les verres commandés pour un client se reçoivent dans l'écran Bon de Réception.",
    magasin: true,
  },
  utilisateurs: {
    titre: "Utilisateurs",
    aide: "Une ligne par profil donné (plusieurs lignes pour plusieurs profils). Un identifiant déjà pris est refusé. Mot de passe provisoire de 12 caractères au moins : supprimez le fichier après l'import.",
  },
};

const INVALIDES = ["catalogue", "articles", "clients", "fournisseurs", "bons-reception", "utilisateurs"];

/** Import d'un fichier : modèles à télécharger, vérification puis import (tout ou rien). */
export function BlocImport({ type }: { type: TypeImport }) {
  const config = IMPORTS[type];
  const queryClient = useQueryClient();
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins, enabled: Boolean(config.magasin) });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = config.magasin ? magasinChoisi || magasins.data?.[0]?.id || "" : "";
  const [piece, setPiece] = useState("");
  const [fichier, setFichier] = useState<File | null>(null);
  const champs: Record<string, string> = {
    ...(config.magasin && { magasin }),
    ...(config.piece && { piece }),
  };
  const envoi = useMutation({
    mutationFn: (jeton?: string) => importer(type, fichier as File, champs, jeton),
    onSuccess: (rapport) => {
      if (!rapport.apercu && rapport.erreurs.length === 0) {
        setFichier(null);
        INVALIDES.forEach((cle) => void queryClient.invalidateQueries({ queryKey: [cle] }));
      }
    },
  });

  // L'import n'est possible qu'après une vérification sans erreur de ce fichier, pour ce magasin.
  const jeton = envoi.data?.apercu ? envoi.data.jeton : "";
  const { reset } = envoi;
  useEffect(() => reset(), [magasin, piece, reset]);
  const pret = Boolean(fichier) && (!config.magasin || Boolean(magasin));

  return (
    <Stack spacing={2}>
      <Typography variant="subtitle1">{config.titre}</Typography>
      <Typography variant="body2" color="text.secondary">
        {config.aide}
      </Typography>
      <Typography variant="body2">
        Télécharger le modèle :{" "}
        <Link href={urlModele(type, "xlsx")} download>
          Excel
        </Link>
        {" · "}
        <Link href={urlModele(type, "csv")} download>
          CSV
        </Link>
      </Typography>
      {config.magasin && (
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
          <TextField
            select
            size="small"
            label="Magasin"
            value={magasin}
            onChange={(e) => setMagasin(e.target.value)}
            sx={{ minWidth: 220 }}
          >
            {magasins.data?.map((m) => (
              <MenuItem key={m.id} value={m.id}>
                {m.nom}
              </MenuItem>
            ))}
          </TextField>
          {config.piece && (
            <TextField
              size="small"
              label="N° du bon de livraison"
              value={piece}
              onChange={(e) => setPiece(e.target.value)}
            />
          )}
        </Stack>
      )}
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ alignItems: { sm: "center" } }}>
        <Button component="label" variant="outlined">
          Choisir un fichier
          <input
            hidden
            type="file"
            accept=".xlsx,.csv"
            aria-label={`Fichier ${config.titre}`}
            onChange={(e) => {
              setFichier(e.target.files?.[0] ?? null);
              envoi.reset();
            }}
          />
        </Button>
        <Typography color="text.secondary">{fichier?.name ?? "Excel (.xlsx) ou CSV"}</Typography>
      </Stack>
      <Stack direction="row" spacing={2}>
        <Button variant="outlined" disabled={!pret || envoi.isPending} onClick={() => envoi.mutate(undefined)}>
          1. Vérifier
        </Button>
        <Button variant="contained" disabled={!jeton || envoi.isPending} onClick={() => envoi.mutate(jeton)}>
          2. Importer
        </Button>
      </Stack>
      {envoi.isError && <Alert severity="error">{envoi.error.message}</Alert>}
      {envoi.data && <Rapport rapport={envoi.data} />}
    </Stack>
  );
}

/** Bouton « Importer » d'un écran : ouvre l'import et ses modèles dans une fenêtre. */
export function BoutonImport({ type, libelle = "Importer" }: { type: TypeImport; libelle?: string }) {
  const [ouvert, setOuvert] = useState(false);
  return (
    <>
      <Button variant="outlined" startIcon={<UploadFile />} onClick={() => setOuvert(true)}>
        {libelle}
      </Button>
      {ouvert && (
        <Dialog open onClose={() => setOuvert(false)} maxWidth="md" fullWidth>
          <DialogTitle>Importer : {IMPORTS[type].titre}</DialogTitle>
          <DialogContent>
            <BlocImport type={type} />
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setOuvert(false)}>Fermer</Button>
          </DialogActions>
        </Dialog>
      )}
    </>
  );
}

/** Page des imports Excel ou CSV : un bloc par import autorisé. */
export function Imports({ types }: { types: TypeImport[] }) {
  return (
    <Card>
      <CardContent>
        <Stack spacing={4}>
          <Typography variant="h6" component="h2">
            Imports
          </Typography>
          {types.map((type) => (
            <BlocImport key={type} type={type} />
          ))}
        </Stack>
      </CardContent>
    </Card>
  );
}
