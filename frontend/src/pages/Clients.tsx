import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Checkbox from "@mui/material/Checkbox";
import Divider from "@mui/material/Divider";
import FormControlLabel from "@mui/material/FormControlLabel";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemText from "@mui/material/ListItemText";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  chercherClients,
  creerClient,
  formaterOeil,
  listerPrescriptions,
  saisirPrescription,
  type Client,
  type MesureOeil,
} from "../api/clients";
import { listerMagasins } from "../api/magasins";

type Droits = { creerClient: boolean; voirOrdonnances: boolean; saisirOrdonnance: boolean };

function ChoixMagasin({ valeur, onChange }: { valeur: string; onChange: (id: string) => void }) {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const premier = magasins.data?.[0]?.id;
  // Premier magasin du périmètre choisi d'office : la plupart des comptes n'en ont qu'un.
  useEffect(() => {
    if (!valeur && premier) onChange(premier);
  }, [valeur, premier, onChange]);
  const choisi = valeur || premier || "";
  return (
    <TextField select size="small" label="Magasin" value={choisi} onChange={(e) => onChange(e.target.value)}>
      {magasins.data?.map((m) => (
        <MenuItem key={m.id} value={m.id}>
          {m.nom}
        </MenuItem>
      ))}
    </TextField>
  );
}

function NouveauClient({ onCree }: { onCree: (client: Client) => void }) {
  const [saisie, setSaisie] = useState({ nom: "", prenom: "", telephone: "", email: "", magasin_origine: "" });
  const [relances, setRelances] = useState(false);
  const creation = useMutation({
    mutationFn: () => creerClient({ ...saisie, accepte_relances: relances }),
    onSuccess: onCree,
  });
  const choisirMagasin = useCallback(
    (id: string) => setSaisie((s) => ({ ...s, magasin_origine: id })),
    [],
  );
  const champ = (nom: keyof typeof saisie, label: string) => (
    <TextField
      size="small"
      label={label}
      value={saisie[nom]}
      onChange={(e) => setSaisie({ ...saisie, [nom]: e.target.value })}
    />
  );

  function envoyer(e: FormEvent) {
    e.preventDefault();
    creation.mutate();
  }

  return (
    <Stack component="form" spacing={2} onSubmit={envoyer} aria-label="Nouveau client">
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        {champ("nom", "Nom")}
        {champ("prenom", "Prénom")}
      </Stack>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        {champ("telephone", "Téléphone")}
        {champ("email", "E-mail")}
        <ChoixMagasin
          valeur={saisie.magasin_origine}
          onChange={choisirMagasin}
        />
      </Stack>
      <FormControlLabel
        control={<Checkbox checked={relances} onChange={(e) => setRelances(e.target.checked)} />}
        label="Accepte les relances par e-mail ou SMS"
      />
      {creation.isError && <Alert severity="error">{creation.error.message}</Alert>}
      <Button type="submit" variant="contained" disabled={creation.isPending || !saisie.nom || !saisie.prenom}>
        Créer le client
      </Button>
    </Stack>
  );
}

const OEIL_VIDE = { sphere: "", cylindre: "", axe: "", addition: "" };
type SaisieOeil = typeof OEIL_VIDE;

function versMesure(oeil: SaisieOeil): MesureOeil {
  return {
    sphere: oeil.sphere,
    cylindre: oeil.cylindre || undefined,
    axe: oeil.axe ? Number(oeil.axe) : null,
    addition: oeil.addition || null,
  };
}

function NouvelleOrdonnance({ client, onSaisie }: { client: Client; onSaisie: () => void }) {
  const [magasin, setMagasin] = useState("");
  const [type, setType] = useState<"lunettes" | "lentilles">("lunettes");
  const [date, setDate] = useState("");
  const [prescripteur, setPrescripteur] = useState("");
  const [identifiant, setIdentifiant] = useState("");
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  // Le pays du magasin dit quel identifiant porte le prescripteur (Ordre des médecins, RPPS…).
  const libelleIdentifiant =
    magasins.data?.find((m) => m.id === magasin)?.pays.libelle_identifiant_prescripteur ??
    "Identifiant du prescripteur";
  const [yeux, setYeux] = useState({ od: OEIL_VIDE, og: OEIL_VIDE });
  const [ecart, setEcart] = useState("");
  const saisie = useMutation({
    mutationFn: () =>
      saisirPrescription({
        client: client.id,
        magasin_saisie: magasin,
        type,
        date_prescription: date,
        prescripteur,
        prescripteur_identifiant: identifiant,
        mesures: { od: versMesure(yeux.od), og: versMesure(yeux.og), ecart_pupillaire: ecart || null },
      }),
    onSuccess: onSaisie,
  });

  const oeil = (cote: "od" | "og", libelle: string) => (
    <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
      <Typography sx={{ width: 32 }}>{libelle}</Typography>
      {(["sphere", "cylindre", "axe", "addition"] as const).map((mesure) => (
        <TextField
          key={mesure}
          size="small"
          label={{ sphere: "Sphère", cylindre: "Cylindre", axe: "Axe", addition: "Addition" }[mesure]}
          value={yeux[cote][mesure]}
          onChange={(e) => setYeux({ ...yeux, [cote]: { ...yeux[cote], [mesure]: e.target.value } })}
          slotProps={{ htmlInput: { inputMode: "decimal", "aria-label": `${mesure} ${libelle}` } }}
        />
      ))}
    </Stack>
  );

  function envoyer(e: FormEvent) {
    e.preventDefault();
    saisie.mutate();
  }

  return (
    <Stack component="form" spacing={2} onSubmit={envoyer} aria-label="Nouvelle ordonnance">
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <ChoixMagasin valeur={magasin} onChange={setMagasin} />
        <TextField select size="small" label="Type" value={type} onChange={(e) => setType(e.target.value as typeof type)}>
          <MenuItem value="lunettes">Lunettes</MenuItem>
          <MenuItem value="lentilles">Lentilles</MenuItem>
        </TextField>
        <TextField
          size="small"
          type="date"
          label="Date de l'ordonnance"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
        />
      </Stack>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <TextField size="small" label="Prescripteur" value={prescripteur} onChange={(e) => setPrescripteur(e.target.value)} />
        <TextField
          size="small"
          label={libelleIdentifiant}
          value={identifiant}
          onChange={(e) => setIdentifiant(e.target.value)}
        />
        <TextField size="small" label="Écart pupillaire (mm)" value={ecart} onChange={(e) => setEcart(e.target.value)} />
      </Stack>
      {oeil("od", "OD")}
      {oeil("og", "OG")}
      {saisie.isError && <Alert severity="error">{saisie.error.message}</Alert>}
      <Button
        type="submit"
        variant="contained"
        disabled={saisie.isPending || !date || !prescripteur || !yeux.od.sphere || !yeux.og.sphere}
      >
        Enregistrer l'ordonnance
      </Button>
    </Stack>
  );
}

function Ordonnances({ client, peutSaisir }: { client: Client; peutSaisir: boolean }) {
  const queryClient = useQueryClient();
  const [saisie, setSaisie] = useState(false);
  const ordonnances = useQuery({
    queryKey: ["prescriptions", client.id],
    queryFn: () => listerPrescriptions(client.id),
  });

  return (
    <Stack spacing={1}>
      <Typography variant="subtitle1">Ordonnances</Typography>
      {ordonnances.isError && <Alert severity="error">{ordonnances.error.message}</Alert>}
      {ordonnances.data?.length === 0 && <Typography color="text.secondary">Aucune ordonnance.</Typography>}
      <List dense>
        {ordonnances.data?.map((p) => (
          <ListItemText
            key={p.id}
            primary={`OD ${formaterOeil(p.mesures.od)} · OG ${formaterOeil(p.mesures.og)}`}
            secondary={`${p.type === "lunettes" ? "Lunettes" : "Lentilles"} · ${new Date(p.date_prescription).toLocaleDateString("fr-FR")} · ${p.prescripteur}`}
          />
        ))}
      </List>
      {peutSaisir && !saisie && <Button onClick={() => setSaisie(true)}>Nouvelle ordonnance</Button>}
      {saisie && (
        <NouvelleOrdonnance
          client={client}
          onSaisie={() => {
            setSaisie(false);
            void queryClient.invalidateQueries({ queryKey: ["prescriptions", client.id] });
          }}
        />
      )}
    </Stack>
  );
}

export function Clients({ droits }: { droits: Droits }) {
  const [recherche, setRecherche] = useState("");
  const [choisi, setChoisi] = useState<Client | null>(null);
  const [creation, setCreation] = useState(false);
  const clients = useQuery({
    queryKey: ["clients", recherche],
    queryFn: () => chercherClients(recherche),
    enabled: recherche.trim().length >= 2,
  });

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Clients
          </Typography>
          <Stack direction="row" spacing={2}>
            <TextField
              label="Rechercher un client"
              helperText="Nom, prénom, téléphone ou e-mail"
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
              sx={{ flexGrow: 1 }}
            />
            {droits.creerClient && (
              <Button onClick={() => setCreation(!creation)} sx={{ alignSelf: "flex-start", mt: 1 }}>
                Nouveau client
              </Button>
            )}
          </Stack>

          {creation && (
            <NouveauClient
              onCree={(client) => {
                setCreation(false);
                setChoisi(client);
              }}
            />
          )}

          {clients.isError && <Alert severity="error">{clients.error.message}</Alert>}
          {clients.data?.length === 0 && <Typography color="text.secondary">Aucun client trouvé.</Typography>}
          <List dense>
            {clients.data?.map((client) => (
              <ListItemButton key={client.id} selected={choisi?.id === client.id} onClick={() => setChoisi(client)}>
                <ListItemText
                  primary={`${client.nom.toUpperCase()} ${client.prenom}`}
                  secondary={[client.telephone, client.email, client.ville].filter(Boolean).join(" · ")}
                />
              </ListItemButton>
            ))}
          </List>

          {choisi && (
            <>
              <Divider />
              <Typography variant="h6" component="h3">
                {choisi.nom.toUpperCase()} {choisi.prenom}
              </Typography>
              <Typography color="text.secondary">
                {[choisi.telephone, choisi.email].filter(Boolean).join(" · ") || "Pas de coordonnées"}
              </Typography>
              {droits.voirOrdonnances && <Ordonnances client={choisi} peutSaisir={droits.saisirOrdonnance} />}
            </>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
