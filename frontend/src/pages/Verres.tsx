import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Checkbox from "@mui/material/Checkbox";
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
  annulerCommandeFournisseur,
  listerCommandesEnvoyees,
  listerFournisseurs,
  listerVerresACommander,
  passerCommande,
  receptionner,
} from "../api/achats";
import { listerMagasins } from "../api/magasins";

const dateCourte = (iso: string) => new Date(iso.length === 10 ? `${iso}T00:00:00` : iso).toLocaleDateString("fr-FR");

/**
 * Verres des commandes clients : commande au fournisseur, puis réception. Une commande client
 * ne se livre qu'une fois ses verres reçus.
 */
export function Verres() {
  const queryClient = useQueryClient();
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = magasinChoisi || magasins.data?.[0]?.id || "";
  const fournisseurs = useQuery({ queryKey: ["fournisseurs"], queryFn: listerFournisseurs });
  const [fournisseurChoisi, setFournisseur] = useState("");
  const fournisseur = fournisseurChoisi || fournisseurs.data?.[0]?.id || "";
  const [reference, setReference] = useState("");
  const [choisies, setChoisies] = useState<Record<number, string>>({});
  const [message, setMessage] = useState("");

  const aCommander = useQuery({
    queryKey: ["verres-a-commander", magasin],
    queryFn: () => listerVerresACommander(magasin),
    enabled: Boolean(magasin),
  });
  const envoyees = useQuery({
    queryKey: ["commandes-fournisseurs", magasin],
    queryFn: () => listerCommandesEnvoyees(magasin),
    enabled: Boolean(magasin),
  });
  const rafraichir = () => {
    void queryClient.invalidateQueries({ queryKey: ["verres-a-commander"] });
    void queryClient.invalidateQueries({ queryKey: ["commandes-fournisseurs"] });
    void queryClient.invalidateQueries({ queryKey: ["commandes"] });
  };

  const commande = useMutation({
    mutationFn: () =>
      passerCommande({
        magasin,
        fournisseur,
        reference_fournisseur: reference,
        lignes: Object.entries(choisies).map(([ligne, details]) => ({
          ligne: Number(ligne),
          ...(details ? { details } : {}),
        })),
      }),
    onSuccess: (passee) => {
      setMessage(`Commande ${passee.numero} envoyée à ${passee.fournisseur}.`);
      setChoisies({});
      setReference("");
      rafraichir();
    },
  });
  const suite = useMutation({
    mutationFn: ({ id, quoi }: { id: string; quoi: "recevoir" | "annuler" }) =>
      quoi === "recevoir"
        ? receptionner(id).then((c) => `Commande ${c.numero} reçue : les commandes clients peuvent être livrées.`)
        : annulerCommandeFournisseur(id).then((c) => `Commande ${c.numero} annulée : les verres sont à recommander.`),
    onSuccess: (texte) => {
      setMessage(texte);
      rafraichir();
    },
  });

  const basculer = (ligne: number) =>
    setChoisies((actuelles) => {
      const suivantes = { ...actuelles };
      if (ligne in suivantes) delete suivantes[ligne];
      else suivantes[ligne] = "";
      return suivantes;
    });

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Verres à commander
          </Typography>
          <TextField
            select
            label="Magasin"
            value={magasin}
            onChange={(e) => {
              setMagasin(e.target.value);
              setChoisies({});
            }}
            sx={{ maxWidth: 260 }}
          >
            {magasins.data?.map((m) => (
              <MenuItem key={m.id} value={m.id}>
                {m.nom}
              </MenuItem>
            ))}
          </TextField>

          {aCommander.data?.length === 0 && <Typography color="text.secondary">Aucun verre à commander.</Typography>}
          {aCommander.data && aCommander.data.length > 0 && (
            <Table size="small" aria-label="Verres à commander">
              <TableHead>
                <TableRow>
                  <TableCell />
                  <TableCell>Commande client</TableCell>
                  <TableCell>Verre</TableCell>
                  <TableCell>Détails pour le fournisseur</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {aCommander.data.map((v) => (
                  <TableRow key={v.ligne}>
                    <TableCell padding="checkbox">
                      <Checkbox
                        checked={v.ligne in choisies}
                        onChange={() => basculer(v.ligne)}
                        slotProps={{ input: { "aria-label": `Commander ${v.commande_client} ${v.libelle}` } }}
                      />
                    </TableCell>
                    <TableCell>
                      {v.commande_client}
                      <Typography variant="body2" color="text.secondary">
                        {v.client?.nom ?? "Sans client"}
                        {v.livraison_prevue_le && ` · prévue le ${dateCourte(v.livraison_prevue_le)}`}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      {v.quantite} × {v.libelle}
                    </TableCell>
                    <TableCell>
                      <TextField
                        size="small"
                        label={`Détails ${v.commande_client}`}
                        placeholder="OD -2.25 add +2.00 / OG -1.75…"
                        disabled={!(v.ligne in choisies)}
                        value={choisies[v.ligne] ?? ""}
                        onChange={(e) => setChoisies((c) => ({ ...c, [v.ligne]: e.target.value }))}
                        fullWidth
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {aCommander.data && aCommander.data.length > 0 && (
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ alignItems: "center" }}>
              <TextField
                select
                label="Fournisseur"
                value={fournisseur}
                onChange={(e) => setFournisseur(e.target.value)}
                sx={{ minWidth: 220 }}
                helperText={fournisseurs.data?.length === 0 ? "Ajouter les fournisseurs dans l'administration." : undefined}
              >
                {fournisseurs.data?.map((f) => (
                  <MenuItem key={f.id} value={f.id}>
                    {f.nom}
                  </MenuItem>
                ))}
              </TextField>
              <TextField label="Réf. fournisseur" value={reference} onChange={(e) => setReference(e.target.value)} />
              <Button
                variant="contained"
                disabled={!fournisseur || Object.keys(choisies).length === 0 || commande.isPending}
                onClick={() => commande.mutate()}
              >
                Commander au fournisseur
              </Button>
            </Stack>
          )}
          {commande.isError && <Alert severity="error">{commande.error.message}</Alert>}
          {suite.isError && <Alert severity="error">{suite.error.message}</Alert>}
          {message && <Alert severity="success">{message}</Alert>}

          {envoyees.data && envoyees.data.length > 0 && (
            <>
              <Typography variant="subtitle1" component="h3">
                En attente de réception
              </Typography>
              <List dense aria-label="Commandes fournisseurs envoyées">
                {envoyees.data.map((c) => (
                  <ListItem
                    key={c.id}
                    disableGutters
                    secondaryAction={
                      <Stack direction="row" spacing={1}>
                        <Button size="small" variant="contained" onClick={() => suite.mutate({ id: c.id, quoi: "recevoir" })}>
                          Réceptionner
                        </Button>
                        <Button size="small" color="error" onClick={() => suite.mutate({ id: c.id, quoi: "annuler" })}>
                          Annuler
                        </Button>
                      </Stack>
                    }
                  >
                    <ListItemText
                      primary={`${c.numero} · ${c.fournisseur}${c.reference_fournisseur ? ` (${c.reference_fournisseur})` : ""}`}
                      secondary={`Envoyée le ${dateCourte(c.cree_le)} · ${c.lignes
                        .map((l) => `${l.commande_client} : ${l.quantite} × ${l.libelle}`)
                        .join(", ")}`}
                    />
                  </ListItem>
                ))}
              </List>
            </>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
