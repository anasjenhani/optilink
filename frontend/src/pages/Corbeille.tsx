import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { listerCorbeille, restaurerElement, supprimerDefinitivement } from "../api/corbeille";
import { BANDEAU } from "./RechercheClients";

const dateHeure = (iso: string) => new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });

export type DroitsCorbeille = { restaurer: boolean; vider: boolean };

/**
 * Corbeille : ce qui a été supprimé (dans l'application ou dans /admin/) se restaure pendant le
 * délai de grâce, puis s'efface automatiquement. Chacun ne voit que ce qu'il a le droit de créer.
 */
export function Corbeille({ droits }: { droits: DroitsCorbeille }) {
  const queryClient = useQueryClient();
  const [recherche, setRecherche] = useState("");
  const [aEffacer, setAEffacer] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const elements = useQuery({ queryKey: ["corbeille", recherche], queryFn: () => listerCorbeille(recherche) });
  const fini = (texte: string) => {
    setMessage(texte);
    setAEffacer(null);
    void queryClient.invalidateQueries();
  };
  const restauration = useMutation({
    mutationFn: (id: number) => restaurerElement(id),
    onSuccess: (_, id) => fini(`« ${elements.data?.find((e) => e.id === id)?.libelle} » est restauré.`),
  });
  const effacement = useMutation({
    mutationFn: (id: number) => supprimerDefinitivement(id),
    onSuccess: () => fini("Élément supprimé définitivement."),
  });
  const erreur = restauration.error ?? effacement.error;
  const jours = elements.data?.[0]?.jours_de_grace;

  return (
    <Stack spacing={1.5}>
      <Box sx={{ px: 3, py: 1, borderRadius: 1, background: BANDEAU }}>
        <Typography variant="h5" component="h3" sx={{ color: "common.white", fontWeight: 500 }}>
          Corbeille
        </Typography>
      </Box>
      <Typography color="text.secondary">
        Un élément supprimé par erreur se restaure ici, à l'identique
        {jours ? `, pendant ${jours} jours` : " pendant le délai de grâce"}. Ensuite, il est effacé automatiquement.
      </Typography>
      <TextField
        size="small"
        label="Rechercher"
        value={recherche}
        onChange={(e) => setRecherche(e.target.value)}
        sx={{ maxWidth: 360 }}
      />
      {message && !erreur && <Alert severity="success">{message}</Alert>}
      {erreur && <Alert severity="error">{erreur.message}</Alert>}
      {elements.isError && <Alert severity="error">{elements.error.message}</Alert>}
      {elements.data?.length === 0 && <Typography color="text.secondary">La corbeille est vide.</Typography>}
      {Boolean(elements.data?.length) && (
        <TableContainer>
          <Table size="small" aria-label="Éléments de la corbeille">
            <TableHead>
              <TableRow>
                {["Supprimé le", "Type", "Élément", "Supprimé par", "Effacé le", ""].map((t) => (
                  <TableCell key={t}>{t}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {elements.data?.map((e) => (
                <TableRow key={e.id}>
                  <TableCell>{dateHeure(e.supprime_le)}</TableCell>
                  <TableCell>{e.type_libelle}</TableCell>
                  <TableCell>
                    {e.libelle}
                    {e.nombre_objets > 1 && (
                      <Typography variant="body2" color="text.secondary">
                        avec {e.nombre_objets - 1} élément(s) lié(s)
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>{e.supprime_par}</TableCell>
                  <TableCell>{dateHeure(e.expire_le)}</TableCell>
                  <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                    {aEffacer === e.id ? (
                      <>
                        Effacer définitivement ?{" "}
                        <Button
                          size="small"
                          color="error"
                          disabled={effacement.isPending}
                          onClick={() => effacement.mutate(e.id)}
                        >
                          Oui
                        </Button>
                        <Button size="small" onClick={() => setAEffacer(null)}>
                          Non
                        </Button>
                      </>
                    ) : (
                      <>
                        {droits.restaurer && (
                          <Button
                            size="small"
                            variant="contained"
                            disabled={restauration.isPending}
                            onClick={() => restauration.mutate(e.id)}
                            aria-label={`Restaurer ${e.libelle}`}
                          >
                            Restaurer
                          </Button>
                        )}
                        {droits.vider && (
                          <Button
                            size="small"
                            color="error"
                            onClick={() => setAEffacer(e.id)}
                            aria-label={`Effacer ${e.libelle}`}
                          >
                            Effacer
                          </Button>
                        )}
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Stack>
  );
}
