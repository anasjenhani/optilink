import Alert from "@mui/material/Alert";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";

import { lireSante } from "../api/sante";

function Etat({ libelle, valeur }: { libelle: string; valeur: string }) {
  return (
    <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
      <Typography sx={{ minWidth: 160 }}>{libelle}</Typography>
      <Chip size="small" label={valeur} color={valeur === "ok" ? "success" : "error"} />
    </Stack>
  );
}

export function Accueil() {
  const sante = useQuery({ queryKey: ["sante"], queryFn: lireSante });

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          État de la plateforme
        </Typography>
        {sante.isPending && <CircularProgress size={24} />}
        {sante.isError && <Alert severity="error">{sante.error.message}</Alert>}
        {sante.data && (
          <Stack spacing={1}>
            <Etat libelle="API" valeur={sante.data.statut} />
            <Etat libelle="Base de données" valeur={sante.data.base_de_donnees} />
            <Etat libelle="Cache Redis" valeur={sante.data.cache} />
          </Stack>
        )}
      </CardContent>
    </Card>
  );
}
