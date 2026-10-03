import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import MenuItem from "@mui/material/MenuItem";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
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

import { listerMagasins } from "../api/magasins";
import {
  annulerMonConge,
  creerEmploye,
  deciderConge,
  demanderConge,
  enregistrerPresence,
  lireMonEspace,
  lirePresence,
  listerConges,
  listerEmployes,
  saisirConge,
  type Conge,
  type LignePresence,
  type SaisieConge,
  type Solde,
  type StatutConge,
  type StatutPointage,
  type TypeConge,
} from "../api/rh";

export type DroitsRh = {
  voirEmployes: boolean;
  creerEmploye: boolean;
  voirPresence: boolean;
  pointer: boolean;
  voirConges: boolean;
  saisirConge: boolean;
  deciderConge: boolean;
};

const TYPES: { valeur: TypeConge; libelle: string }[] = [
  { valeur: "annuel", libelle: "Congé annuel payé" },
  { valeur: "maladie", libelle: "Congé maladie" },
  { valeur: "exceptionnel", libelle: "Congé exceptionnel (mariage, décès…)" },
  { valeur: "maternite", libelle: "Congé de maternité ou de paternité" },
  { valeur: "sans_solde", libelle: "Congé sans solde" },
];

const STATUTS: Record<StatutConge, { libelle: string; couleur: "default" | "info" | "success" | "error" }> = {
  demandee: { libelle: "En attente", couleur: "info" },
  acceptee: { libelle: "Acceptée", couleur: "success" },
  refusee: { libelle: "Refusée", couleur: "error" },
  annulee: { libelle: "Annulée", couleur: "default" },
};

const POINTAGES: { valeur: StatutPointage; libelle: string }[] = [
  { valeur: "present", libelle: "Présent" },
  { valeur: "retard", libelle: "En retard" },
  { valeur: "absent_justifie", libelle: "Absent justifié" },
  { valeur: "absent", libelle: "Absent non justifié" },
];

const jour = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString("fr-FR");
const aujourdhui = () => new Date().toLocaleDateString("en-CA");
const jours = (valeur: string) => `${Number(valeur).toLocaleString("fr-FR")} j`;

/** Personnel : congés de chacun, présence du jour, décisions et fiches employés. */
export function RessourcesHumaines({ droits }: { droits: DroitsRh }) {
  const espace = useQuery({ queryKey: ["mon-espace-rh"], queryFn: lireMonEspace, retry: false });
  const estEmploye = Boolean(espace.data?.employe);
  const onglets = [
    estEmploye && { valeur: "moi", libelle: "Mes congés" },
    droits.voirPresence && { valeur: "presence", libelle: "Présence" },
    droits.voirConges && { valeur: "conges", libelle: "Congés" },
    droits.voirEmployes && { valeur: "employes", libelle: "Employés" },
  ].filter((o): o is { valeur: string; libelle: string } => Boolean(o));
  const [choisi, setOnglet] = useState("");
  const onglet = onglets.some((o) => o.valeur === choisi) ? choisi : onglets[0]?.valeur;
  if (!onglet) return null;

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Ressources humaines
          </Typography>
          <Tabs value={onglet} onChange={(_, valeur: string) => setOnglet(valeur)} variant="scrollable">
            {onglets.map((o) => (
              <Tab key={o.valeur} value={o.valeur} label={o.libelle} />
            ))}
          </Tabs>
          {onglet === "moi" && espace.data && <MesConges conges={espace.data.employe.solde} demandes={espace.data.conges} />}
          {onglet === "presence" && <Presence pointer={droits.pointer} />}
          {onglet === "conges" && <Conges droits={droits} />}
          {onglet === "employes" && <Employes creer={droits.creerEmploye} />}
        </Stack>
      </CardContent>
    </Card>
  );
}

function SoldeConges({ solde }: { solde: Solde }) {
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle2">Congé annuel</Typography>
      <Typography>
        Disponible : <strong>{jours(solde.disponible)}</strong>
      </Typography>
      <Typography variant="body2" color="text.secondary">
        Acquis {jours(solde.acquis)} − pris {jours(solde.pris)} − en attente {jours(solde.en_attente)}
      </Typography>
    </Paper>
  );
}

const DEMANDE_VIDE: SaisieConge = { type: "annuel", debut: "", fin: "", motif: "" };

function FormulaireConge({ envoyer, enCours, erreur }: {
  envoyer: (demande: SaisieConge) => void;
  enCours: boolean;
  erreur: Error | null;
}) {
  const [demande, setDemande] = useState(DEMANDE_VIDE);
  const changer = (champ: keyof SaisieConge) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setDemande((d) => ({ ...d, [champ]: e.target.value }));
  return (
    <Stack spacing={2}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <TextField select label="Type de congé" value={demande.type} onChange={changer("type")} sx={{ minWidth: 260 }}>
          {TYPES.map((t) => (
            <MenuItem key={t.valeur} value={t.valeur}>
              {t.libelle}
            </MenuItem>
          ))}
        </TextField>
        <TextField type="date" label="Du" value={demande.debut} onChange={changer("debut")} slotProps={{ inputLabel: { shrink: true } }} />
        <TextField type="date" label="Au" value={demande.fin} onChange={changer("fin")} slotProps={{ inputLabel: { shrink: true } }} />
      </Stack>
      <TextField label="Motif" value={demande.motif} onChange={changer("motif")} />
      {erreur && <Alert severity="error">{erreur.message}</Alert>}
      <Button
        variant="contained"
        onClick={() => {
          envoyer(demande);
          setDemande(DEMANDE_VIDE);
        }}
        disabled={!demande.debut || !demande.fin || enCours}
        sx={{ alignSelf: "flex-start" }}
      >
        Envoyer la demande
      </Button>
    </Stack>
  );
}

function MesConges({ conges: solde, demandes }: { conges: Solde; demandes: Conge[] }) {
  const queryClient = useQueryClient();
  const rafraichir = (espace: unknown) => queryClient.setQueryData(["mon-espace-rh"], espace);
  const demande = useMutation({ mutationFn: demanderConge, onSuccess: rafraichir });
  const annulation = useMutation({ mutationFn: annulerMonConge, onSuccess: rafraichir });
  return (
    <Stack spacing={2}>
      <SoldeConges solde={solde} />
      <Typography variant="subtitle2">Nouvelle demande</Typography>
      <FormulaireConge envoyer={(d) => demande.mutate(d)} enCours={demande.isPending} erreur={demande.error} />
      {annulation.isError && <Alert severity="error">{annulation.error.message}</Alert>}
      {demandes.length > 0 && (
        <TableConges conges={demandes} action={(c) =>
          (c.statut === "demandee" || (c.statut === "acceptee" && c.debut > aujourdhui())) && (
            <Button size="small" color="error" onClick={() => annulation.mutate(c.id)}>
              Annuler
            </Button>
          )
        } />
      )}
    </Stack>
  );
}

function TableConges({ conges, action, avecNom = false }: {
  conges: Conge[];
  action?: (conge: Conge) => React.ReactNode;
  avecNom?: boolean;
}) {
  return (
    <Table size="small" aria-label="Demandes de congé">
      <TableBody>
        {conges.map((c) => (
          <TableRow key={c.id}>
            <TableCell>
              {avecNom && <strong>{c.employe_nom} · </strong>}
              {c.type_libelle}
              <Typography variant="body2" color="text.secondary">
                Du {jour(c.debut)} au {jour(c.fin)} · {jours(c.jours)}
                {c.motif && ` · ${c.motif}`}
              </Typography>
              {c.commentaire_decision && (
                <Typography variant="body2">
                  {c.decidee_par} : « {c.commentaire_decision} »
                </Typography>
              )}
            </TableCell>
            <TableCell>
              <Chip size="small" color={STATUTS[c.statut].couleur} label={STATUTS[c.statut].libelle} />
            </TableCell>
            <TableCell>{action?.(c)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function ChoixMagasin({ valeur, changer }: { valeur: string; changer: (id: string) => void }) {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  return (
    <TextField select label="Magasin" value={valeur} onChange={(e) => changer(e.target.value)} sx={{ minWidth: 220 }}>
      {magasins.data?.map((m) => (
        <MenuItem key={m.id} value={m.id}>
          {m.nom}
        </MenuItem>
      ))}
    </TextField>
  );
}

function useMagasin() {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [choisi, setChoisi] = useState("");
  return [choisi || magasins.data?.[0]?.id || "", setChoisi] as const;
}

type Saisie = { statut: StatutPointage | ""; arrivee: string; depart: string; commentaire: string };

const versSaisie = (l: LignePresence): Saisie => ({
  statut: l.pointage?.statut ?? "",
  arrivee: l.pointage?.arrivee?.slice(0, 5) ?? "",
  depart: l.pointage?.depart?.slice(0, 5) ?? "",
  commentaire: l.pointage?.commentaire ?? "",
});

function Presence({ pointer }: { pointer: boolean }) {
  const [magasin, setMagasin] = useMagasin();
  const [date, setDate] = useState(aujourdhui());
  const feuille = useQuery({
    queryKey: ["presence", magasin, date],
    queryFn: () => lirePresence(magasin, date),
    enabled: Boolean(magasin && date),
  });
  return (
    <Stack spacing={2}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <ChoixMagasin valeur={magasin} changer={setMagasin} />
        <TextField
          type="date"
          label="Jour"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          slotProps={{ inputLabel: { shrink: true }, htmlInput: { max: aujourdhui() } }}
        />
      </Stack>
      {feuille.isError && <Alert severity="error">{feuille.error.message}</Alert>}
      {feuille.data?.length === 0 && <Typography color="text.secondary">Aucun employé dans ce magasin ce jour-là.</Typography>}
      {feuille.data && feuille.data.length > 0 && (
        <FeuillePresence key={`${magasin}-${date}`} magasin={magasin} date={date} lignes={feuille.data} pointer={pointer} />
      )}
    </Stack>
  );
}

function FeuillePresence({ magasin, date, lignes, pointer }: {
  magasin: string;
  date: string;
  lignes: LignePresence[];
  pointer: boolean;
}) {
  const queryClient = useQueryClient();
  const [saisies, setSaisies] = useState<Record<string, Saisie>>(() =>
    Object.fromEntries(lignes.map((l) => [l.employe, versSaisie(l)])),
  );
  const [message, setMessage] = useState("");
  const changer = (employe: string, champ: keyof Saisie, valeur: string) => {
    setMessage("");
    setSaisies((s) => ({ ...s, [employe]: { ...s[employe], [champ]: valeur } }));
  };
  const aPointer = lignes.filter((l) => !l.conge && saisies[l.employe].statut);
  const envoi = useMutation({
    mutationFn: () =>
      enregistrerPresence(
        magasin,
        date,
        aPointer.map((l) => {
          const s = saisies[l.employe];
          return {
            employe: l.employe,
            statut: s.statut as StatutPointage,
            arrivee: s.arrivee || null,
            depart: s.depart || null,
            commentaire: s.commentaire,
          };
        }),
      ),
    onSuccess: (feuille) => {
      queryClient.setQueryData(["presence", magasin, date], feuille);
      setMessage("Présence enregistrée.");
    },
  });
  const tous = (statut: StatutPointage) =>
    setSaisies((s) =>
      Object.fromEntries(lignes.map((l) => [l.employe, l.conge ? s[l.employe] : { ...s[l.employe], statut }])),
    );

  return (
    <Stack spacing={2}>
      {message && <Alert severity="success">{message}</Alert>}
      {pointer && (
        <Button size="small" onClick={() => tous("present")} sx={{ alignSelf: "flex-start" }}>
          Tout le monde présent
        </Button>
      )}
      <Table size="small" aria-label="Feuille de présence">
        <TableHead>
          <TableRow>
            <TableCell>Employé</TableCell>
            <TableCell>Présence</TableCell>
            <TableCell>Arrivée</TableCell>
            <TableCell>Départ</TableCell>
            <TableCell>Commentaire</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {lignes.map((l) => {
            const s = saisies[l.employe];
            return (
              <TableRow key={l.employe}>
                <TableCell>
                  {l.nom}
                  <Typography variant="body2" color="text.secondary">
                    {l.matricule} · {l.poste}
                  </Typography>
                </TableCell>
                {l.conge ? (
                  <TableCell colSpan={4}>
                    <Chip size="small" color="info" label={`En congé : ${l.conge}`} />
                  </TableCell>
                ) : (
                  <>
                    <TableCell>
                      <TextField
                        select
                        size="small"
                        label={`Présence ${l.nom}`}
                        value={s.statut}
                        onChange={(e) => changer(l.employe, "statut", e.target.value)}
                        disabled={!pointer}
                        sx={{ minWidth: 180 }}
                      >
                        {POINTAGES.map((p) => (
                          <MenuItem key={p.valeur} value={p.valeur}>
                            {p.libelle}
                          </MenuItem>
                        ))}
                      </TextField>
                    </TableCell>
                    {(["arrivee", "depart"] as const).map((champ) => (
                      <TableCell key={champ}>
                        <TextField
                          type="time"
                          size="small"
                          value={s[champ]}
                          onChange={(e) => changer(l.employe, champ, e.target.value)}
                          disabled={!pointer}
                          slotProps={{ htmlInput: { "aria-label": `${champ === "arrivee" ? "Arrivée" : "Départ"} ${l.nom}` } }}
                        />
                      </TableCell>
                    ))}
                    <TableCell>
                      <TextField
                        size="small"
                        value={s.commentaire}
                        onChange={(e) => changer(l.employe, "commentaire", e.target.value)}
                        disabled={!pointer}
                        slotProps={{ htmlInput: { "aria-label": `Commentaire ${l.nom}` } }}
                      />
                    </TableCell>
                  </>
                )}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      {envoi.isError && <Alert severity="error">{envoi.error.message}</Alert>}
      {pointer && (
        <Button
          variant="contained"
          onClick={() => envoi.mutate()}
          disabled={aPointer.length === 0 || envoi.isPending}
          sx={{ alignSelf: "flex-start" }}
        >
          Enregistrer la présence
        </Button>
      )}
    </Stack>
  );
}

function Conges({ droits }: { droits: DroitsRh }) {
  const queryClient = useQueryClient();
  const [statut, setStatut] = useState<StatutConge | "tous">(droits.deciderConge ? "demandee" : "tous");
  const conges = useQuery({
    queryKey: ["conges-rh", statut],
    queryFn: () => listerConges(statut === "tous" ? undefined : statut),
  });
  const employes = useQuery({ queryKey: ["employes"], queryFn: listerEmployes, enabled: droits.saisirConge });
  const [employe, setEmploye] = useState("");
  const [commentaires, setCommentaires] = useState<Record<string, string>>({});
  const invalider = () => {
    void queryClient.invalidateQueries({ queryKey: ["conges-rh"] });
    void queryClient.invalidateQueries({ queryKey: ["employes"] });
    void queryClient.invalidateQueries({ queryKey: ["presence"] });
  };
  const decision = useMutation({
    mutationFn: ({ conge, choix }: { conge: Conge; choix: "accepter" | "refuser" }) =>
      deciderConge(conge.id, choix, commentaires[conge.id] ?? ""),
    onSuccess: invalider,
  });
  const saisie = useMutation({
    mutationFn: (demande: SaisieConge) => saisirConge({ ...demande, employe }),
    onSuccess: invalider,
  });
  const choisi = employes.data?.find((e) => e.id === employe);

  return (
    <Stack spacing={2}>
      {droits.saisirConge && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack spacing={2}>
            <Typography variant="subtitle2">Saisir un congé pour un employé</Typography>
            <TextField select label="Employé" value={employe} onChange={(e) => setEmploye(e.target.value)} sx={{ maxWidth: 320 }}>
              {employes.data?.map((e) => (
                <MenuItem key={e.id} value={e.id}>
                  {e.prenom} {e.nom} · {e.magasin_nom}
                </MenuItem>
              ))}
            </TextField>
            {choisi && <SoldeConges solde={choisi.solde} />}
            {employe && <FormulaireConge envoyer={(d) => saisie.mutate(d)} enCours={saisie.isPending} erreur={saisie.error} />}
          </Stack>
        </Paper>
      )}
      <TextField
        select
        size="small"
        label="Afficher"
        value={statut}
        onChange={(e) => setStatut(e.target.value as StatutConge | "tous")}
        sx={{ maxWidth: 220 }}
      >
        <MenuItem value="demandee">En attente</MenuItem>
        <MenuItem value="acceptee">Acceptées</MenuItem>
        <MenuItem value="refusee">Refusées</MenuItem>
        <MenuItem value="tous">Toutes</MenuItem>
      </TextField>
      {decision.isError && <Alert severity="error">{decision.error.message}</Alert>}
      {conges.data?.length === 0 && <Typography color="text.secondary">Aucune demande.</Typography>}
      {conges.data && conges.data.length > 0 && (
        <TableConges
          avecNom
          conges={conges.data}
          action={(c) =>
            droits.deciderConge &&
            c.statut === "demandee" && (
              <Stack spacing={1}>
                <TextField
                  size="small"
                  label={`Commentaire ${c.employe_nom}`}
                  value={commentaires[c.id] ?? ""}
                  onChange={(e) => setCommentaires((m) => ({ ...m, [c.id]: e.target.value }))}
                  helperText="Obligatoire pour un refus."
                />
                <Stack direction="row" spacing={1}>
                  <Button size="small" variant="contained" color="success" onClick={() => decision.mutate({ conge: c, choix: "accepter" })}>
                    Accepter
                  </Button>
                  <Button
                    size="small"
                    color="error"
                    onClick={() => decision.mutate({ conge: c, choix: "refuser" })}
                    disabled={!commentaires[c.id]?.trim()}
                  >
                    Refuser
                  </Button>
                </Stack>
              </Stack>
            )
          }
        />
      )}
    </Stack>
  );
}

const FICHE_VIDE = {
  nom: "",
  prenom: "",
  cin: "",
  telephone: "",
  poste: "",
  date_embauche: "",
  solde_conges_initial: "",
  utilisateur: "",
};

function Employes({ creer }: { creer: boolean }) {
  const queryClient = useQueryClient();
  const employes = useQuery({ queryKey: ["employes"], queryFn: listerEmployes });
  const [magasin, setMagasin] = useMagasin();
  const [ouvert, setOuvert] = useState(false);
  const [fiche, setFiche] = useState(FICHE_VIDE);
  const changer = (champ: keyof typeof FICHE_VIDE) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setFiche((f) => ({ ...f, [champ]: e.target.value }));
  const creation = useMutation({
    mutationFn: () =>
      creerEmploye({
        ...fiche,
        magasin,
        solde_conges_initial: fiche.solde_conges_initial || "0",
        utilisateur: fiche.utilisateur || null,
      }),
    onSuccess: () => {
      setFiche(FICHE_VIDE);
      setOuvert(false);
      void queryClient.invalidateQueries({ queryKey: ["employes"] });
    },
  });

  return (
    <Stack spacing={2}>
      {creer && !ouvert && (
        <Button variant="outlined" onClick={() => setOuvert(true)} sx={{ alignSelf: "flex-start" }}>
          Nouvel employé
        </Button>
      )}
      {creer && ouvert && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack spacing={2}>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <TextField label="Nom" value={fiche.nom} onChange={changer("nom")} />
              <TextField label="Prénom" value={fiche.prenom} onChange={changer("prenom")} />
              <TextField label="Poste" value={fiche.poste} onChange={changer("poste")} />
            </Stack>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <ChoixMagasin valeur={magasin} changer={setMagasin} />
              <TextField
                type="date"
                label="Date d'embauche"
                value={fiche.date_embauche}
                onChange={changer("date_embauche")}
                slotProps={{ inputLabel: { shrink: true } }}
              />
              <TextField
                label="Solde de congés de départ"
                value={fiche.solde_conges_initial}
                onChange={changer("solde_conges_initial")}
                helperText="Jours déjà acquis, repris de l'ancien logiciel."
                slotProps={{ htmlInput: { inputMode: "decimal" } }}
              />
            </Stack>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <TextField label="CIN" value={fiche.cin} onChange={changer("cin")} />
              <TextField label="Téléphone" value={fiche.telephone} onChange={changer("telephone")} />
              <TextField
                label="Compte OptiLink"
                value={fiche.utilisateur}
                onChange={changer("utilisateur")}
                helperText="Identifiant de connexion, pour qu'il demande ses congés."
              />
            </Stack>
            {creation.isError && <Alert severity="error">{creation.error.message}</Alert>}
            <Stack direction="row" spacing={2}>
              <Button
                variant="contained"
                onClick={() => creation.mutate()}
                disabled={!fiche.nom || !fiche.prenom || !fiche.poste || !fiche.date_embauche || creation.isPending}
              >
                Créer la fiche
              </Button>
              <Button onClick={() => setOuvert(false)}>Fermer</Button>
            </Stack>
          </Stack>
        </Paper>
      )}
      {employes.data?.length === 0 && <Typography color="text.secondary">Aucun employé pour l'instant.</Typography>}
      {employes.data && employes.data.length > 0 && (
        <Table size="small" aria-label="Employés">
          <TableHead>
            <TableRow>
              <TableCell>Employé</TableCell>
              <TableCell>Embauche</TableCell>
              <TableCell align="right">Congés disponibles</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {employes.data.map((e) => (
              <TableRow key={e.id}>
                <TableCell>
                  {e.prenom} {e.nom}
                  <Typography variant="body2" color="text.secondary">
                    {e.matricule} · {e.poste} · {e.magasin_nom}
                  </Typography>
                </TableCell>
                <TableCell>{jour(e.date_embauche)}</TableCell>
                <TableCell align="right">
                  {jours(e.solde.disponible)}
                  <Typography variant="body2" color="text.secondary">
                    sur {jours(e.solde.acquis)} acquis
                  </Typography>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Stack>
  );
}
