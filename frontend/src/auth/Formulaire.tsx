import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import type { FormEvent, ReactNode } from "react";

/** Carte centrée commune aux écrans de connexion. */
export function Formulaire(props: {
  titre: string;
  erreur?: string;
  envoi: boolean;
  bouton: string;
  onSubmit: () => void;
  children: ReactNode;
}) {
  function soumettre(evenement: FormEvent) {
    evenement.preventDefault();
    props.onSubmit();
  }

  return (
    <Card sx={{ maxWidth: 440, mx: "auto" }}>
      <CardContent>
        <Stack component="form" spacing={2} onSubmit={soumettre} noValidate>
          <Typography variant="h6" component="h2">
            {props.titre}
          </Typography>
          {props.children}
          {props.erreur && <Alert severity="error">{props.erreur}</Alert>}
          <Button type="submit" variant="contained" disabled={props.envoi}>
            {props.bouton}
          </Button>
        </Stack>
      </CardContent>
    </Card>
  );
}
