import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import ButtonBase from "@mui/material/ButtonBase";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Step from "@mui/material/Step";
import StepButton from "@mui/material/StepButton";
import Stepper from "@mui/material/Stepper";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { TYPES_VENTE, type TypeVente } from "../api/caisse";
import { nomClient, type Client } from "../api/clients";
import { listerMagasins } from "../api/magasins";
import { Caisse } from "./Caisse";
import { FicheClient } from "./Clients";
import { RechercheClients } from "./RechercheClients";

const ETAPES = ["Client", "Type de vente", "Saisie de la vente"];

/** Étape 1 : retrouver le client dans le tableau « Recherche Clients », ou le créer. */
function ChoixClient({
  creer,
  onChoisi,
}: {
  creer: boolean;
  onChoisi: (client: Client | null) => void;
}) {
  const [nouveau, setNouveau] = useState(false);

  if (nouveau) {
    return (
      <Stack spacing={2}>
        <Typography variant="subtitle1">Nouveau client</Typography>
        <FicheClient onEnregistre={onChoisi} />
        <Button onClick={() => setNouveau(false)} sx={{ alignSelf: "flex-start" }}>
          Revenir à la recherche
        </Button>
      </Stack>
    );
  }
  return (
    <RechercheClients
      onChoisi={onChoisi}
      onNouveau={creer ? () => setNouveau(true) : undefined}
      onPassage={() => onChoisi(null)}
    />
  );
}

/** Étape 2 : ce que l'on vend ; d'autres types restent ajoutables pendant la saisie. */
function ChoixType({ onChoisi }: { onChoisi: (type: TypeVente) => void }) {
  return (
    <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))" }}>
      {TYPES_VENTE.map((t) => (
        <ButtonBase
          key={t.valeur}
          onClick={() => onChoisi(t.valeur)}
          sx={{
            p: 3,
            display: "block",
            textAlign: "center",
            border: 1,
            borderColor: "grey.400",
            borderRadius: 1,
            background: "linear-gradient(180deg, #fbfbfb 0%, #e6e6e6 100%)",
            "&:hover": { borderColor: "primary.main" },
          }}
        >
          <Typography variant="h6" component="span" sx={{ display: "block" }}>
            {t.libelle}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {t.aide}
          </Typography>
        </ButtonBase>
      ))}
    </Box>
  );
}

/** Vente au comptoir en trois étapes : client, type de vente, puis saisie et encaissement. */
export function VenteComptoir({ creerClient }: { creerClient: boolean }) {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = magasinChoisi || magasins.data?.[0]?.id || "";
  const [etape, setEtape] = useState(0);
  // undefined : pas encore choisi ; null : client de passage.
  const [client, setClient] = useState<Client | null | undefined>(undefined);
  const [typeVente, setTypeVente] = useState<TypeVente | null>(null);
  const [vente, setVente] = useState(0);

  function recommencer() {
    setClient(undefined);
    setTypeVente(null);
    setEtape(0);
    setVente((n) => n + 1);
  }

  return (
    <Card>
      <CardContent>
        <Stack spacing={3}>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ alignItems: { sm: "center" } }}>
            <Typography variant="h6" component="h2" sx={{ flexGrow: 1 }}>
              Vente au comptoir
            </Typography>
            <TextField
              select
              size="small"
              label="Magasin"
              value={magasin}
              onChange={(e) => {
                setMagasin(e.target.value);
                recommencer();
              }}
              sx={{ minWidth: 200 }}
            >
              {magasins.data?.map((m) => (
                <MenuItem key={m.id} value={m.id}>
                  {m.nom}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
          <Stepper nonLinear activeStep={etape}>
            {ETAPES.map((libelle, i) => (
              <Step key={libelle} completed={i < etape}>
                <StepButton onClick={() => setEtape(i)} disabled={i > etape}>
                  {i === 0 && client !== undefined
                    ? `Client : ${client ? nomClient(client) : "de passage"}`
                    : i === 1 && typeVente
                      ? TYPES_VENTE.find((t) => t.valeur === typeVente)?.libelle
                      : libelle}
                </StepButton>
              </Step>
            ))}
          </Stepper>
          {etape === 0 && (
            <ChoixClient
              key={vente}
              creer={creerClient}
              onChoisi={(c) => {
                setClient(c);
                setEtape(1);
              }}
            />
          )}
          {etape === 1 && (
            <ChoixType
              onChoisi={(t) => {
                setTypeVente(t);
                setEtape(2);
              }}
            />
          )}
          {/* La caisse reste montée quand on revient changer de client : le panier est gardé. */}
          {client !== undefined && typeVente && (
            <Box hidden={etape !== 2}>
              <Caisse
                key={`${vente}-${magasin}`}
                parcours={{ client, magasin, typeVente, onTypeVente: setTypeVente, onNouvelleVente: recommencer }}
              />
            </Box>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
