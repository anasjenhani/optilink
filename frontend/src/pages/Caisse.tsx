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
import Chip from "@mui/material/Chip";
import {
  chercherArticles,
  encaisser,
  TYPES_VENTE,
  type Article,
  type ModePaiement,
  type RoleLigne,
  type SaisieLentilles,
  type SaisieLunette,
  type TypeVente,
  type Vente,
} from "../api/caisse";
import { listerMagasins } from "../api/magasins";
import { enUnites, formater, formaterTexte, versTexte, type Monnaie } from "../api/monnaie";
import { FicheLentilles, type LentilleChoisie } from "./FicheLentilles";
import { ChampPeniche, FicheLunette, type ArticleLunette } from "./FicheLunette";

/** Ligne du panier ; celles d'une lunette portent son rang (``lunette``) et leur place. */
type Ligne = {
  article: Article;
  quantite: number;
  lunette?: number;
  lentilles?: number;
  numero_lot?: string;
  date_peremption?: string;
  role?: RoleLigne;
  remise_pct?: string;
};

const PLACES: Record<RoleLigne, string> = {
  monture: "Monture",
  verre_d: "Verre droit",
  verre_g: "Verre gauche",
  supplement_d: "Supplément droit",
  supplement_g: "Supplément gauche",
  lentille_d: "Lentille droite",
  lentille_g: "Lentille gauche",
};

/** Ce que l'utilisateur peut faire dans la fiche lunettes. */
export type DroitsLunette = {
  remise: boolean;
  voirOrdonnances: boolean;
  saisirOrdonnance: boolean;
};

const MODES: { valeur: ModePaiement; libelle: string }[] = [
  { valeur: "carte", libelle: "Carte bancaire" },
  { valeur: "especes", libelle: "Espèces" },
  { valeur: "cheque", libelle: "Chèque" },
];

/**
 * Vente au comptoir guidée : le client (ou ``null`` pour un client de passage) et le magasin
 * sont choisis à l'étape d'avant, et le type de vente filtre les articles proposés.
 */
type Parcours = {
  client: Client | null;
  magasin: string;
  typeVente: TypeVente;
  onTypeVente: (type: TypeVente) => void;
  onNouvelleVente: () => void;
  droits?: DroitsLunette;
};

export function Caisse({ parcours }: { parcours?: Parcours } = {}) {
  const queryClient = useQueryClient();
  const magasins = useQuery({
    queryKey: ["magasins"],
    queryFn: listerMagasins,
  });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = parcours?.magasin || magasinChoisi || magasins.data?.[0]?.id || "";
  const typeVente = parcours?.typeVente ?? "";
  const pays = magasins.data?.find((m) => m.id === magasin)?.pays;
  const monnaie: Monnaie = {
    devise: pays?.devise ?? "TND",
    decimales: pays?.decimales ?? 3,
  };
  const unites = (montant: string) => enUnites(montant, monnaie.decimales);
  const [recherche, setRecherche] = useState("");
  const [panier, setPanier] = useState<Ligne[]>([]);
  const [lunettes, setLunettes] = useState<SaisieLunette[]>([]);
  const ficheLunette = parcours?.typeVente === "optique";
  const [jeuxLentilles, setJeuxLentilles] = useState<SaisieLentilles[]>([]);
  const ficheLentilles = parcours?.typeVente === "lentille";
  // Lot et péremption : saisis pour les lentilles et leurs produits.
  const avecLots = ficheLentilles || panier.some((l) => l.numero_lot || l.date_peremption);
  const equipement = (l: Ligne) =>
    l.lunette !== undefined ? `L${l.lunette}` : l.lentilles !== undefined ? `C${l.lentilles}` : null;
  const [mode, setMode] = useState<ModePaiement>("carte");
  const [derniereVente, setDerniereVente] = useState<Vente | null>(null);
  // Commande : acompte maintenant, solde à la livraison. Obligatoire dès qu'un article est
  // commandé au fournisseur (verres…).
  const [enCommande, setEnCommande] = useState(false);
  const [acompte, setAcompte] = useState("");
  const [livraisonPrevue, setLivraisonPrevue] = useState("");
  // Bac numéroté où le vendeur range l'équipement de la commande.
  const [peniche, setPeniche] = useState("");
  // Client facultatif sur le ticket ; il sera repris pour la facture, générée à part.
  const [avecClient, setAvecClient] = useState(false);
  const [rechercheClient, setRechercheClient] = useState("");
  const [clientChoisi, setClient] = useState<Client | null>(null);
  const client = parcours ? parcours.client : clientChoisi;
  const clients = useQuery({
    queryKey: ["clients", rechercheClient],
    queryFn: () => chercherClients(rechercheClient),
    enabled: avecClient && !client && rechercheClient.trim().length >= 2,
  });

  const articles = useQuery({
    queryKey: ["articles", magasin, recherche, typeVente],
    queryFn: () => chercherArticles(magasin, recherche, "", typeVente),
    enabled: Boolean(magasin) && (recherche.trim().length >= 2 || Boolean(typeVente)),
  });

  const totalLigne = (l: Ligne) =>
    Math.round(unites(l.article.prix_vente_ttc) * l.quantite * (1 - Number(l.remise_pct || 0) / 100));
  const total = panier.reduce((somme, l) => somme + totalLigne(l), 0);
  // Verres commandés au fournisseur, ou lunette optique ou applique à préparer : commande et péniche.
  // Vente « Lunettes optiques » : la péniche se saisit dès le départ, avant même la première lunette.
  const lunetteARanger =
    ficheLunette ||
    panier.some(
      (l) =>
        l.article.famille === "monture" &&
        ["optique", "applique"].includes(String(l.article.caracteristiques?.categorie ?? "")),
    );
  const commandeImposee = lunetteARanger || panier.some((l) => l.article.sur_commande);
  const commande = enCommande || commandeImposee;
  const maxPeniche = magasins.data?.find((m) => m.id === magasin)?.nombre_peniches;
  const montantAcompte = Math.min(unites(acompte || "0"), total);

  const vente = useMutation({
    mutationFn: () =>
      encaisser({
        magasin,
        client: parcours || avecClient ? client?.id : undefined,
        lignes: panier.map((l) => ({
          article: l.article.id,
          quantite: l.quantite,
          ...(Number(l.remise_pct || 0) > 0 ? { remise_pct: l.remise_pct } : {}),
          ...(l.lunette !== undefined ? { lunette: l.lunette, role: l.role } : {}),
          ...(l.lentilles !== undefined ? { lentilles: l.lentilles, role: l.role } : {}),
          ...(l.numero_lot ? { numero_lot: l.numero_lot } : {}),
          ...(l.date_peremption ? { date_peremption: l.date_peremption } : {}),
          ...(l.article.plage ? { plage: l.article.plage } : {}),
        })),
        ...(lunettes.length ? { lunettes } : {}),
        ...(jeuxLentilles.length ? { lentilles: jeuxLentilles } : {}),
        paiements:
          commande && montantAcompte === 0
            ? []
            : [
                {
                  mode,
                  montant: versTexte(commande ? montantAcompte : total, monnaie.decimales),
                },
              ],
        ...(commande
          ? {
              commande: true,
              ...(livraisonPrevue ? { livraison_prevue_le: livraisonPrevue } : {}),
              peniche: Number(peniche),
            }
          : {}),
      }),
    onSuccess: (enregistree) => {
      setDerniereVente(enregistree);
      setPanier([]);
      setLunettes([]);
      setJeuxLentilles([]);
      setEnCommande(false);
      setAcompte("");
      setLivraisonPrevue("");
      setPeniche("");
      setAvecClient(false);
      setClient(null);
      setRechercheClient("");
      void queryClient.invalidateQueries({ queryKey: ["articles"] });
    },
  });

  // Une douchette tape le code-barres puis Entrée : l'article va directement au panier.
  // La case est vidée tout de suite : deux scans rapprochés ne se collent pas l'un à l'autre.
  // Un code qui n'est pas un code-barres en stock reste dans la case comme une recherche.
  async function scanner(code: string) {
    if (!magasin || !code) return;
    setRecherche("");
    const trouves = await chercherArticles(magasin, code);
    const article = trouves.find((a) => a.code_barres === code);
    if (article && (article.sur_commande || article.stock)) ajouter(article);
    else setRecherche((r) => r || code);
  }

  function ajouter(article: Article) {
    setDerniereVente(null);
    setPanier((lignes) => {
      const existante = lignes.find((l) => l.article.id === article.id && equipement(l) === null);
      if (!existante) return [...lignes, { article, quantite: 1 }];
      return lignes.map((l) => (l === existante ? { ...l, quantite: l.quantite + 1 } : l));
    });
  }

  function ajouterLunette(lunette: SaisieLunette, articles: ArticleLunette[]) {
    setDerniereVente(null);
    const rang = lunettes.length;
    setLunettes([...lunettes, lunette]);
    setPanier((lignes) => [
      ...lignes,
      ...articles.map((a) => ({
        article: a.article,
        quantite: 1,
        lunette: rang,
        role: a.role,
        remise_pct: a.remise_pct,
      })),
    ]);
  }

  function ajouterLentilles(jeu: SaisieLentilles, choisies: LentilleChoisie[]) {
    setDerniereVente(null);
    const rang = jeuxLentilles.length;
    setJeuxLentilles([...jeuxLentilles, jeu]);
    setPanier((lignes) => [...lignes, ...choisies.map((c) => ({ ...c, lentilles: rang }))]);
  }

  function retirerLentilles(rang: number) {
    setJeuxLentilles((liste) => liste.filter((_, i) => i !== rang));
    setPanier((lignes) =>
      lignes
        .filter((l) => l.lentilles !== rang)
        .map((l) => (l.lentilles !== undefined && l.lentilles > rang ? { ...l, lentilles: l.lentilles - 1 } : l)),
    );
  }

  function changerLigne(ligne: Ligne, modification: Partial<Ligne>) {
    setPanier((lignes) => lignes.map((l) => (l === ligne ? { ...l, ...modification } : l)));
  }

  /** Retire une lunette et ses articles ; les suivantes reprennent leur numéro. */
  function retirerLunette(rang: number) {
    setLunettes((liste) => liste.filter((_, i) => i !== rang));
    setPanier((lignes) =>
      lignes
        .filter((l) => l.lunette !== rang)
        .map((l) => (l.lunette !== undefined && l.lunette > rang ? { ...l, lunette: l.lunette - 1 } : l)),
    );
  }

  function changerQuantite(ligne: Ligne, delta: number) {
    setPanier((lignes) =>
      lignes.map((l) => (l === ligne ? { ...l, quantite: l.quantite + delta } : l)).filter((l) => l.quantite > 0),
    );
  }

  function changerMagasin(id: string) {
    setMagasin(id);
    setPanier([]);
    setLunettes([]);
    setJeuxLentilles([]);
    setDerniereVente(null);
  }

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Caisse
          </Typography>
          {parcours && (
            <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: 1 }} aria-label="Type de vente">
              {TYPES_VENTE.map((t) => (
                <Chip
                  key={t.valeur}
                  label={t.libelle}
                  color={typeVente === t.valeur ? "primary" : "default"}
                  onClick={() => parcours.onTypeVente(t.valeur)}
                />
              ))}
            </Stack>
          )}
          {ficheLunette && parcours ? (
            <FicheLunette
              key={`lunette-${lunettes.length}-${derniereVente?.id ?? ""}`}
              magasin={magasin}
              client={client}
              monnaie={monnaie}
              numero={lunettes.length + 1}
              droits={
                parcours.droits ?? {
                  remise: false,
                  voirOrdonnances: false,
                  saisirOrdonnance: false,
                }
              }
              peniche={peniche}
              onPeniche={setPeniche}
              maxPeniche={maxPeniche}
              onValider={ajouterLunette}
            />
          ) : (
            <>
              {ficheLentilles && parcours && (
                <FicheLentilles
                  key={`lentilles-${jeuxLentilles.length}-${derniereVente?.id ?? ""}`}
                  magasin={magasin}
                  client={client}
                  monnaie={monnaie}
                  numero={jeuxLentilles.length + 1}
                  droits={parcours.droits ?? { remise: false, voirOrdonnances: false, saisirOrdonnance: false }}
                  onValider={ajouterLentilles}
                />
              )}
              <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                {!parcours && (
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
                )}
                <TextField
                  label="Rechercher un article"
                  helperText="Référence, libellé, marque ou code-barres (douchette)"
                  value={recherche}
                  onChange={(e) => setRecherche(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      void scanner(recherche.trim());
                    }
                  }}
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
                      <Button
                        size="small"
                        onClick={() => ajouter(article)}
                        disabled={!article.sur_commande && !article.stock}
                      >
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
            </>
          )}

          {panier.length > 0 && (
            <Table size="small" aria-label="Panier">
              <TableHead>
                <TableRow>
                  <TableCell>Article</TableCell>
                  {(lunettes.length > 0 || jeuxLentilles.length > 0) && <TableCell>Équipement</TableCell>}
                  {avecLots && <TableCell>N° lot</TableCell>}
                  {avecLots && <TableCell>Péremption</TableCell>}
                  <TableCell align="center">Quantité</TableCell>
                  <TableCell align="right">Total</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {panier.map((ligne, i) => (
                  <TableRow key={`${ligne.article.id}-${equipement(ligne) ?? ""}-${ligne.role ?? ""}-${i}`}>
                    <TableCell>
                      {ligne.article.libelle}
                      {Number(ligne.remise_pct || 0) > 0 && ` (remise ${ligne.remise_pct} %)`}
                    </TableCell>
                    {(lunettes.length > 0 || jeuxLentilles.length > 0) && (
                      <TableCell>
                        {ligne.lunette !== undefined && ligne.role && (
                          <>
                            Lunette n° {ligne.lunette + 1} · {PLACES[ligne.role]}
                            {(i === 0 || equipement(panier[i - 1]) !== equipement(ligne)) && (
                              <Button size="small" color="error" onClick={() => retirerLunette(ligne.lunette!)}>
                                Retirer la lunette
                              </Button>
                            )}
                          </>
                        )}
                        {ligne.lentilles !== undefined && ligne.role && (
                          <>
                            Lentilles n° {ligne.lentilles + 1} · {PLACES[ligne.role]}
                            {(i === 0 || equipement(panier[i - 1]) !== equipement(ligne)) && (
                              <Button size="small" color="error" onClick={() => retirerLentilles(ligne.lentilles!)}>
                                Retirer les lentilles
                              </Button>
                            )}
                          </>
                        )}
                      </TableCell>
                    )}
                    {avecLots && (
                      <TableCell>
                        <TextField
                          size="small"
                          variant="standard"
                          value={ligne.numero_lot ?? ""}
                          onChange={(e) => changerLigne(ligne, { numero_lot: e.target.value })}
                          slotProps={{ htmlInput: { "aria-label": `N° de lot ${ligne.article.libelle}` } }}
                          sx={{ width: 110 }}
                        />
                      </TableCell>
                    )}
                    {avecLots && (
                      <TableCell>
                        <TextField
                          size="small"
                          variant="standard"
                          type="date"
                          value={ligne.date_peremption ?? ""}
                          onChange={(e) => changerLigne(ligne, { date_peremption: e.target.value })}
                          slotProps={{ htmlInput: { "aria-label": `Péremption ${ligne.article.libelle}` } }}
                          sx={{ width: 140 }}
                        />
                      </TableCell>
                    )}
                    <TableCell align="center">
                      {equipement(ligne) === null && (
                        <IconButton size="small" aria-label="Retirer un" onClick={() => changerQuantite(ligne, -1)}>
                          −
                        </IconButton>
                      )}
                      {ligne.quantite}
                      {equipement(ligne) === null && (
                        <IconButton
                          size="small"
                          aria-label="Ajouter un"
                          disabled={!ligne.article.sur_commande && ligne.quantite >= (ligne.article.stock ?? 0)}
                          onClick={() => changerQuantite(ligne, 1)}
                        >
                          +
                        </IconButton>
                      )}
                    </TableCell>
                    <TableCell align="right">{formater(totalLigne(ligne), monnaie)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!parcours && (
            <FormControlLabel
              control={<Checkbox checked={avecClient} onChange={(e) => setAvecClient(e.target.checked)} />}
              label="Rattacher un client au ticket"
            />
          )}
          {!parcours && avecClient && client && (
            <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
              <Typography>
                Client : {client.nom.toUpperCase()} {client.prenom}
              </Typography>
              <Button size="small" onClick={() => setClient(null)}>
                Changer
              </Button>
            </Stack>
          )}
          {!parcours && avecClient && !client && (
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
              panier.some((l) => l.article.sur_commande)
                ? "Commande : verres commandés au fournisseur, solde à la livraison"
                : lunetteARanger
                  ? "Commande : lunette optique ou applique rangée dans une péniche, solde à la livraison"
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
              {!ficheLunette && <ChampPeniche valeur={peniche} onChange={setPeniche} max={maxPeniche} />}
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
              disabled={panier.length === 0 || vente.isPending || (commande && !peniche)}
              onClick={() => vente.mutate()}
            >
              {commande ? "Enregistrer la commande" : "Encaisser"}
            </Button>
          </Stack>

          {vente.isError && <Alert severity="error">{vente.error.message}</Alert>}
          {derniereVente && (
            <Alert severity="success">
              {derniereVente.statut === "en_commande" ? "Commande" : "Ticket"} {derniereVente.numero},{" "}
              {formaterTexte(derniereVente.total_ttc, {
                devise: derniereVente.devise,
                decimales: monnaie.decimales,
              })}
              {derniereVente.peniche && `, péniche ${derniereVente.peniche}`}
              {derniereVente.statut === "en_commande" &&
                `, reste ${formaterTexte(derniereVente.reste_a_payer, { devise: derniereVente.devise, decimales: monnaie.decimales })} à la livraison`}
              .
              {parcours && (
                <Button size="small" sx={{ ml: 2 }} onClick={parcours.onNouvelleVente}>
                  Nouvelle vente
                </Button>
              )}
            </Alert>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
