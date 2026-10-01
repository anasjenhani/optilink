import AppBar from "@mui/material/AppBar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Container from "@mui/material/Container";
import Stack from "@mui/material/Stack";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { deconnecter, lireSession, peut, type EtatSession } from "./api/auth";
import { ActivationMfa } from "./auth/ActivationMfa";
import { CodesSecours } from "./auth/CodesSecours";
import { Connexion } from "./auth/Connexion";
import { VerificationMfa } from "./auth/VerificationMfa";
import { Accueil } from "./pages/Accueil";
import { Caisse } from "./pages/Caisse";
import { Clients } from "./pages/Clients";
import { Devis } from "./pages/Devis";
import { Factures } from "./pages/Factures";
import { Magasins } from "./pages/Magasins";

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
  return (
    <Stack spacing={3}>
      {peut(session, "ventes.add_vente") && <Caisse />}
      {peut(session, "ventes.add_devis") && peut(session, "crm.view_client") && (
        <Devis
          droits={{
            remise: peut(session, "ventes.appliquer_remise"),
            voirOrdonnances: peut(session, "optique.view_prescription"),
            changerStatut: peut(session, "ventes.change_devis"),
            encaisser: peut(session, "ventes.add_vente"),
          }}
        />
      )}
      {peut(session, "ventes.add_facture") && <Factures />}
      {peut(session, "crm.view_client") && (
        <Clients
          droits={{
            creerClient: peut(session, "crm.add_client"),
            voirOrdonnances: peut(session, "optique.view_prescription"),
            saisirOrdonnance: peut(session, "optique.add_prescription"),
          }}
        />
      )}
      {peut(session, "reseau.view_magasin") && <Magasins />}
      <Accueil />
    </Stack>
  );
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
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="h1" sx={{ flexGrow: 1 }}>
            OptiLink
          </Typography>
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
      <Container maxWidth="md" sx={{ py: 4 }}>
        {session.isPending && <CircularProgress />}
        {session.isError && <Accueil />}
        {session.data && <Contenu session={session.data} />}
      </Container>
    </>
  );
}
