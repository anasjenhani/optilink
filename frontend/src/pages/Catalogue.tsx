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
import Button from "@mui/material/Button";
import { FicheArticle } from "./FicheArticle";
import { FicheMonture } from "./FicheMonture";
import { BoutonImport } from "./Imports";

/**
 * Catalogue par famille, avec prix et stock du magasin. Chaque article s'ouvre sur sa fiche (création et
 * modification) : fiche monture pour les montures, fiche article pour les verres, lentilles et articles divers.
 */
export function Catalogue({
  familleInitiale = "monture",
  importer = false,
  fiche = { creer: false, modifier: false },
}: {
  familleInitiale?: Famille | "";
  /** Bouton d'import : des verres sur la liste des verres, du catalogue sinon. */
  importer?: boolean;
  /** Droits sur les fiches article. */
  fiche?: { creer: boolean; modifier: boolean };
}) {
  // Fiche ouverte : article (null pour un nouveau) et sa famille.
  const [ouverte, setOuverte] = useState<{ article: string | null; famille: Famille } | undefined>(undefined);
  const [magasinChoisi, setMagasin] = useState("");
  const [famille, setFamille] = useState<Famille | "">(familleInitiale);
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
            {fiche.creer && famille && (
              <Button
                variant="contained"
                onClick={() => setOuverte({ article: null, famille })}
                sx={{ whiteSpace: "nowrap" }}
              >
                {famille === "monture" ? "Nouvelle monture" : "Nouvel article"}
              </Button>
            )}
            {importer && (
              <BoutonImport
                type={famille === "verre" ? "verres" : "catalogue"}
                libelle={famille === "verre" ? "Importer des verres" : "Importer des articles"}
              />
            )}
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
                  <TableRow
                    key={article.id}
                    hover
                    onClick={() => setOuverte({ article: article.id, famille: article.famille })}
                    sx={{ cursor: "pointer" }}
                  >
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
        {ouverte && magasin && ouverte.famille === "monture" && (
          <FicheMonture
            article={ouverte.article}
            magasin={magasin}
            monnaie={monnaie}
            tauxTva={pays?.taux_tva ?? []}
            lectureSeule={ouverte.article !== null && !fiche.modifier}
            onFerme={() => setOuverte(undefined)}
          />
        )}
        {ouverte && magasin && ouverte.famille !== "monture" && (
          <FicheArticle
            famille={ouverte.famille}
            article={ouverte.article}
            magasin={magasin}
            monnaie={monnaie}
            tauxTva={pays?.taux_tva ?? []}
            lectureSeule={ouverte.article !== null && !fiche.modifier}
            onFerme={() => setOuverte(undefined)}
          />
        )}
      </CardContent>
    </Card>
  );
}
