import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";

import { listerAlertes, type Gravite } from "../api/pilotage";

const GRAVITES: Record<Gravite, { libelle: string; couleur: "error" | "warning" | "info" }> = {
  haute: { libelle: "Urgent", couleur: "error" },
  moyenne: { libelle: "À surveiller", couleur: "warning" },
  info: { libelle: "À traiter", couleur: "info" },
};

/** Ce qui attend une action aujourd'hui, avec un lien vers l'écran où la faire. */
export function Alertes() {
  const alertes = useQuery({ queryKey: ["alertes"], queryFn: listerAlertes });

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Alertes
          </Typography>
          {alertes.isPending && <CircularProgress size={24} />}
          {alertes.isError && <Alert severity="error">{alertes.error.message}</Alert>}
          {alertes.data?.length === 0 && <Alert severity="success">Aucune alerte : tout est à jour.</Alert>}
          {alertes.data?.map((a) => (
            <Card key={`${a.code}-${a.magasin}`} variant="outlined">
              <CardContent>
                <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ alignItems: { sm: "center" } }}>
                  <Chip
                    label={GRAVITES[a.gravite].libelle}
                    color={GRAVITES[a.gravite].couleur}
                    size="small"
                    sx={{ minWidth: 110 }}
                  />
                  <Stack sx={{ flexGrow: 1 }}>
                    <Typography sx={{ fontWeight: 600 }}>
                      {a.titre}
                      {a.magasin && ` · ${a.magasin}`}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {a.detail}
                    </Typography>
                  </Stack>
                  <Button onClick={() => (window.location.hash = `/${a.module}/${a.ecran}`)}>Traiter</Button>
                </Stack>
              </CardContent>
            </Card>
          ))}
        </Stack>
      </CardContent>
    </Card>
  );
}
