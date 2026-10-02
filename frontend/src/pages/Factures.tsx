import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemText from "@mui/material/ListItemText";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { genererFacture, trouverVente, type Facture, type ModePaiement, type Vente } from "../api/caisse";
import { chercherClients, type Client } from "../api/clients";
import { listerMagasins } from "../api/magasins";
import { formaterTexte, type Monnaie } from "../api/monnaie";

const MODES: { valeur: ModePaiement; libelle: string }[] = [
  { valeur: "especes", libelle: "Espèces" },
  { valeur: "carte", libelle: "Carte bancaire" },
  { valeur: "cheque", libelle: "Chèque" },
];

/**
 * Génération d'une facture, à part de la caisse : on retrouve le ticket, on vérifie qu'il est
 * entièrement payé, on choisit le client et on encaisse le droit de timbre.
 */
export function Factures() {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [numero, setNumero] = useState("");
  const [vente, setVente] = useState<Vente | null>(null);
  const [recherche, setRecherche] = useState("");
  const [client, setClient] = useState<Client | null>(null);
  const [mode, setMode] = useState<ModePaiement>("especes");
  const [facture, setFacture] = useState<Facture | null>(null);

  const pays = magasins.data?.find((m) => vente?.numero.startsWith(`${m.code}-`))?.pays;
  const monnaie: Monnaie = { devise: vente?.devise ?? "TND", decimales: pays?.decimales ?? 3 };
  const timbre = Number(pays?.timbre_fiscal ?? "0");
  const solde = vente !== null && Number(vente.reste_a_payer) === 0;

  const recherchee = useMutation({
    mutationFn: () => trouverVente(numero.trim()),
    onSuccess: (trouvee) => {
      setVente(trouvee);
      setClient(null);
      setFacture(null);
    },
  });
  const clients = useQuery({
    queryKey: ["clients", recherche],
    queryFn: () => chercherClients(recherche),
    enabled: Boolean(vente) && !vente?.client && !client && recherche.trim().length >= 2,
  });
  const generation = useMutation({
    mutationFn: () =>
      genererFacture({
        vente: vente!.id,
        client: client?.id ?? vente!.client?.id,
        mode_paiement_timbre: timbre > 0 ? mode : undefined,
      }),
    onSuccess: setFacture,
  });

  function chercher(e: FormEvent) {
    e.preventDefault();
    recherchee.mutate();
  }

  const nomClient = client ? `${client.nom.toUpperCase()} ${client.prenom}` : vente?.client?.nom;

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Factures
          </Typography>
          <Stack component="form" direction="row" spacing={2} onSubmit={chercher}>
            <TextField
              label="N° de ticket"
              value={numero}
              onChange={(e) => setNumero(e.target.value)}
              sx={{ flexGrow: 1 }}
            />
            <Button type="submit" disabled={!numero.trim() || recherchee.isPending}>
              Rechercher
            </Button>
          </Stack>
          {recherchee.isError && <Alert severity="error">{recherchee.error.message}</Alert>}
          {recherchee.isSuccess && !vente && <Alert severity="warning">Ticket introuvable.</Alert>}

          {vente && (
            <>
              <Typography>
                Ticket {vente.numero} : {formaterTexte(vente.total_ttc, monnaie)}
              </Typography>
              {vente.facture && <Alert severity="info">Déjà facturé : facture {vente.facture}.</Alert>}
              {!vente.facture && !solde && (
                <Alert severity="warning">
                  Commande pas entièrement payée : reste {formaterTexte(vente.reste_a_payer, monnaie)}. La
                  facture sera possible une fois soldée.
                </Alert>
              )}
            </>
          )}

          {vente && solde && !vente.facture && !facture && (
            <>
              {nomClient ? (
                <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                  <Typography>Au nom de {nomClient}</Typography>
                  {client && (
                    <Button size="small" onClick={() => setClient(null)}>
                      Changer
                    </Button>
                  )}
                </Stack>
              ) : (
                <>
                  <TextField
                    label="Client de la facture"
                    helperText="Nom, téléphone ou e-mail"
                    value={recherche}
                    onChange={(e) => setRecherche(e.target.value)}
                  />
                  <List dense>
                    {clients.data?.map((c) => (
                      <ListItemButton key={c.id} onClick={() => setClient(c)}>
                        <ListItemText primary={`${c.nom.toUpperCase()} ${c.prenom}`} secondary={c.telephone} />
                      </ListItemButton>
                    ))}
                  </List>
                </>
              )}
              {timbre > 0 && (
                <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
                  <Typography sx={{ flexGrow: 1 }}>
                    Timbre fiscal à encaisser : {formaterTexte(pays!.timbre_fiscal, monnaie)}
                  </Typography>
                  <TextField
                    select
                    size="small"
                    label="Paiement du timbre"
                    value={mode}
                    onChange={(e) => setMode(e.target.value as ModePaiement)}
                  >
                    {MODES.map((m) => (
                      <MenuItem key={m.valeur} value={m.valeur}>
                        {m.libelle}
                      </MenuItem>
                    ))}
                  </TextField>
                </Stack>
              )}
              {generation.isError && <Alert severity="error">{generation.error.message}</Alert>}
              <Button
                variant="contained"
                disabled={!nomClient || generation.isPending}
                onClick={() => generation.mutate()}
              >
                Générer la facture
              </Button>
            </>
          )}

          {facture && (
            <Alert severity="success">
              Facture {facture.numero} au nom de {facture.client.nom} : {formaterTexte(facture.total_ttc, monnaie)}
              {Number(facture.timbre_fiscal) > 0 && ` + timbre ${formaterTexte(facture.timbre_fiscal, monnaie)}`} ={" "}
              {formaterTexte(facture.net_a_payer, monnaie)}.
            </Alert>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
