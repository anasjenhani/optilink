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
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { listerMagasins } from "../api/magasins";
import { formaterTexte } from "../api/monnaie";
import { changerStatutPec, listerPrisesEnCharge, STATUTS_PEC, type StatutPec } from "../api/prisesEnCharge";

/**
 * Suivi des dossiers de prise en charge (CNAM, assurances, mutuelles) : de la demande au
 * règlement par l'organisme. Une prise en charge refusée redevient à la charge du client.
 */
export function PrisesEnCharge({ modifier }: { modifier: boolean }) {
  const queryClient = useQueryClient();
  const [statut, setStatut] = useState("");
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const decimales = (code: string) => magasins.data?.find((m) => m.code === code)?.pays.decimales ?? 3;
  const liste = useQuery({ queryKey: ["prises-en-charge", statut], queryFn: () => listerPrisesEnCharge(statut) });
  const changement = useMutation({
    mutationFn: ({ id, nouveau }: { id: string; nouveau: StatutPec }) => changerStatutPec(id, nouveau),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["prises-en-charge"] }),
  });

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Prises en charge
          </Typography>
          <TextField
            select
            size="small"
            label="Statut"
            value={statut}
            onChange={(e) => setStatut(e.target.value)}
            sx={{ maxWidth: 260 }}
          >
            <MenuItem value="">Tous</MenuItem>
            {STATUTS_PEC.map((s) => (
              <MenuItem key={s.valeur} value={s.valeur}>
                {s.libelle}
              </MenuItem>
            ))}
          </TextField>
          {liste.isError && <Alert severity="error">{liste.error.message}</Alert>}
          {changement.isError && <Alert severity="error">{changement.error.message}</Alert>}
          {liste.data?.length === 0 && <Typography color="text.secondary">Aucune prise en charge.</Typography>}
          {liste.data && liste.data.length > 0 && (
            <Table size="small" aria-label="Prises en charge">
              <TableHead>
                <TableRow>
                  <TableCell>Date</TableCell>
                  <TableCell>Visite</TableCell>
                  <TableCell>Client</TableCell>
                  <TableCell>Organisme</TableCell>
                  <TableCell>N° dossier</TableCell>
                  <TableCell align="right">Montant</TableCell>
                  <TableCell>Statut</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {liste.data.map((pec) => (
                  <TableRow key={pec.id}>
                    <TableCell>{new Date(pec.cree_le).toLocaleDateString("fr-FR")}</TableCell>
                    <TableCell>{pec.vente_numero}</TableCell>
                    <TableCell>{pec.client ?? "—"}</TableCell>
                    <TableCell>{pec.organisme_nom}</TableCell>
                    <TableCell>{pec.numero_dossier || "—"}</TableCell>
                    <TableCell align="right">{formaterTexte(pec.montant, { devise: pec.devise, decimales: decimales(pec.magasin) })}</TableCell>
                    <TableCell>
                      {modifier ? (
                        <TextField
                          select
                          size="small"
                          label={`Statut ${pec.vente_numero}`}
                          value={pec.statut}
                          disabled={changement.isPending}
                          onChange={(e) => changement.mutate({ id: pec.id, nouveau: e.target.value as StatutPec })}
                          sx={{ minWidth: 200 }}
                        >
                          {STATUTS_PEC.map((s) => (
                            <MenuItem key={s.valeur} value={s.valeur}>
                              {s.libelle}
                            </MenuItem>
                          ))}
                        </TextField>
                      ) : (
                        pec.statut_libelle
                      )}
                    </TableCell>
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
