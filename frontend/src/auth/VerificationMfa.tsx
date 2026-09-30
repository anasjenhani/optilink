import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { verifierCode } from "../api/auth";
import { ChampCode } from "./ChampCode";
import { Formulaire } from "./Formulaire";

export function VerificationMfa() {
  const queryClient = useQueryClient();
  const [code, setCode] = useState("");
  const verification = useMutation({
    mutationFn: () => verifierCode(code),
    onSuccess: (session) => queryClient.setQueryData(["session"], session),
  });

  return (
    <Formulaire
      titre="Double authentification"
      bouton="Valider"
      envoi={verification.isPending}
      erreur={verification.error?.message}
      onSubmit={() => verification.mutate()}
    >
      <ChampCode
        valeur={code}
        onChange={setCode}
        aide="Code à 6 chiffres de votre application d'authentification, ou un code de secours."
      />
    </Formulaire>
  );
}
