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
  modifierClient,
  saisirPrescription,
  type Client,
  type MesureOeil,
} from "../api/clients";
import { listerMagasins } from "../api/magasins";

type Droits = {
  creerClient: boolean;
  modifierClient: boolean;
  voirOrdonnances: boolean;
  saisirOrdonnance: boolean;
};

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

const FICHE_VIDE = {
  civilite: "" as Client["civilite"],
  nom: "",
  prenom: "",
  date_naissance: "",
  telephone: "",
  telephone_2: "",
  email: "",
  adresse: "",
  code_postal: "",
  ville: "",
  societe: "",
  matricule_fiscal: "",
  magasin_origine: "",
  accepte_relances: false,
};
type SaisieFiche = typeof FICHE_VIDE;

function versFiche(client: Client): SaisieFiche {
  return { ...client, date_naissance: client.date_naissance ?? "" };
}

/** Création d'un client, ou modification de sa fiche quand ``client`` est donné. */
export function FicheClient({ client, onEnregistre }: { client?: Client; onEnregistre: (client: Client) => void }) {
  const [saisie, setSaisie] = useState<SaisieFiche>(client ? versFiche(client) : FICHE_VIDE);
  const [professionnel, setProfessionnel] = useState(Boolean(client?.societe || client?.matricule_fiscal));
  const enregistrement = useMutation({
    mutationFn: () => {
      const fiche = {
        ...saisie,
        date_naissance: saisie.date_naissance || null,
        societe: professionnel ? saisie.societe : "",
        matricule_fiscal: professionnel ? saisie.matricule_fiscal : "",
      };
      if (!client) return creerClient(fiche);
      const { magasin_origine: _, ...modifications } = fiche;
      return modifierClient(client.id, modifications);
    },
    onSuccess: onEnregistre,
  });
  const choisirMagasin = useCallback(
    (id: string) => setSaisie((s) => ({ ...s, magasin_origine: id })),
    [],
  );
  const champ = (nom: Exclude<keyof SaisieFiche, "accepte_relances" | "civilite">, label: string, type = "text") => (
    <TextField
      size="small"
      type={type}
      label={label}
      value={saisie[nom]}
      onChange={(e) => setSaisie({ ...saisie, [nom]: e.target.value })}
      slotProps={type === "date" ? { inputLabel: { shrink: true } } : undefined}
    />
  );

  function envoyer(e: FormEvent) {
    e.preventDefault();
    enregistrement.mutate();
  }

  return (
    <Stack component="form" spacing={2} onSubmit={envoyer} aria-label={client ? "Fiche client" : "Nouveau client"}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <TextField
          select
          size="small"
          label="Civilité"
          value={saisie.civilite}
          onChange={(e) => setSaisie({ ...saisie, civilite: e.target.value as Client["civilite"] })}
          sx={{ minWidth: 100 }}
        >
          <MenuItem value="">–</MenuItem>
          <MenuItem value="mme">Mme</MenuItem>
          <MenuItem value="m">M.</MenuItem>
        </TextField>
        {champ("nom", "Nom")}
        {champ("prenom", "Prénom")}
        {champ("date_naissance", "Date de naissance", "date")}
      </Stack>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        {champ("telephone", "Téléphone 1")}
        {champ("telephone_2", "Téléphone 2")}
        {champ("email", "E-mail")}
      </Stack>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        {champ("adresse", "Adresse")}
        {champ("code_postal", "Code postal")}
        {champ("ville", "Ville")}
        {!client && <ChoixMagasin valeur={saisie.magasin_origine} onChange={choisirMagasin} />}
      </Stack>
      <FormControlLabel
        control={<Checkbox checked={professionnel} onChange={(e) => setProfessionnel(e.target.checked)} />}
        label="Client professionnel (société)"
      />
      {professionnel && (
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
          {champ("societe", "Nom de la société")}
          {champ("matricule_fiscal", "Matricule fiscal")}
        </Stack>
      )}
      <FormControlLabel
        control={
          <Checkbox
            checked={saisie.accepte_relances}
            onChange={(e) => setSaisie({ ...saisie, accepte_relances: e.target.checked })}
          />
        }
        label="Accepte les relances par e-mail ou SMS"
      />
      {enregistrement.isError && <Alert severity="error">{enregistrement.error.message}</Alert>}
      <Button
        type="submit"
        variant="contained"
        disabled={enregistrement.isPending || !saisie.nom || !saisie.prenom}
      >
        {client ? "Enregistrer la fiche" : "Créer le client"}
      </Button>
    </Stack>
  );
}

function Coordonnees({ client }: { client: Client }) {
  const ville = [client.code_postal, client.ville].filter(Boolean).join(" ");
  const lignes = [
    client.societe && `${client.societe}${client.matricule_fiscal ? ` · MF ${client.matricule_fiscal}` : ""}`,
    [client.telephone, client.telephone_2, client.email].filter(Boolean).join(" · "),
    [client.adresse, ville].filter(Boolean).join(", "),
    client.date_naissance && `Né(e) le ${new Date(client.date_naissance).toLocaleDateString("fr-FR")}`,
  ].filter(Boolean);
  if (!lignes.length) return <Typography color="text.secondary">Pas de coordonnées</Typography>;
  return (
    <>
      {lignes.map((ligne) => (
        <Typography key={ligne as string} color="text.secondary">
          {ligne}
        </Typography>
      ))}
    </>
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
  const [edition, setEdition] = useState(false);
  const queryClient = useQueryClient();
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
            <FicheClient
              onEnregistre={(client) => {
                setCreation(false);
                setChoisi(client);
              }}
            />
          )}

          {clients.isError && <Alert severity="error">{clients.error.message}</Alert>}
          {clients.data?.length === 0 && <Typography color="text.secondary">Aucun client trouvé.</Typography>}
          <List dense>
            {clients.data?.map((client) => (
              <ListItemButton
                key={client.id}
                selected={choisi?.id === client.id}
                onClick={() => {
                  setChoisi(client);
                  setEdition(false);
                }}
              >
                <ListItemText
                  primary={`${client.nom.toUpperCase()} ${client.prenom}`}
                  secondary={[client.societe, client.telephone, client.email, client.ville].filter(Boolean).join(" · ")}
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
              {edition ? (
                <FicheClient
                  key={choisi.id}
                  client={choisi}
                  onEnregistre={(client) => {
                    setEdition(false);
                    setChoisi(client);
                    void queryClient.invalidateQueries({ queryKey: ["clients"] });
                  }}
                />
              ) : (
                <>
                  <Coordonnees client={choisi} />
                  {droits.modifierClient && (
                    <Button onClick={() => setEdition(true)} sx={{ alignSelf: "flex-start" }}>
                      Modifier la fiche
                    </Button>
                  )}
                </>
              )}
              {droits.voirOrdonnances && <Ordonnances client={choisi} peutSaisir={droits.saisirOrdonnance} />}
            </>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
