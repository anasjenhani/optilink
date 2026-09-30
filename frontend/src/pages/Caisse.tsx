import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import IconButton from "@mui/material/IconButton";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemText from "@mui/material/ListItemText";
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
import { useState } from "react";

import {
  chercherArticles,
  encaisser,
  enCentimes,
  enEuros,
  type Article,
  type ModePaiement,
  type Vente,
} from "../api/caisse";
import { listerMagasins } from "../api/magasins";

type Ligne = { article: Article; quantite: number };

const MODES: { valeur: ModePaiement; libelle: string }[] = [
  { valeur: "carte", libelle: "Carte bancaire" },
  { valeur: "especes", libelle: "Espèces" },
  { valeur: "cheque", libelle: "Chèque" },
];

export function Caisse() {
  const queryClient = useQueryClient();
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = magasinChoisi || magasins.data?.[0]?.id || "";
  const [recherche, setRecherche] = useState("");
  const [panier, setPanier] = useState<Ligne[]>([]);
  const [mode, setMode] = useState<ModePaiement>("carte");
  const [derniereVente, setDerniereVente] = useState<Vente | null>(null);

  const articles = useQuery({
    queryKey: ["articles", magasin, recherche],
    queryFn: () => chercherArticles(magasin, recherche),
    enabled: Boolean(magasin) && recherche.trim().length >= 2,
  });

  const total = panier.reduce((somme, l) => somme + enCentimes(l.article.prix_vente_ttc) * l.quantite, 0);

  const vente = useMutation({
    mutationFn: () =>
      encaisser({
        magasin,
        lignes: panier.map((l) => ({ article: l.article.id, quantite: l.quantite })),
        paiements: [{ mode, montant: enEuros(total) }],
      }),
    onSuccess: (enregistree) => {
      setDerniereVente(enregistree);
      setPanier([]);
      void queryClient.invalidateQueries({ queryKey: ["articles"] });
    },
  });

  function ajouter(article: Article) {
    setDerniereVente(null);
    setPanier((lignes) => {
      const existante = lignes.find((l) => l.article.id === article.id);
      if (!existante) return [...lignes, { article, quantite: 1 }];
      return lignes.map((l) => (l === existante ? { ...l, quantite: l.quantite + 1 } : l));
    });
  }

  function changerQuantite(ligne: Ligne, delta: number) {
    setPanier((lignes) =>
      lignes
        .map((l) => (l === ligne ? { ...l, quantite: l.quantite + delta } : l))
        .filter((l) => l.quantite > 0),
    );
  }

  function changerMagasin(id: string) {
    setMagasin(id);
    setPanier([]);
    setDerniereVente(null);
  }

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Caisse
          </Typography>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField
              select
              label="Magasin"
              value={magasin}
              onChange={(e) => changerMagasin(e.target.value)}
              sx={{ minWidth: 200 }}
            >
              {magasins.data?.map((m) => (
                <MenuItem key={m.id} value={m.id}>
                  {m.nom}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="Rechercher un article"
              helperText="Référence, libellé ou code-barres"
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
              sx={{ flexGrow: 1 }}
            />
          </Stack>

          {articles.isError && <Alert severity="error">{articles.error.message}</Alert>}
          {articles.data && articles.data.length === 0 && (
            <Typography color="text.secondary">Aucun article trouvé.</Typography>
          )}
          <List dense>
            {articles.data?.map((article) => (
              <ListItem
                key={article.id}
                disableGutters
                secondaryAction={
                  <Button size="small" onClick={() => ajouter(article)} disabled={!article.stock}>
                    Ajouter
                  </Button>
                }
              >
                <ListItemText
                  primary={`${article.libelle} · ${article.prix_vente_ttc} €`}
                  secondary={`${article.reference} · stock ${article.stock ?? "?"}`}
                />
              </ListItem>
            ))}
          </List>

          {panier.length > 0 && (
            <Table size="small" aria-label="Panier">
              <TableHead>
                <TableRow>
                  <TableCell>Article</TableCell>
                  <TableCell align="center">Quantité</TableCell>
                  <TableCell align="right">Total</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {panier.map((ligne) => (
                  <TableRow key={ligne.article.id}>
                    <TableCell>{ligne.article.libelle}</TableCell>
                    <TableCell align="center">
                      <IconButton size="small" aria-label="Retirer un" onClick={() => changerQuantite(ligne, -1)}>
                        −
                      </IconButton>
                      {ligne.quantite}
                      <IconButton
                        size="small"
                        aria-label="Ajouter un"
                        disabled={ligne.quantite >= (ligne.article.stock ?? 0)}
                        onClick={() => changerQuantite(ligne, 1)}
                      >
                        +
                      </IconButton>
                    </TableCell>
                    <TableCell align="right">
                      {enEuros(enCentimes(ligne.article.prix_vente_ttc) * ligne.quantite)} €
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
            <Typography variant="h5" sx={{ flexGrow: 1 }}>
              Total : {enEuros(total)} €
            </Typography>
            <TextField
              select
              size="small"
              label="Paiement"
              value={mode}
              onChange={(e) => setMode(e.target.value as ModePaiement)}
            >
              {MODES.map((m) => (
                <MenuItem key={m.valeur} value={m.valeur}>
                  {m.libelle}
                </MenuItem>
              ))}
            </TextField>
            <Button
              variant="contained"
              size="large"
              disabled={panier.length === 0 || vente.isPending}
              onClick={() => vente.mutate()}
            >
              Encaisser
            </Button>
          </Stack>

          {vente.isError && <Alert severity="error">{vente.error.message}</Alert>}
          {derniereVente && (
            <Alert severity="success">
              Vente enregistrée : facture {derniereVente.numero}, {derniereVente.total_ttc} €.
            </Alert>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
