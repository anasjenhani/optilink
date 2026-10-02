import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
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
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { listerCommandes, livrerCommande, reglerCommande, type ModePaiement, type Vente } from "../api/caisse";
import { listerMagasins } from "../api/magasins";
import { formaterTexte, type Monnaie } from "../api/monnaie";

const MODES: { valeur: ModePaiement; libelle: string }[] = [
  { valeur: "especes", libelle: "Espèces" },
  { valeur: "carte", libelle: "Carte bancaire" },
  { valeur: "cheque", libelle: "Chèque" },
];

const dateCourte = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString("fr-FR");

/**
 * Commandes en cours du magasin : règlements successifs, puis livraison contre le solde.
 */
export function Commandes() {
  const queryClient = useQueryClient();
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = magasinChoisi || magasins.data?.[0]?.id || "";
  const pays = magasins.data?.find((m) => m.id === magasin)?.pays;
  const [mode, setMode] = useState<ModePaiement>("especes");
  const [montants, setMontants] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [peniche, setPeniche] = useState("");

  const commandes = useQuery({
    queryKey: ["commandes", magasin],
    queryFn: () => listerCommandes(magasin),
    enabled: Boolean(magasin),
  });
  const monnaie = (vente: Vente): Monnaie => ({ devise: vente.devise, decimales: pays?.decimales ?? 3 });

  const action = useMutation({
    mutationFn: ({ vente, quoi }: { vente: Vente; quoi: "regler" | "livrer" }) => {
      if (quoi === "regler") {
        return reglerCommande(vente.id, { mode, montant: montants[vente.id] }).then(
          (v) => `Règlement enregistré sur ${v.numero} : reste ${formaterTexte(v.reste_a_payer, monnaie(v))}.`,
        );
      }
      const solde = Number(vente.reste_a_payer) > 0 ? { mode, montant: vente.reste_a_payer } : null;
      return livrerCommande(vente.id, solde).then(
        (v) =>
          `Commande ${v.numero} livrée${solde ? `, solde de ${formaterTexte(solde.montant, monnaie(v))} encaissé` : ""}.`,
      );
    },
    onSuccess: (texte) => {
      setMessage(texte);
      setMontants({});
      void queryClient.invalidateQueries({ queryKey: ["commandes"] });
    },
  });

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Commandes en cours
          </Typography>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField
              select
              label="Magasin"
              value={magasin}
              onChange={(e) => setMagasin(e.target.value)}
              sx={{ minWidth: 200 }}
            >
              {magasins.data?.map((m) => (
                <MenuItem key={m.id} value={m.id}>
                  {m.nom}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label="Paiement"
              value={mode}
              onChange={(e) => setMode(e.target.value as ModePaiement)}
              sx={{ minWidth: 200 }}
            >
              {MODES.map((m) => (
                <MenuItem key={m.valeur} value={m.valeur}>
                  {m.libelle}
                </MenuItem>
              ))}
            </TextField>
          </Stack>

          <TextField
            size="small"
            type="number"
            label="Chercher par péniche"
            value={peniche}
            onChange={(e) => setPeniche(e.target.value)}
            sx={{ maxWidth: 220 }}
          />
          {commandes.isError && <Alert severity="error">{commandes.error.message}</Alert>}
          {commandes.data?.length === 0 && <Typography color="text.secondary">Aucune commande en cours.</Typography>}
          {commandes.data && commandes.data.length > 0 && (
            <Table size="small" aria-label="Commandes en cours">
              <TableHead>
                <TableRow>
                  <TableCell>Péniche</TableCell>
                  <TableCell>Commande</TableCell>
                  <TableCell>Client</TableCell>
                  <TableCell align="right">Reste à payer</TableCell>
                  <TableCell>Règlement</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {commandes.data
                  .filter((vente) => !peniche || vente.peniche === Number(peniche))
                  .map((vente) => (
                    <TableRow key={vente.id}>
                      <TableCell>{vente.peniche ?? "—"}</TableCell>
                      <TableCell>
                        {vente.numero}
                        {vente.livraison_prevue_le && (
                          <Typography variant="body2" color="text.secondary">
                            Prévue le {dateCourte(vente.livraison_prevue_le)}
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>{vente.client?.nom ?? "—"}</TableCell>
                      <TableCell align="right">
                        {formaterTexte(vente.reste_a_payer, monnaie(vente))}
                        <Typography variant="body2" color="text.secondary">
                          sur {formaterTexte(vente.total_ttc, monnaie(vente))}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {Number(vente.reste_a_payer) > 0 && (
                          <Stack direction="row" spacing={1}>
                            <TextField
                              size="small"
                              type="number"
                              label={`Montant ${vente.numero}`}
                              value={montants[vente.id] ?? ""}
                              onChange={(e) => setMontants((m) => ({ ...m, [vente.id]: e.target.value }))}
                              sx={{ width: 140 }}
                            />
                            <Button
                              size="small"
                              disabled={!Number(montants[vente.id]) || action.isPending}
                              onClick={() => action.mutate({ vente, quoi: "regler" })}
                            >
                              Encaisser
                            </Button>
                          </Stack>
                        )}
                      </TableCell>
                      <TableCell>
                        {vente.verres && vente.verres !== "recus" && (
                          <Typography variant="body2" color="warning.main">
                            {vente.verres === "a_commander" ? "Verres à commander" : "Verres en attente du fournisseur"}
                          </Typography>
                        )}
                        <Button
                          variant="contained"
                          size="small"
                          disabled={action.isPending || (Boolean(vente.verres) && vente.verres !== "recus")}
                          onClick={() => action.mutate({ vente, quoi: "livrer" })}
                        >
                          {Number(vente.reste_a_payer) > 0 ? "Encaisser le solde et livrer" : "Livrer"}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
          )}
          {action.isError && <Alert severity="error">{action.error.message}</Alert>}
          {message && <Alert severity="success">{message}</Alert>}
        </Stack>
      </CardContent>
    </Card>
  );
}
