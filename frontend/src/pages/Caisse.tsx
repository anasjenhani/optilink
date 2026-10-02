import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import FormControlLabel from "@mui/material/FormControlLabel";
import ListItemButton from "@mui/material/ListItemButton";
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

import { chercherClients, type Client } from "../api/clients";
import { chercherArticles, encaisser, type Article, type ModePaiement, type Vente } from "../api/caisse";
import { listerMagasins } from "../api/magasins";
import { enUnites, formater, formaterTexte, versTexte, type Monnaie } from "../api/monnaie";

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
  const pays = magasins.data?.find((m) => m.id === magasin)?.pays;
  const monnaie: Monnaie = { devise: pays?.devise ?? "TND", decimales: pays?.decimales ?? 3 };
  const unites = (montant: string) => enUnites(montant, monnaie.decimales);
  const [recherche, setRecherche] = useState("");
  const [panier, setPanier] = useState<Ligne[]>([]);
  const [mode, setMode] = useState<ModePaiement>("carte");
  const [derniereVente, setDerniereVente] = useState<Vente | null>(null);
  // Commande : acompte maintenant, solde à la livraison. Obligatoire dès qu'un article est
  // commandé au fournisseur (verres…).
  const [enCommande, setEnCommande] = useState(false);
  const [acompte, setAcompte] = useState("");
  const [livraisonPrevue, setLivraisonPrevue] = useState("");
  // Client facultatif sur le ticket ; il sera repris pour la facture, générée à part.
  const [avecClient, setAvecClient] = useState(false);
  const [rechercheClient, setRechercheClient] = useState("");
  const [client, setClient] = useState<Client | null>(null);
  const clients = useQuery({
    queryKey: ["clients", rechercheClient],
    queryFn: () => chercherClients(rechercheClient),
    enabled: avecClient && !client && rechercheClient.trim().length >= 2,
  });

  const articles = useQuery({
    queryKey: ["articles", magasin, recherche],
    queryFn: () => chercherArticles(magasin, recherche),
    enabled: Boolean(magasin) && recherche.trim().length >= 2,
  });

  const total = panier.reduce((somme, l) => somme + unites(l.article.prix_vente_ttc) * l.quantite, 0);
  const commandeImposee = panier.some((l) => l.article.sur_commande);
  const commande = enCommande || commandeImposee;
  const montantAcompte = Math.min(unites(acompte || "0"), total);

  const vente = useMutation({
    mutationFn: () =>
      encaisser({
        magasin,
        client: avecClient ? client?.id : undefined,
        lignes: panier.map((l) => ({ article: l.article.id, quantite: l.quantite })),
        paiements:
          commande && montantAcompte === 0
            ? []
            : [{ mode, montant: versTexte(commande ? montantAcompte : total, monnaie.decimales) }],
        ...(commande ? { commande: true, ...(livraisonPrevue ? { livraison_prevue_le: livraisonPrevue } : {}) } : {}),
      }),
    onSuccess: (enregistree) => {
      setDerniereVente(enregistree);
      setPanier([]);
      setEnCommande(false);
      setAcompte("");
      setLivraisonPrevue("");
      setAvecClient(false);
      setClient(null);
      setRechercheClient("");
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
                  <Button size="small" onClick={() => ajouter(article)} disabled={!article.sur_commande && !article.stock}>
                    Ajouter
                  </Button>
                }
              >
                <ListItemText
                  primary={`${article.libelle} · ${formaterTexte(article.prix_vente_ttc, monnaie)}`}
                  secondary={[
                    article.reference,
                    article.description,
                    article.sur_commande ? "sur commande" : `stock ${article.stock ?? "?"}`,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
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
                        disabled={!ligne.article.sur_commande && ligne.quantite >= (ligne.article.stock ?? 0)}
                        onClick={() => changerQuantite(ligne, 1)}
                      >
                        +
                      </IconButton>
                    </TableCell>
                    <TableCell align="right">
                      {formater(unites(ligne.article.prix_vente_ttc) * ligne.quantite, monnaie)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          <FormControlLabel
            control={<Checkbox checked={avecClient} onChange={(e) => setAvecClient(e.target.checked)} />}
            label="Rattacher un client au ticket"
          />
          {avecClient && client && (
            <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
              <Typography>
                Client : {client.nom.toUpperCase()} {client.prenom}
              </Typography>
              <Button size="small" onClick={() => setClient(null)}>
                Changer
              </Button>
            </Stack>
          )}
          {avecClient && !client && (
            <>
              <TextField
                label="Client"
                helperText="Nom, téléphone ou e-mail"
                value={rechercheClient}
                onChange={(e) => setRechercheClient(e.target.value)}
              />
              {clients.isError && <Alert severity="error">{clients.error.message}</Alert>}
              <List dense>
                {clients.data?.map((c) => (
                  <ListItemButton key={c.id} onClick={() => setClient(c)}>
                    <ListItemText primary={`${c.nom.toUpperCase()} ${c.prenom}`} secondary={c.telephone} />
                  </ListItemButton>
                ))}
              </List>
            </>
          )}

          <FormControlLabel
            control={
              <Checkbox
                checked={commande}
                disabled={commandeImposee}
                onChange={(e) => setEnCommande(e.target.checked)}
              />
            }
            label={
              commandeImposee
                ? "Commande : verres commandés au fournisseur, solde à la livraison"
                : "Commande : acompte maintenant, solde à la livraison"
            }
          />
          {commande && (
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <TextField
                label="Acompte"
                type="number"
                value={acompte}
                onChange={(e) => setAcompte(e.target.value)}
                helperText={`Reste à la livraison : ${formater(total - montantAcompte, monnaie)}`}
              />
              <TextField
                label="Livraison prévue le"
                type="date"
                value={livraisonPrevue}
                onChange={(e) => setLivraisonPrevue(e.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
              />
            </Stack>
          )}

          <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
            <Typography variant="h5" sx={{ flexGrow: 1 }}>
              Total : {formater(total, monnaie)}
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
              {commande ? "Enregistrer la commande" : "Encaisser"}
            </Button>
          </Stack>

          {vente.isError && <Alert severity="error">{vente.error.message}</Alert>}
          {derniereVente && (
            <Alert severity="success">
              {derniereVente.statut === "en_commande" ? "Commande" : "Ticket"} {derniereVente.numero},{" "}
              {formaterTexte(derniereVente.total_ttc, { devise: derniereVente.devise, decimales: monnaie.decimales })}
              {derniereVente.statut === "en_commande" &&
                `, reste ${formaterTexte(derniereVente.reste_a_payer, { devise: derniereVente.devise, decimales: monnaie.decimales })} à la livraison`}
              .
            </Alert>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
