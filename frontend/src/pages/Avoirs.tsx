import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Checkbox from "@mui/material/Checkbox";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { emettreAvoir, type Avoir } from "../api/avoirs";
import { trouverVente, type ModePaiement, type Vente } from "../api/caisse";
import { listerMagasins } from "../api/magasins";
import { formaterTexte, type Monnaie } from "../api/monnaie";

const MODES: { valeur: ModePaiement; libelle: string }[] = [
  { valeur: "especes", libelle: "Espèces" },
  { valeur: "carte", libelle: "Carte bancaire" },
  { valeur: "cheque", libelle: "Chèque" },
];

type Reprise = { quantite: string; enStock: boolean };

/**
 * Avoirs : reprendre des articles d'une vente livrée, ou annuler une vente ou une commande.
 * Le client est remboursé de ce qu'il a versé ; les articles repris reviennent en stock.
 */
export function Avoirs() {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [numero, setNumero] = useState("");
  const [vente, setVente] = useState<Vente | null>(null);
  const [reprises, setReprises] = useState<Record<number, Reprise>>({});
  const [motif, setMotif] = useState("");
  const [mode, setMode] = useState<ModePaiement>("especes");
  const [avoir, setAvoir] = useState<Avoir | null>(null);

  const pays = magasins.data?.find((m) => vente?.numero.startsWith(`${m.code}-`))?.pays;
  const monnaie: Monnaie = { devise: vente?.devise ?? "TND", decimales: pays?.decimales ?? 3 };

  const recherchee = useMutation({
    mutationFn: () => trouverVente(numero.trim()),
    onSuccess: (trouvee) => {
      setVente(trouvee);
      setReprises({});
    },
  });
  const emission = useMutation({
    mutationFn: (annulation: boolean) => {
      const commun = { vente: vente!.id, motif, mode_remboursement: mode };
      if (annulation) return emettreAvoir({ ...commun, annulation: true });
      return emettreAvoir({
        ...commun,
        lignes: Object.entries(reprises)
          .filter(([, r]) => Number(r.quantite) > 0)
          .map(([ligne, r]) => ({ ligne: Number(ligne), quantite: Number(r.quantite), remis_en_stock: r.enStock })),
      });
    },
    onSuccess: (emis) => {
      setAvoir(emis);
      recherchee.mutate();
    },
  });

  function chercher(e: FormEvent) {
    e.preventDefault();
    setAvoir(null);
    recherchee.mutate();
  }

  const reprise = (id: number): Reprise => reprises[id] ?? { quantite: "", enStock: true };
  const modifier = (id: number, changement: Partial<Reprise>) =>
    setReprises((r) => ({ ...r, [id]: { ...reprise(id), ...changement } }));
  const aReprendre = Object.values(reprises).some((r) => Number(r.quantite) > 0);
  const enCommande = vente?.statut === "en_commande";

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Avoirs et annulations
          </Typography>
          <Stack component="form" direction="row" spacing={2} onSubmit={chercher}>
            <TextField
              label="N° de ticket ou de commande"
              value={numero}
              onChange={(e) => setNumero(e.target.value)}
              sx={{ flexGrow: 1 }}
            />
            <Button type="submit" disabled={!numero.trim() || recherchee.isPending}>
              Rechercher
            </Button>
          </Stack>
          {recherchee.isError && <Alert severity="error">{recherchee.error.message}</Alert>}
          {recherchee.isSuccess && !vente && <Alert severity="warning">Ticket introuvable.</Alert>}
          {avoir && (
            <Alert severity="success">
              Avoir {avoir.numero} : {formaterTexte(avoir.total_ttc, monnaie)} repris
              {Number(avoir.montant_rembourse) > 0
                ? `, ${formaterTexte(avoir.montant_rembourse, monnaie)} remboursé au client`
                : ", rien à rembourser"}
              .
            </Alert>
          )}

          {vente && (
            <>
              <Typography>
                {enCommande ? "Commande" : "Ticket"} {vente.numero} : {formaterTexte(vente.total_ttc, monnaie)}
                {vente.facture && ` · facture ${vente.facture}`}
              </Typography>
              {vente.statut === "annulee" && <Alert severity="info">Cette vente est annulée.</Alert>}
              {enCommande && (
                <Alert severity="info">
                  Commande pas encore livrée : elle s'annule en entier, l'acompte est rendu au client.
                </Alert>
              )}
            </>
          )}

          {vente && vente.statut === "livree" && (
            <Table size="small" aria-label="Articles de la vente">
              <TableHead>
                <TableRow>
                  <TableCell>Article</TableCell>
                  <TableCell align="center">Vendu</TableCell>
                  <TableCell align="center">Déjà repris</TableCell>
                  <TableCell>À reprendre</TableCell>
                  <TableCell>Remettre en stock</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {vente.lignes.map((ligne) => {
                  const restante = ligne.quantite - ligne.quantite_reprise;
                  return (
                    <TableRow key={ligne.id}>
                      <TableCell>{ligne.libelle}</TableCell>
                      <TableCell align="center">{ligne.quantite}</TableCell>
                      <TableCell align="center">{ligne.quantite_reprise}</TableCell>
                      <TableCell>
                        <TextField
                          size="small"
                          type="number"
                          label={`Quantité ${ligne.libelle}`}
                          disabled={restante === 0}
                          value={reprise(ligne.id).quantite}
                          onChange={(e) => modifier(ligne.id, { quantite: e.target.value })}
                          slotProps={{ htmlInput: { min: 0, max: restante } }}
                          sx={{ width: 120 }}
                        />
                      </TableCell>
                      <TableCell>
                        <Checkbox
                          checked={reprise(ligne.id).enStock}
                          disabled={restante === 0}
                          onChange={(e) => modifier(ligne.id, { enStock: e.target.checked })}
                          slotProps={{ input: { "aria-label": `Remettre en stock ${ligne.libelle}` } }}
                        />
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}

          {vente && vente.statut !== "annulee" && (
            <>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                <TextField
                  label="Motif"
                  value={motif}
                  onChange={(e) => setMotif(e.target.value)}
                  sx={{ flexGrow: 1 }}
                />
                <TextField
                  select
                  label="Remboursement"
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
              {emission.isError && <Alert severity="error">{emission.error.message}</Alert>}
              <Stack direction="row" spacing={2}>
                {!enCommande && (
                  <Button
                    variant="contained"
                    disabled={!aReprendre || !motif.trim() || emission.isPending}
                    onClick={() => emission.mutate(false)}
                  >
                    Émettre l'avoir
                  </Button>
                )}
                <Button
                  color="error"
                  variant={enCommande ? "contained" : "outlined"}
                  disabled={!motif.trim() || emission.isPending}
                  onClick={() => emission.mutate(true)}
                >
                  {enCommande ? "Annuler la commande" : "Annuler toute la vente"}
                </Button>
              </Stack>
            </>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
