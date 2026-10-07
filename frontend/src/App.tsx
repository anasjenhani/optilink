import AppBar from "@mui/material/AppBar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Container from "@mui/material/Container";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { deconnecter, lireSession, type EtatSession } from "./api/auth";
import { ActivationMfa } from "./auth/ActivationMfa";
import { CodesSecours } from "./auth/CodesSecours";
import { Connexion } from "./auth/Connexion";
import { VerificationMfa } from "./auth/VerificationMfa";
import { Espace } from "./navigation/Espace";
import { Accueil } from "./pages/Accueil";
import logo from "./assets/logo-optilink.png";

function Contenu({ session }: { session: EtatSession }) {
  const queryClient = useQueryClient();
  // Les codes de secours restent affichés jusqu'à confirmation, même si la session a changé.
  const [codesSecours, setCodesSecours] = useState<string[] | null>(null);

  if (codesSecours) {
    return (
      <CodesSecours
        codes={codesSecours}
        onTermine={() => {
          setCodesSecours(null);
          void queryClient.invalidateQueries({ queryKey: ["session"] });
        }}
      />
    );
  }
  if (!session.authentifie) return <Connexion />;
  if (session.mfa === "a_verifier") return <VerificationMfa />;
  if (session.mfa === "a_activer") return <ActivationMfa onConfirmee={setCodesSecours} />;
  return <Espace session={session} />;
}

export function App() {
  const queryClient = useQueryClient();
  const session = useQuery({ queryKey: ["session"], queryFn: lireSession });
  const deconnexion = useMutation({
    mutationFn: deconnecter,
    onSettled: () => queryClient.clear(),
  });

  return (
    <>
      <AppBar
        position="static"
        color="inherit"
        elevation={0}
        sx={{ bgcolor: "#dff3ec", borderBottom: 1, borderColor: "divider" }}
      >
        <Toolbar>
          <Box component="h1" sx={{ m: 0, flexGrow: 1, lineHeight: 0 }}>
            <Box component="img" src={logo} alt="OptiLink" sx={{ height: 44 }} />
          </Box>
          {session.data?.utilisateur && (
            <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
              <Typography>{session.data.utilisateur.nom_complet}</Typography>
              <Button color="inherit" onClick={() => deconnexion.mutate()}>
                Se déconnecter
              </Button>
            </Box>
          )}
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg" sx={{ py: 3 }}>
        {session.isPending && <CircularProgress />}
        {session.isError && <Accueil />}
        {session.data && <Contenu session={session.data} />}
      </Container>
    </>
  );
}
