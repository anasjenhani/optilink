import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import FormControlLabel from "@mui/material/FormControlLabel";
import MenuItem from "@mui/material/MenuItem";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { listerMagasins } from "../api/magasins";
import { enUnites, formater, type Monnaie } from "../api/monnaie";
import {
  annulerOperation,
  creerCompte,
  creerOperation,
  deposer,
  effectuerOperation,
  listerARemettre,
  listerComptes,
  listerOperations,
  rapprocherOperation,
  type ARemettre,
  type Compte,
  type Operation,
  type StatutOperation,
  type TypeCompte,
  type TypeDepot,
} from "../api/tresorerie";

/** Nombre de décimales d'une devise (3 pour le dinar, 2 pour l'euro). */
export const monnaieDe = (devise: string): Monnaie => ({
  devise,
  decimales: new Intl.NumberFormat("fr-FR", { style: "currency", currency: devise }).resolvedOptions()
    .maximumFractionDigits ?? 2,
});

const montant = (valeur: string | null, devise = "TND") => {
  if (valeur === null) return "—";
  const monnaie = monnaieDe(devise);
  return formater(enUnites(valeur, monnaie.decimales), monnaie);
};

const jour = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("fr-FR") : "");
const aujourdhui = () => new Date().toISOString().slice(0, 10);

const DEPOTS: { valeur: TypeDepot; libelle: string; champ: "especes" | "cheques" | "cartes" }[] = [
  { valeur: "depot_especes", libelle: "Espèces", champ: "especes" },
  { valeur: "depot_cheques", libelle: "Chèques", champ: "cheques" },
  { valeur: "encaissement_cartes", libelle: "Cartes", champ: "cartes" },
];

const TYPES_COMPTE: { valeur: TypeCompte; libelle: string }[] = [
  { valeur: "banque", libelle: "Compte bancaire" },
  { valeur: "coffre", libelle: "Coffre d'un magasin" },
  { valeur: "caisse_centrale", libelle: "Caisse centrale" },
];

const STATUTS: Record<StatutOperation, { libelle: string; couleur: "default" | "info" | "success" }> = {
  prevue: { libelle: "Prévue", couleur: "default" },
  effectuee: { libelle: "Effectuée", couleur: "info" },
  rapprochee: { libelle: "Rapprochée", couleur: "success" },
};

function invalider(queryClient: ReturnType<typeof useQueryClient>) {
  for (const cle of ["a-remettre", "operations", "comptes-tresorerie", "clotures", "situation-caisse"]) {
    void queryClient.invalidateQueries({ queryKey: [cle] });
  }
}

/** Argent des clôtures validées à déposer au coffre ou à la banque, et prévisions de versement. */
export function Versements() {
  const queryClient = useQueryClient();
  const aRemettre = useQuery({ queryKey: ["a-remettre"], queryFn: listerARemettre });
  const comptes = useQuery({ queryKey: ["comptes-tresorerie"], queryFn: listerComptes });
  const [type, setType] = useState<TypeDepot>("depot_especes");
  const [choisies, setChoisies] = useState<string[]>([]);
  const [destination, setDestination] = useState("");
  const [reference, setReference] = useState("");
  const [prevue, setPrevue] = useState(false);
  const [date, setDate] = useState("");
  const [message, setMessage] = useState("");

  const champ = DEPOTS.find((d) => d.valeur === type)!.champ;
  const lignes = (aRemettre.data ?? []).filter((c) => c[champ] !== null);
  const selection = lignes.filter((c) => choisies.includes(c.id));
  const societe = selection[0]?.societe;
  const devise = selection[0]?.devise ?? "TND";
  const total = selection.reduce((somme, c) => somme + Number(c[champ]), 0);
  const destinations = (comptes.data ?? []).filter(
    (c) => c.est_actif && (!societe || c.societe === societe) && (type === "depot_especes" || c.type === "banque"),
  );
  const versBanque = destinations.find((c) => c.id === destination)?.type === "banque";

  const depot = useMutation({
    mutationFn: () => deposer({ type, clotures: choisies, destination, reference, prevue, date: date || null }),
    onSuccess: (operation) => {
      setMessage(
        prevue
          ? `Versement ${operation.numero} prévu ; confirmez-le dans « Prévisions » une fois fait.`
          : `Dépôt ${operation.numero} enregistré.`,
      );
      setChoisies([]);
      setReference("");
      invalider(queryClient);
    },
  });

  const cocher = (cloture: ARemettre) => {
    setMessage("");
    setChoisies((liste) =>
      liste.includes(cloture.id)
        ? liste.filter((id) => id !== cloture.id)
        : [...liste.filter((id) => lignes.find((l) => l.id === id)?.societe === cloture.societe), cloture.id],
    );
  };

  return (
    <Stack spacing={2}>
      {message && <Alert severity="success">{message}</Alert>}
      <ToggleButtonGroup
        exclusive
        size="small"
        value={type}
        onChange={(_, valeur: TypeDepot | null) => {
          if (!valeur) return;
          setType(valeur);
          setChoisies([]);
          setDestination("");
        }}
        aria-label="Argent à déposer"
      >
        {DEPOTS.map((d) => (
          <ToggleButton key={d.valeur} value={d.valeur}>
            {d.libelle}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
      {aRemettre.data && lignes.length === 0 && (
        <Typography color="text.secondary">Rien à déposer : toutes les clôtures validées sont remises.</Typography>
      )}
      {lignes.length > 0 && (
        <Table size="small" aria-label="Clôtures à remettre">
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox" />
              <TableCell>Clôture</TableCell>
              <TableCell align="right">Montant</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {lignes.map((c) => (
              <TableRow key={c.id} hover onClick={() => cocher(c)} sx={{ cursor: "pointer" }}>
                <TableCell padding="checkbox">
                  <Checkbox checked={choisies.includes(c.id)} slotProps={{ input: { "aria-label": c.numero } }} />
                </TableCell>
                <TableCell>
                  {c.numero}
                  <Typography variant="body2" color="text.secondary">
                    {c.magasin} · {jour(c.fin)}
                    {champ === "cheques" && ` · ${c.nombre_cheques} chèque(s)`}
                  </Typography>
                </TableCell>
                <TableCell align="right">{montant(c[champ], c.devise)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      {selection.length > 0 && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack spacing={2}>
            <Typography variant="subtitle2">
              {selection.length} clôture(s) · total {montant(String(total), devise)}
            </Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <TextField
                select
                label="Déposer sur"
                value={destination}
                onChange={(e) => setDestination(e.target.value)}
                sx={{ minWidth: 240 }}
              >
                {destinations.map((c) => (
                  <MenuItem key={c.id} value={c.id}>
                    {c.nom}
                  </MenuItem>
                ))}
              </TextField>
              {prevue ? (
                <TextField
                  type="date"
                  label="Date prévue"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
              ) : (
                <TextField
                  label="N° de bordereau"
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                  helperText={versBanque ? "Obligatoire pour un versement en banque." : " "}
                />
              )}
            </Stack>
            <FormControlLabel
              control={<Checkbox checked={prevue} onChange={(e) => setPrevue(e.target.checked)} />}
              label="Prévision : le versement n'est pas encore fait"
            />
            {destinations.length === 0 && (
              <Alert severity="info">Aucun compte ne convient : la finance doit d'abord le créer dans « Banque ».</Alert>
            )}
            {depot.isError && <Alert severity="error">{depot.error.message}</Alert>}
            <Button
              variant="contained"
              onClick={() => depot.mutate()}
              disabled={!destination || depot.isPending || (versBanque && !prevue && !reference.trim())}
              sx={{ alignSelf: "flex-start" }}
            >
              {prevue ? "Prévoir le versement" : "Enregistrer le dépôt"}
            </Button>
          </Stack>
        </Paper>
      )}
      <Previsions />
    </Stack>
  );
}

function Previsions() {
  const queryClient = useQueryClient();
  const prevues = useQuery({ queryKey: ["operations", "prevue"], queryFn: () => listerOperations("prevue") });
  const [references, setReferences] = useState<Record<string, string>>({});
  const action = useMutation({
    mutationFn: async ({ operation, annuler }: { operation: Operation; annuler: boolean }) => {
      if (annuler) await annulerOperation(operation.id);
      else await effectuerOperation(operation.id, references[operation.id] ?? "");
    },
    onSuccess: () => invalider(queryClient),
  });
  if (!prevues.data?.length) return null;
  return (
    <Stack spacing={1}>
      <Typography variant="subtitle2">Prévisions de versement</Typography>
      {action.isError && <Alert severity="error">{action.error.message}</Alert>}
      <Table size="small" aria-label="Prévisions de versement">
        <TableBody>
          {prevues.data.map((o) => (
            <TableRow key={o.id}>
              <TableCell>
                {o.numero} · {o.type_libelle}
                <Typography variant="body2" color="text.secondary">
                  {o.destination ?? o.magasin} {o.date_prevue && `· prévu le ${jour(o.date_prevue)}`} · {o.libelle}
                </Typography>
              </TableCell>
              <TableCell align="right">{montant(o.montant)}</TableCell>
              <TableCell>
                <TextField
                  size="small"
                  label={`Bordereau ${o.numero}`}
                  value={references[o.id] ?? ""}
                  onChange={(e) => setReferences((r) => ({ ...r, [o.id]: e.target.value }))}
                />
              </TableCell>
              <TableCell>
                <Stack direction="row" spacing={1}>
                  <Button size="small" variant="outlined" onClick={() => action.mutate({ operation: o, annuler: false })}>
                    Versement fait
                  </Button>
                  <Button size="small" color="error" onClick={() => action.mutate({ operation: o, annuler: true })}>
                    Annuler
                  </Button>
                </Stack>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Stack>
  );
}

export type DroitsBanque = { gererComptes: boolean; rapprocher: boolean; operations: boolean };

/** Comptes et soldes, opérations, rapprochement avec le relevé bancaire. */
export function Banque({ droits }: { droits: DroitsBanque }) {
  const comptes = useQuery({ queryKey: ["comptes-tresorerie"], queryFn: listerComptes });
  const [statut, setStatut] = useState<StatutOperation | "toutes">(droits.rapprocher ? "effectuee" : "toutes");
  const operations = useQuery({
    queryKey: ["operations", statut],
    queryFn: () => listerOperations(statut === "toutes" ? undefined : statut),
  });

  return (
    <Stack spacing={3}>
      <Stack spacing={1}>
        <Typography variant="subtitle2">Comptes</Typography>
        {comptes.data?.length === 0 && <Typography color="text.secondary">Aucun compte pour l'instant.</Typography>}
        {comptes.data && comptes.data.length > 0 && <Comptes comptes={comptes.data} />}
        {droits.gererComptes && <NouveauCompte />}
      </Stack>
      {droits.operations && comptes.data && comptes.data.length > 0 && <NouvelleOperation comptes={comptes.data} />}
      <Stack spacing={1}>
        <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
          <Typography variant="subtitle2">Opérations</Typography>
          <TextField
            select
            size="small"
            label="Statut"
            value={statut}
            onChange={(e) => setStatut(e.target.value as StatutOperation | "toutes")}
            sx={{ minWidth: 200 }}
          >
            <MenuItem value="toutes">Toutes</MenuItem>
            <MenuItem value="prevue">Prévues</MenuItem>
            <MenuItem value="effectuee">À rapprocher</MenuItem>
            <MenuItem value="rapprochee">Rapprochées</MenuItem>
          </TextField>
        </Stack>
        {operations.data?.length === 0 && <Typography color="text.secondary">Aucune opération.</Typography>}
        {operations.data && operations.data.length > 0 && (
          <Operations operations={operations.data} comptes={comptes.data ?? []} rapprocher={droits.rapprocher} />
        )}
      </Stack>
    </Stack>
  );
}

function Comptes({ comptes }: { comptes: Compte[] }) {
  return (
    <Table size="small" aria-label="Comptes de trésorerie">
      <TableHead>
        <TableRow>
          <TableCell>Compte</TableCell>
          <TableCell align="right">Solde OptiLink</TableCell>
          <TableCell align="right">Solde banque</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {comptes.map((c) => (
          <TableRow key={c.id}>
            <TableCell>
              {c.nom}
              <Typography variant="body2" color="text.secondary">
                {TYPES_COMPTE.find((t) => t.valeur === c.type)?.libelle} · {c.societe_nom}
                {c.rib && ` · RIB ${c.rib}`}
                {c.magasin_nom && ` · ${c.magasin_nom}`}
              </Typography>
            </TableCell>
            <TableCell align="right">{montant(c.solde_comptable, c.devise)}</TableCell>
            <TableCell align="right">{c.type === "banque" ? montant(c.solde_banque, c.devise) : ""}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

const COMPTE_VIDE = { type: "banque" as TypeCompte, nom: "", banque: "", rib: "", magasin: "", solde_initial: "" };

function NouveauCompte() {
  const queryClient = useQueryClient();
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const societes = [...new Map((magasins.data ?? []).map((m) => [m.societe_id, m.societe])).entries()];
  const [ouvert, setOuvert] = useState(false);
  const [saisie, setSaisie] = useState(COMPTE_VIDE);
  const [societeChoisie, setSociete] = useState("");
  const societe = societeChoisie || societes[0]?.[0] || "";
  const changer = (champ: keyof typeof COMPTE_VIDE) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setSaisie((s) => ({ ...s, [champ]: e.target.value }));
  const creation = useMutation({
    mutationFn: () =>
      creerCompte({
        ...saisie,
        societe,
        magasin: saisie.type === "coffre" ? saisie.magasin || null : null,
        solde_initial: saisie.solde_initial || "0",
      }),
    onSuccess: () => {
      setSaisie(COMPTE_VIDE);
      setOuvert(false);
      void queryClient.invalidateQueries({ queryKey: ["comptes-tresorerie"] });
    },
  });
  if (!ouvert) {
    return (
      <Button onClick={() => setOuvert(true)} sx={{ alignSelf: "flex-start" }}>
        Ajouter un compte
      </Button>
    );
  }
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack spacing={2}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
          {societes.length > 1 && (
            <TextField select label="Société" value={societe} onChange={(e) => setSociete(e.target.value)}>
              {societes.map(([id, nom]) => (
                <MenuItem key={id} value={id}>
                  {nom}
                </MenuItem>
              ))}
            </TextField>
          )}
          <TextField select label="Type de compte" value={saisie.type} onChange={changer("type")} sx={{ minWidth: 200 }}>
            {TYPES_COMPTE.map((t) => (
              <MenuItem key={t.valeur} value={t.valeur}>
                {t.libelle}
              </MenuItem>
            ))}
          </TextField>
          <TextField label="Nom du compte" value={saisie.nom} onChange={changer("nom")} sx={{ flexGrow: 1 }} />
        </Stack>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
          {saisie.type === "banque" && (
            <>
              <TextField label="Banque" value={saisie.banque} onChange={changer("banque")} />
              <TextField label="RIB" value={saisie.rib} onChange={changer("rib")} sx={{ flexGrow: 1 }} />
            </>
          )}
          {saisie.type === "coffre" && (
            <TextField select label="Magasin" value={saisie.magasin} onChange={changer("magasin")} sx={{ minWidth: 200 }}>
              {magasins.data
                ?.filter((m) => m.societe_id === societe)
                .map((m) => (
                  <MenuItem key={m.id} value={m.id}>
                    {m.nom}
                  </MenuItem>
                ))}
            </TextField>
          )}
          <TextField
            label="Solde de départ"
            value={saisie.solde_initial}
            onChange={changer("solde_initial")}
            slotProps={{ htmlInput: { inputMode: "decimal" } }}
          />
        </Stack>
        {creation.isError && <Alert severity="error">{creation.error.message}</Alert>}
        <Stack direction="row" spacing={2}>
          <Button variant="contained" onClick={() => creation.mutate()} disabled={!saisie.nom || creation.isPending}>
            Créer le compte
          </Button>
          <Button onClick={() => setOuvert(false)}>Fermer</Button>
        </Stack>
      </Stack>
    </Paper>
  );
}

type TypeLibre = "transfert" | "alimentation_fond" | "operation_bancaire";
const OPERATIONS_LIBRES: { valeur: TypeLibre; libelle: string }[] = [
  { valeur: "alimentation_fond", libelle: "Alimenter le fond d'une caisse" },
  { valeur: "transfert", libelle: "Transfert entre comptes" },
  { valeur: "operation_bancaire", libelle: "Opération bancaire (frais, agios…)" },
];

const OPERATION_VIDE = { source: "", destination: "", magasin: "", montant: "", reference: "", libelle: "" };

function NouvelleOperation({ comptes }: { comptes: Compte[] }) {
  const queryClient = useQueryClient();
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [ouvert, setOuvert] = useState(false);
  const [type, setType] = useState<TypeLibre>("alimentation_fond");
  const [sens, setSens] = useState<"debit" | "credit">("debit");
  const [saisie, setSaisie] = useState(OPERATION_VIDE);
  const [message, setMessage] = useState("");
  const changer = (champ: keyof typeof OPERATION_VIDE) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setSaisie((s) => ({ ...s, [champ]: e.target.value }));
  const actifs = comptes.filter((c) => c.est_actif);
  const compte = (id: string) => actifs.find((c) => c.id === id);
  const banques = actifs.filter((c) => c.type === "banque");

  let source: string | null = saisie.source || null;
  let destination: string | null = saisie.destination || null;
  if (type === "alimentation_fond") destination = null;
  if (type === "operation_bancaire") {
    [source, destination] = sens === "debit" ? [saisie.source || null, null] : [null, saisie.source || null];
  }
  const societe = compte(saisie.source)?.societe ?? "";

  const enregistrement = useMutation({
    mutationFn: () =>
      creerOperation({
        type,
        societe,
        montant: saisie.montant,
        source,
        destination,
        magasin: type === "alimentation_fond" ? saisie.magasin || null : null,
        reference: saisie.reference,
        libelle: saisie.libelle,
        prevue: false,
        date: null,
      }),
    onSuccess: (operation) => {
      setMessage(`Opération ${operation.numero} enregistrée.`);
      setSaisie(OPERATION_VIDE);
      invalider(queryClient);
    },
  });

  if (!ouvert) {
    return (
      <Button variant="outlined" onClick={() => setOuvert(true)} sx={{ alignSelf: "flex-start" }}>
        Nouvelle opération
      </Button>
    );
  }
  const sources =
    type === "alimentation_fond"
      ? actifs.filter((c) => c.type !== "banque")
      : type === "operation_bancaire"
        ? banques
        : actifs;
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack spacing={2}>
        {message && <Alert severity="success">{message}</Alert>}
        <TextField
          select
          label="Opération"
          value={type}
          onChange={(e) => {
            setType(e.target.value as TypeLibre);
            setSaisie(OPERATION_VIDE);
          }}
          sx={{ maxWidth: 360 }}
        >
          {OPERATIONS_LIBRES.map((o) => (
            <MenuItem key={o.valeur} value={o.valeur}>
              {o.libelle}
            </MenuItem>
          ))}
        </TextField>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
          {type === "operation_bancaire" && (
            <TextField
              select
              label="Sens"
              value={sens}
              onChange={(e) => setSens(e.target.value as "debit" | "credit")}
              sx={{ minWidth: 160 }}
            >
              <MenuItem value="debit">Débit (frais)</MenuItem>
              <MenuItem value="credit">Crédit</MenuItem>
            </TextField>
          )}
          <TextField
            select
            label={type === "operation_bancaire" ? "Compte bancaire" : "Depuis"}
            value={saisie.source}
            onChange={changer("source")}
            sx={{ minWidth: 220 }}
          >
            {sources.map((c) => (
              <MenuItem key={c.id} value={c.id}>
                {c.nom}
              </MenuItem>
            ))}
          </TextField>
          {type === "transfert" && (
            <TextField select label="Vers" value={saisie.destination} onChange={changer("destination")} sx={{ minWidth: 220 }}>
              {actifs
                .filter((c) => c.id !== saisie.source && (!societe || c.societe === societe))
                .map((c) => (
                  <MenuItem key={c.id} value={c.id}>
                    {c.nom}
                  </MenuItem>
                ))}
            </TextField>
          )}
          {type === "alimentation_fond" && (
            <TextField select label="Caisse du magasin" value={saisie.magasin} onChange={changer("magasin")} sx={{ minWidth: 200 }}>
              {magasins.data
                ?.filter((m) => !societe || m.societe_id === societe)
                .map((m) => (
                  <MenuItem key={m.id} value={m.id}>
                    {m.nom}
                  </MenuItem>
                ))}
            </TextField>
          )}
          <TextField
            label="Montant"
            value={saisie.montant}
            onChange={changer("montant")}
            slotProps={{ htmlInput: { inputMode: "decimal" } }}
            sx={{ maxWidth: 160 }}
          />
        </Stack>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
          <TextField label="N° de pièce" value={saisie.reference} onChange={changer("reference")} />
          <TextField label="Libellé" value={saisie.libelle} onChange={changer("libelle")} sx={{ flexGrow: 1 }} />
        </Stack>
        {enregistrement.isError && <Alert severity="error">{enregistrement.error.message}</Alert>}
        <Stack direction="row" spacing={2}>
          <Button
            variant="contained"
            onClick={() => enregistrement.mutate()}
            disabled={!saisie.source || !saisie.montant || enregistrement.isPending}
          >
            Enregistrer l'opération
          </Button>
          <Button onClick={() => setOuvert(false)}>Fermer</Button>
        </Stack>
      </Stack>
    </Paper>
  );
}

function Operations({ operations, comptes, rapprocher }: { operations: Operation[]; comptes: Compte[]; rapprocher: boolean }) {
  const banques = new Set(comptes.filter((c) => c.type === "banque").map((c) => c.nom));
  return (
    <Table size="small" aria-label="Opérations de trésorerie">
      <TableHead>
        <TableRow>
          <TableCell>Opération</TableCell>
          <TableCell align="right">Montant</TableCell>
          <TableCell>Statut</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {operations.map((o) => {
          const parLaBanque = [o.source, o.destination].some((c) => c !== null && banques.has(c));
          return (
            <TableRow key={o.id}>
              <TableCell>
                {o.numero} · {o.type_libelle}
                <Typography variant="body2" color="text.secondary">
                  {[o.source, o.destination ?? o.magasin].filter(Boolean).join(" → ")}
                  {o.reference && ` · pièce ${o.reference}`}
                  {o.date_operation && ` · le ${jour(o.date_operation)}`}
                  {o.libelle && ` · ${o.libelle}`}
                </Typography>
              </TableCell>
              <TableCell align="right">
                {montant(o.montant)}
                {o.commission !== null && (
                  <Typography variant="body2" color="text.secondary">
                    commission {montant(o.commission)}
                  </Typography>
                )}
              </TableCell>
              <TableCell>
                <Chip size="small" color={STATUTS[o.statut].couleur} label={STATUTS[o.statut].libelle} />
                {o.date_valeur && (
                  <Typography variant="body2" color="text.secondary">
                    valeur {jour(o.date_valeur)}
                  </Typography>
                )}
                {rapprocher && o.statut === "effectuee" && parLaBanque && <Rapprochement operation={o} />}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

function Rapprochement({ operation }: { operation: Operation }) {
  const queryClient = useQueryClient();
  const cartes = operation.type === "encaissement_cartes";
  const [date, setDate] = useState(aujourdhui());
  const [credite, setCredite] = useState("");
  const rapprochement = useMutation({
    mutationFn: () => rapprocherOperation(operation.id, date, cartes ? credite : null),
    onSuccess: () => invalider(queryClient),
  });
  return (
    <Stack spacing={1} sx={{ mt: 1 }}>
      <TextField
        size="small"
        type="date"
        label={`Date de valeur ${operation.numero}`}
        value={date}
        onChange={(e) => setDate(e.target.value)}
        slotProps={{ inputLabel: { shrink: true } }}
      />
      {cartes && (
        <TextField
          size="small"
          label={`Montant crédité ${operation.numero}`}
          value={credite}
          onChange={(e) => setCredite(e.target.value)}
          helperText="Ce que la banque a versé, commission déduite."
          slotProps={{ htmlInput: { inputMode: "decimal" } }}
        />
      )}
      {rapprochement.isError && <Alert severity="error">{rapprochement.error.message}</Alert>}
      <Button
        size="small"
        variant="outlined"
        onClick={() => rapprochement.mutate()}
        disabled={!date || (cartes && !credite) || rapprochement.isPending}
      >
        Rapprocher
      </Button>
    </Stack>
  );
}
