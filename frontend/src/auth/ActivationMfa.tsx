import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Typography from "@mui/material/Typography";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { confirmerActivation, demarrerActivation } from "../api/auth";
import { ChampCode } from "./ChampCode";
import { Formulaire } from "./Formulaire";

/** Première connexion : enregistrer une application d'authentification. */
export function ActivationMfa({ onConfirmee }: { onConfirmee: (codesSecours: string[]) => void }) {
  const [code, setCode] = useState("");
  // Une seule activation par affichage : chaque appel génère une nouvelle clé.
  const activation = useQuery({
    queryKey: ["activation-mfa"],
    queryFn: demarrerActivation,
    staleTime: Infinity,
    gcTime: 0,
    refetchOnWindowFocus: false,
    retry: false,
  });
  const confirmation = useMutation({
    mutationFn: () => confirmerActivation(code),
    onSuccess: (reponse) => onConfirmee(reponse.codes_secours),
  });

  return (
    <Formulaire
      titre="Activer la double authentification"
      bouton="Activer"
      envoi={confirmation.isPending || !activation.data}
      erreur={confirmation.error?.message}
      onSubmit={() => confirmation.mutate()}
    >
      <Typography>
        Scannez ce QR code avec une application d'authentification (Microsoft Authenticator,
        Google Authenticator, FreeOTP…), puis saisissez le code affiché.
      </Typography>
      {activation.isPending && <CircularProgress size={24} />}
      {activation.isError && <Alert severity="error">{activation.error.message}</Alert>}
      {activation.data && (
        <>
          <Box
            component="img"
            alt="QR code d'activation"
            src={`data:image/svg+xml;utf8,${encodeURIComponent(activation.data.qr_svg)}`}
            sx={{ width: 200, height: 200, alignSelf: "center", bgcolor: "common.white" }}
          />
          <Typography variant="body2" color="text.secondary">
            Saisie manuelle : <code>{activation.data.cle}</code>
          </Typography>
        </>
      )}
      <ChampCode valeur={code} onChange={setCode} />
    </Formulaire>
  );
}
