import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import FormControlLabel from "@mui/material/FormControlLabel";
import FormGroup from "@mui/material/FormGroup";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemText from "@mui/material/ListItemText";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Switch from "@mui/material/Switch";
import Tab from "@mui/material/Tab";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Tabs from "@mui/material/Tabs";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  creerProfil,
  creerUtilisateur,
  listerPrivileges,
  listerProfils,
  listerSocietes,
  listerUtilisateurs,
  modifierProfil,
  modifierUtilisateur,
  reinitialiserMfa,
  supprimerProfil,
  type Affectation,
  type Portee,
  type Profil,
  type Utilisateur,
} from "../api/acces";
import { listerMagasins } from "../api/magasins";
import { BoutonImport } from "./Imports";

export type DroitsAcces = {
  voirUtilisateurs: boolean;
  creerUtilisateur: boolean;
  modifierUtilisateur: boolean;
  voirProfils: boolean;
  creerProfil: boolean;
  modifierProfil: boolean;
  supprimerProfil: boolean;
};

const PORTEES: { valeur: Portee; libelle: string }[] = [
  { valeur: "magasin", libelle: "Un magasin" },
  { valeur: "societe", libelle: "Une société" },
  { valeur: "reseau", libelle: "Tout le réseau" },
];

/** Comptes des employés, profils et privilèges de chaque profil. */
export function AccesSecurite({ droits }: { droits: DroitsAcces }) {
  const [onglet, setOnglet] = useState(droits.voirUtilisateurs ? "utilisateurs" : "profils");
  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Accès et sécurité
          </Typography>
          <Tabs value={onglet} onChange={(_, valeur: string) => setOnglet(valeur)}>
            {droits.voirUtilisateurs && <Tab value="utilisateurs" label="Utilisateurs" />}
            {droits.voirProfils && <Tab value="profils" label="Profils et privilèges" />}
          </Tabs>
          {onglet === "utilisateurs" && <Utilisateurs droits={droits} />}
          {onglet === "profils" && <Profils droits={droits} />}
        </Stack>
      </CardContent>
    </Card>
  );
}

function Utilisateurs({ droits }: { droits: DroitsAcces }) {
  const utilisateurs = useQuery({ queryKey: ["utilisateurs"], queryFn: listerUtilisateurs });
  const [edite, setEdite] = useState<Utilisateur | "nouveau" | null>(null);
  return (
    <Stack spacing={2}>
      {droits.creerUtilisateur && (
        <Stack direction="row" spacing={2}>
          <Button variant="contained" onClick={() => setEdite("nouveau")}>
            Nouvel utilisateur
          </Button>
          <BoutonImport type="utilisateurs" libelle="Importer des utilisateurs" />
        </Stack>
      )}
      {utilisateurs.isError && <Alert severity="error">{utilisateurs.error.message}</Alert>}
      <Table size="small" aria-label="Utilisateurs">
        <TableHead>
          <TableRow>
            <TableCell>Utilisateur</TableCell>
            <TableCell>État</TableCell>
            <TableCell>Profils</TableCell>
            <TableCell>Double authentification</TableCell>
            <TableCell />
          </TableRow>
        </TableHead>
        <TableBody>
          {utilisateurs.data?.map((u) => (
            <TableRow key={u.id}>
              <TableCell>
                {[u.prenom, u.nom].filter(Boolean).join(" ") || u.identifiant}
                <Typography variant="body2" color="text.secondary">
                  {u.identifiant}
                </Typography>
              </TableCell>
              <TableCell>
                <Chip
                  size="small"
                  color={u.actif ? "success" : "default"}
                  variant={u.actif ? "filled" : "outlined"}
                  label={u.actif ? "Actif" : "Inactif"}
                />
                {u.connecte && <Chip size="small" color="info" label="Connecté" sx={{ ml: 0.5 }} />}
              </TableCell>
              <TableCell>
                <Stack direction="row" spacing={0.5} useFlexGap sx={{ flexWrap: "wrap" }}>
                  {u.administrateur_technique && <Chip size="small" color="warning" label="Compte technique" />}
                  {u.affectations.map((a) => (
                    <Chip key={a.id} size="small" label={`${a.profil_nom} · ${a.perimetre}`} />
                  ))}
                </Stack>
              </TableCell>
              <TableCell>{u.mfa_active ? "Activée" : "À activer à la connexion"}</TableCell>
              <TableCell align="right">
                {droits.modifierUtilisateur && !u.administrateur_technique && (
                  <Button size="small" onClick={() => setEdite(u)}>
                    Modifier
                  </Button>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {edite && <FicheUtilisateur utilisateur={edite === "nouveau" ? null : edite} onFermer={() => setEdite(null)} />}
    </Stack>
  );
}

function FicheUtilisateur({ utilisateur, onFermer }: { utilisateur: Utilisateur | null; onFermer: () => void }) {
  const queryClient = useQueryClient();
  const profils = useQuery({ queryKey: ["profils"], queryFn: listerProfils });
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const societes = useQuery({ queryKey: ["societes"], queryFn: listerSocietes });
  const [identifiant, setIdentifiant] = useState(utilisateur?.identifiant ?? "");
  const [prenom, setPrenom] = useState(utilisateur?.prenom ?? "");
  const [nom, setNom] = useState(utilisateur?.nom ?? "");
  const [email, setEmail] = useState(utilisateur?.email ?? "");
  const [actif, setActif] = useState(utilisateur?.actif ?? true);
  const [motDePasse, setMotDePasse] = useState("");
  const [affectations, setAffectations] = useState<Affectation[]>(utilisateur?.affectations ?? []);
  const [message, setMessage] = useState("");

  const enregistrer = useMutation({
    mutationFn: () => {
      const saisie = {
        prenom,
        nom,
        email,
        affectations: affectations.map((a) => ({
          ...(a.id ? { id: a.id } : {}),
          profil: a.profil,
          portee: a.portee,
          magasin: a.portee === "magasin" ? a.magasin : null,
          societe: a.portee === "societe" ? a.societe : null,
          ...(a.debut ? { debut: a.debut } : {}),
          fin: a.fin ?? null,
        })),
        ...(motDePasse ? { mot_de_passe: motDePasse } : {}),
      };
      return utilisateur
        ? modifierUtilisateur(utilisateur.id, { ...saisie, actif })
        : creerUtilisateur({ ...saisie, identifiant });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["utilisateurs"] });
      void queryClient.invalidateQueries({ queryKey: ["profils"] });
      onFermer();
    },
  });
  const mfa = useMutation({
    mutationFn: () => reinitialiserMfa(utilisateur!.id),
    onSuccess: () => {
      setMessage("Double authentification réinitialisée : elle sera demandée à la prochaine connexion.");
      void queryClient.invalidateQueries({ queryKey: ["utilisateurs"] });
    },
  });

  const changer = (index: number, champs: Partial<Affectation>) =>
    setAffectations((liste) => liste.map((a, i) => (i === index ? { ...a, ...champs } : a)));

  return (
    <Dialog open onClose={onFermer} fullWidth maxWidth="md">
      <DialogTitle>{utilisateur ? `Modifier ${utilisateur.identifiant}` : "Nouvel utilisateur"}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField
              label="Identifiant"
              value={identifiant}
              onChange={(e) => setIdentifiant(e.target.value)}
              disabled={Boolean(utilisateur)}
              required
            />
            <TextField label="Prénom" value={prenom} onChange={(e) => setPrenom(e.target.value)} />
            <TextField label="Nom" value={nom} onChange={(e) => setNom(e.target.value)} />
          </Stack>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField label="E-mail" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            <TextField
              label={utilisateur ? "Nouveau mot de passe" : "Mot de passe provisoire"}
              type="password"
              value={motDePasse}
              onChange={(e) => setMotDePasse(e.target.value)}
              required={!utilisateur}
              helperText={utilisateur ? "Laisser vide pour ne pas le changer." : "12 caractères au moins."}
            />
          </Stack>
          {utilisateur && (
            <FormControlLabel
              control={<Switch checked={actif} onChange={(e) => setActif(e.target.checked)} />}
              label={actif ? "Compte actif" : "Compte désactivé"}
            />
          )}

          <Typography variant="subtitle1">Profils</Typography>
          {affectations.length === 0 && (
            <Typography color="text.secondary">Aucun profil : cet utilisateur n'aura accès à rien.</Typography>
          )}
          {affectations.map((a, index) => (
            <Stack
              key={a.id ?? `n${index}`}
              direction={{ xs: "column", sm: "row" }}
              spacing={1}
              sx={{ alignItems: "center" }}
            >
              <TextField
                select
                size="small"
                label="Profil"
                value={a.profil || ""}
                onChange={(e) => changer(index, { profil: Number(e.target.value) })}
                sx={{ minWidth: 220 }}
              >
                {profils.data?.map((p) => (
                  <MenuItem key={p.id} value={p.id}>
                    {p.nom}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                select
                size="small"
                label="Portée"
                value={a.portee}
                onChange={(e) => changer(index, { portee: e.target.value as Portee })}
                sx={{ minWidth: 150 }}
              >
                {PORTEES.map((p) => (
                  <MenuItem key={p.valeur} value={p.valeur}>
                    {p.libelle}
                  </MenuItem>
                ))}
              </TextField>
              {a.portee === "magasin" && (
                <TextField
                  select
                  size="small"
                  label="Magasin"
                  value={a.magasin ?? ""}
                  onChange={(e) => changer(index, { magasin: e.target.value })}
                  sx={{ minWidth: 200 }}
                >
                  {magasins.data?.map((m) => (
                    <MenuItem key={m.id} value={m.id}>
                      {m.code} {m.nom}
                    </MenuItem>
                  ))}
                </TextField>
              )}
              {a.portee === "societe" && (
                <TextField
                  select
                  size="small"
                  label="Société"
                  value={a.societe ?? ""}
                  onChange={(e) => changer(index, { societe: e.target.value })}
                  sx={{ minWidth: 200 }}
                >
                  {societes.data?.map((s) => (
                    <MenuItem key={s.id} value={s.id}>
                      {s.raison_sociale}
                    </MenuItem>
                  ))}
                </TextField>
              )}
              <Button color="error" onClick={() => setAffectations((liste) => liste.filter((_, i) => i !== index))}>
                Retirer
              </Button>
            </Stack>
          ))}
          <Button
            onClick={() =>
              setAffectations((liste) => [
                ...liste,
                { profil: 0, portee: "magasin", magasin: magasins.data?.[0]?.id ?? null, societe: null },
              ])
            }
            sx={{ alignSelf: "flex-start" }}
          >
            Ajouter un profil
          </Button>
          {message && <Alert severity="success">{message}</Alert>}
          {enregistrer.isError && <Alert severity="error">{enregistrer.error.message}</Alert>}
          {mfa.isError && <Alert severity="error">{mfa.error.message}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        {utilisateur?.mfa_active && (
          <Button color="warning" onClick={() => mfa.mutate()} sx={{ mr: "auto" }}>
            Réinitialiser la double authentification
          </Button>
        )}
        <Button onClick={onFermer}>Annuler</Button>
        <Button
          variant="contained"
          onClick={() => enregistrer.mutate()}
          disabled={enregistrer.isPending || !identifiant || affectations.some((a) => !a.profil)}
        >
          Enregistrer
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function Profils({ droits }: { droits: DroitsAcces }) {
  const queryClient = useQueryClient();
  const profils = useQuery({ queryKey: ["profils"], queryFn: listerProfils });
  const catalogue = useQuery({ queryKey: ["privileges"], queryFn: listerPrivileges });
  const [choisi, setChoisi] = useState<number | null>(null);
  const profil = profils.data?.find((p) => p.id === choisi) ?? profils.data?.[0];
  const [nouveau, setNouveau] = useState("");

  const creation = useMutation({
    mutationFn: () => creerProfil(nouveau.trim()),
    onSuccess: (cree) => {
      setNouveau("");
      setChoisi(cree.id);
      void queryClient.invalidateQueries({ queryKey: ["profils"] });
    },
  });

  return (
    <Stack direction={{ xs: "column", md: "row" }} spacing={3} sx={{ alignItems: "flex-start" }}>
      <Stack spacing={1} sx={{ minWidth: 240 }}>
        <List dense aria-label="Profils">
          {profils.data?.map((p) => (
            <ListItemButton key={p.id} selected={p.id === profil?.id} onClick={() => setChoisi(p.id)}>
              <ListItemText
                primary={p.nom}
                secondary={p.utilisateurs === 1 ? "1 utilisateur" : `${p.utilisateurs} utilisateurs`}
              />
            </ListItemButton>
          ))}
        </List>
        {droits.creerProfil && (
          <Stack direction="row" spacing={1}>
            <TextField
              size="small"
              label="Nouveau profil"
              value={nouveau}
              onChange={(e) => setNouveau(e.target.value)}
            />
            <Button onClick={() => creation.mutate()} disabled={!nouveau.trim() || creation.isPending}>
              Créer
            </Button>
          </Stack>
        )}
        {creation.isError && <Alert severity="error">{creation.error.message}</Alert>}
      </Stack>
      {profil && catalogue.data && (
        <PrivilegesDuProfil key={profil.id} profil={profil} catalogue={catalogue.data} droits={droits} />
      )}
    </Stack>
  );
}

function PrivilegesDuProfil({
  profil,
  catalogue,
  droits,
}: {
  profil: Profil;
  catalogue: Awaited<ReturnType<typeof listerPrivileges>>;
  droits: DroitsAcces;
}) {
  const queryClient = useQueryClient();
  const [coches, setCoches] = useState(new Set(profil.privileges));
  const [message, setMessage] = useState("");
  const rafraichir = () => void queryClient.invalidateQueries({ queryKey: ["profils"] });

  const enregistrer = useMutation({
    mutationFn: () => modifierProfil(profil.id, [...coches]),
    onSuccess: () => {
      setMessage(`Privilèges du profil « ${profil.nom} » enregistrés.`);
      rafraichir();
    },
  });
  const suppression = useMutation({ mutationFn: () => supprimerProfil(profil.id), onSuccess: rafraichir });

  const basculer = (code: string) =>
    setCoches((actuels) => {
      const suivants = new Set(actuels);
      if (suivants.has(code)) suivants.delete(code);
      else suivants.add(code);
      return suivants;
    });

  return (
    <Stack spacing={2} sx={{ flexGrow: 1 }}>
      <Typography variant="subtitle1">Privilèges du profil « {profil.nom} »</Typography>
      {catalogue.map((module) => (
        <div key={module.module}>
          <Typography variant="subtitle2" color="primary">
            {module.module}
          </Typography>
          <FormGroup>
            {module.privileges.map((p) => (
              <FormControlLabel
                key={p.code}
                control={
                  <Checkbox
                    size="small"
                    checked={coches.has(p.code)}
                    onChange={() => basculer(p.code)}
                    disabled={!droits.modifierProfil}
                  />
                }
                label={p.libelle}
              />
            ))}
          </FormGroup>
        </div>
      ))}
      {message && <Alert severity="success">{message}</Alert>}
      {enregistrer.isError && <Alert severity="error">{enregistrer.error.message}</Alert>}
      {suppression.isError && <Alert severity="error">{suppression.error.message}</Alert>}
      <Stack direction="row" spacing={2}>
        {droits.modifierProfil && (
          <Button variant="contained" onClick={() => enregistrer.mutate()} disabled={enregistrer.isPending}>
            Enregistrer
          </Button>
        )}
        {droits.supprimerProfil && profil.utilisateurs === 0 && (
          <Button color="error" onClick={() => suppression.mutate()}>
            Supprimer ce profil
          </Button>
        )}
      </Stack>
    </Stack>
  );
}
