import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Link from "@mui/material/Link";
import List from "@mui/material/List";
import ListItemText from "@mui/material/ListItemText";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import {
  COLONNES_CATALOGUE,
  COLONNES_STOCK,
  importerCatalogue,
  importerStock,
  urlModele,
  type RapportImport,
} from "../api/imports";
import { listerMagasins } from "../api/magasins";

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
    <Alert severity={rapport.apercu ? "info" : "success"}>
      {rapport.apercu
        ? `Fichier correct : ${rapport.lignes} ligne(s), ${quoi} à l'import.`
        : `Import terminé : ${quoi}.`}
    </Alert>
  );
}

function Bloc({
  titre,
  aide,
  colonnes,
  nomModele,
  champs,
  pret = true,
  envoyer,
}: {
  titre: string;
  aide: string;
  colonnes: string[];
  nomModele: string;
  champs?: ReactNode;
  pret?: boolean;
  envoyer: (fichier: File, apercu: boolean) => Promise<RapportImport>;
}) {
  const queryClient = useQueryClient();
  const [fichier, setFichier] = useState<File | null>(null);
  const envoi = useMutation({
    mutationFn: (apercu: boolean) => envoyer(fichier as File, apercu),
    onSuccess: (rapport) => {
      if (!rapport.apercu && rapport.erreurs.length === 0) {
        setFichier(null);
        void queryClient.invalidateQueries({ queryKey: ["catalogue"] });
        void queryClient.invalidateQueries({ queryKey: ["articles"] });
      }
    },
  });

  return (
    <Stack spacing={2}>
      <Typography variant="subtitle1">{titre}</Typography>
      <Typography variant="body2" color="text.secondary">
        {aide}{" "}
        <Link href={urlModele(colonnes)} download={nomModele}>
          Télécharger le modèle
        </Link>
      </Typography>
      {champs}
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ alignItems: { sm: "center" } }}>
        <Button component="label" variant="outlined">
          Choisir un fichier
          <input
            hidden
            type="file"
            accept=".xlsx,.csv"
            aria-label={`Fichier ${titre}`}
            onChange={(e) => {
              setFichier(e.target.files?.[0] ?? null);
              envoi.reset();
            }}
          />
        </Button>
        <Typography color="text.secondary">{fichier?.name ?? "Excel (.xlsx) ou CSV"}</Typography>
      </Stack>
      <Stack direction="row" spacing={2}>
        <Button disabled={!fichier || !pret || envoi.isPending} onClick={() => envoi.mutate(true)}>
          Vérifier
        </Button>
        <Button variant="contained" disabled={!fichier || !pret || envoi.isPending} onClick={() => envoi.mutate(false)}>
          Importer
        </Button>
      </Stack>
      {envoi.isError && <Alert severity="error">{envoi.error.message}</Alert>}
      {envoi.data && <Rapport rapport={envoi.data} />}
    </Stack>
  );
}

/** Imports Excel ou CSV : catalogue (articles, fiches, prix) et entrées de stock d'un magasin. */
export function Imports({ droits }: { droits: { catalogue: boolean; stock: boolean } }) {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = magasinChoisi || magasins.data?.[0]?.id || "";
  const [piece, setPiece] = useState("");

  return (
    <Card>
      <CardContent>
        <Stack spacing={3}>
          <Typography variant="h6" component="h2">
            Imports
          </Typography>
          {droits.catalogue && (
            <Bloc
              titre="Catalogue"
              aide="Une ligne par article, mise à jour par référence. Fournisseur obligatoire (déjà créé dans l'administration) ; prix_ttc et tva pour la Tunisie."
              colonnes={COLONNES_CATALOGUE}
              nomModele="modele-catalogue.csv"
              envoyer={importerCatalogue}
            />
          )}
          {droits.stock && (
            <Bloc
              titre="Entrées de stock"
              aide="Une ligne par article reçu : code_barres (ou reference) et quantite."
              colonnes={COLONNES_STOCK}
              nomModele="modele-entrees-stock.csv"
              pret={Boolean(magasin)}
              champs={
                <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                  <TextField
                    select
                    size="small"
                    label="Magasin"
                    value={magasin}
                    onChange={(e) => setMagasin(e.target.value)}
                  >
                    {magasins.data?.map((m) => (
                      <MenuItem key={m.id} value={m.id}>
                        {m.nom}
                      </MenuItem>
                    ))}
                  </TextField>
                  <TextField
                    size="small"
                    label="N° du bon de livraison"
                    value={piece}
                    onChange={(e) => setPiece(e.target.value)}
                  />
                </Stack>
              }
              envoyer={(fichier, apercu) => importerStock(fichier, magasin, piece, apercu)}
            />
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
