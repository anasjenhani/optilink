import TextField from "@mui/material/TextField";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { connecter } from "../api/auth";
import { Formulaire } from "./Formulaire";

export function Connexion() {
  const queryClient = useQueryClient();
  const [identifiant, setIdentifiant] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const connexion = useMutation({
    mutationFn: () => connecter(identifiant, motDePasse),
    onSuccess: (session) => queryClient.setQueryData(["session"], session),
  });

  return (
    <Formulaire
      titre="Connexion"
      bouton="Se connecter"
      envoi={connexion.isPending}
      erreur={connexion.error?.message}
      onSubmit={() => connexion.mutate()}
    >
      <TextField
        label="Identifiant"
        autoComplete="username"
        value={identifiant}
        onChange={(e) => setIdentifiant(e.target.value)}
        autoFocus
        required
      />
      <TextField
        label="Mot de passe"
        type="password"
        autoComplete="current-password"
        value={motDePasse}
        onChange={(e) => setMotDePasse(e.target.value)}
        required
      />
    </Formulaire>
  );
}
