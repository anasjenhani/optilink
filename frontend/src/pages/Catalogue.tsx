import Alert from "@mui/material/Alert";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { chercherArticles, FAMILLES, type Famille } from "../api/caisse";
import { listerMagasins } from "../api/magasins";
import { formaterTexte } from "../api/monnaie";

/** Catalogue par famille, avec prix et stock du magasin. Les articles se créent dans l'administration. */
export function Catalogue() {
  const [magasinChoisi, setMagasin] = useState("");
  const [famille, setFamille] = useState<Famille | "">("monture");
  const [recherche, setRecherche] = useState("");
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const magasin = magasinChoisi || magasins.data?.[0]?.id || "";
  const pays = magasins.data?.find((m) => m.id === magasin)?.pays;
  const monnaie = { devise: pays?.devise ?? "TND", decimales: pays?.decimales ?? 3 };
  const articles = useQuery({
    queryKey: ["catalogue", magasin, famille, recherche],
    queryFn: () => chercherArticles(magasin, recherche, famille),
    enabled: Boolean(magasin),
  });

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Catalogue
          </Typography>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField select size="small" label="Magasin" value={magasin} onChange={(e) => setMagasin(e.target.value)}>
              {magasins.data?.map((m) => (
                <MenuItem key={m.id} value={m.id}>
                  {m.nom}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              size="small"
              label="Famille"
              value={famille}
              onChange={(e) => setFamille(e.target.value as Famille | "")}
              sx={{ minWidth: 140 }}
            >
              <MenuItem value="">Toutes</MenuItem>
              {FAMILLES.map((f) => (
                <MenuItem key={f.valeur} value={f.valeur}>
                  {f.libelle}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              size="small"
              label="Rechercher dans le catalogue"
              helperText="Référence, libellé, marque, modèle ou gamme"
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
              sx={{ flexGrow: 1 }}
            />
          </Stack>
          {articles.isError && <Alert severity="error">{articles.error.message}</Alert>}
          {articles.data?.length === 0 && <Typography color="text.secondary">Aucun article.</Typography>}
          {Boolean(articles.data?.length) && (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Référence</TableCell>
                  <TableCell>Article</TableCell>
                  <TableCell align="right">Prix TTC</TableCell>
                  <TableCell align="right">Stock</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {articles.data?.map((article) => (
                  <TableRow key={article.id}>
                    <TableCell>{article.reference}</TableCell>
                    <TableCell>
                      {article.libelle}
                      {(article.description || article.fournisseur || article.code_barres) && (
                        <Typography variant="body2" color="text.secondary">
                          {[article.description, article.fournisseur, article.code_barres].filter(Boolean).join(" · ")}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell align="right">{formaterTexte(article.prix_vente_ttc, monnaie)}</TableCell>
                    <TableCell align="right">{article.sur_commande ? "sur commande" : article.stock}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
