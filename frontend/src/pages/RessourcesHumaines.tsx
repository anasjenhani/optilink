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
  annulerConge,
  annulerMonConge,
  creerEmploye,
  deciderConge,
  demanderConge,
  enregistrerPresence,
  lireMonEspace,
  lirePresence,
  listerConges,
  listerEmployes,
  listerTousEmployes,
  modifierEmploye,
  saisirConge,
  type Conge,
  type Employe,
  type LignePresence,
  type SaisieConge,
  type Solde,
  type StatutConge,
  type StatutPointage,
  type TypeConge,
} from "../api/rh";
import { Acomptes, BoutonAnnuler, MesAcomptes, Primes, RecapPaie } from "./Remunerations";

export type DroitsRh = {
  voirEmployes: boolean;
  creerEmploye: boolean;
  /** Corriger une fiche, enregistrer une sortie. */
  modifierEmploye?: boolean;
  voirPresence: boolean;
  pointer: boolean;
  voirConges: boolean;
  saisirConge: boolean;
  deciderConge: boolean;
  /** Annuler une demande en attente ou un congé accepté pas encore commencé. */
  annulerConge?: boolean;
  voirAcomptes?: boolean;
  demanderAcompte?: boolean;
  deciderAcompte?: boolean;
  voirPrimes?: boolean;
  proposerPrime?: boolean;
  validerPrime?: boolean;
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
/** Ce que le serveur accepte encore d'annuler : une demande en attente, un congé accepté pas commencé. */
const annulable = (c: Conge) => c.statut === "demandee" || (c.statut === "acceptee" && c.debut > aujourdhui());

/** Personnel : congés de chacun, présence du jour, décisions et fiches employés. */
export function RessourcesHumaines({ droits, ongletInitial }: { droits: DroitsRh; ongletInitial?: string }) {
  const espace = useQuery({ queryKey: ["mon-espace-rh"], queryFn: lireMonEspace, retry: false });
  const estEmploye = Boolean(espace.data?.employe);
  const onglets = [
    estEmploye && { valeur: "moi", libelle: "Mes congés" },
    droits.voirPresence && { valeur: "presence", libelle: "Présence" },
    droits.voirConges && { valeur: "conges", libelle: "Congés" },
    estEmploye && { valeur: "mes-acomptes", libelle: "Mes acomptes et primes" },
    droits.voirEmployes && { valeur: "employes", libelle: "Employés" },
    droits.voirAcomptes && { valeur: "acomptes", libelle: "Acomptes" },
    droits.voirPrimes && { valeur: "primes", libelle: "Primes" },
    droits.voirAcomptes && droits.voirPrimes && { valeur: "recap", libelle: "Récap paie" },
  ].filter((o): o is { valeur: string; libelle: string } => Boolean(o));
  const [choisi, setOnglet] = useState(ongletInitial ?? "");
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
          {onglet === "moi" && espace.data && (
            <MesConges conges={espace.data.employe.solde} demandes={espace.data.conges} />
          )}
          {onglet === "presence" && <Presence pointer={droits.pointer} />}
          {onglet === "conges" && <Conges droits={droits} />}
          {onglet === "employes" && <Employes creer={droits.creerEmploye} modifier={Boolean(droits.modifierEmploye)} />}
          {onglet === "mes-acomptes" && espace.data && (
            <MesAcomptes
              acomptes={espace.data.acomptes}
              primes={espace.data.primes}
              salaire={espace.data.employe.salaire_base}
            />
          )}
          {onglet === "acomptes" && (
            <Acomptes
              demander={Boolean(droits.demanderAcompte && droits.voirEmployes)}
              decider={Boolean(droits.deciderAcompte)}
              annuler={Boolean(droits.demanderAcompte)}
            />
          )}
          {onglet === "primes" && (
            <Primes
              proposer={Boolean(droits.proposerPrime && droits.voirEmployes)}
              valider={Boolean(droits.validerPrime)}
              annuler={Boolean(droits.proposerPrime)}
            />
          )}
          {onglet === "recap" && <RecapPaie />}
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

function FormulaireConge({
  envoyer,
  enCours,
  erreur,
}: {
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
        <TextField
          type="date"
          label="Du"
          value={demande.debut}
          onChange={changer("debut")}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <TextField
          type="date"
          label="Au"
          value={demande.fin}
          onChange={changer("fin")}
          slotProps={{ inputLabel: { shrink: true } }}
        />
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
        <TableConges
          conges={demandes}
          action={(c) =>
            annulable(c) && (
              <Button size="small" color="error" onClick={() => annulation.mutate(c.id)}>
                Annuler
              </Button>
            )
          }
        />
      )}
    </Stack>
  );
}

function TableConges({
  conges,
  action,
  avecNom = false,
}: {
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
      {feuille.data?.length === 0 && (
        <Typography color="text.secondary">Aucun employé dans ce magasin ce jour-là.</Typography>
      )}
      {feuille.data && feuille.data.length > 0 && (
        <FeuillePresence
          key={`${magasin}-${date}`}
          magasin={magasin}
          date={date}
          lignes={feuille.data}
          pointer={pointer}
        />
      )}
    </Stack>
  );
}

function FeuillePresence({
  magasin,
  date,
  lignes,
  pointer,
}: {
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
                          slotProps={{
                            htmlInput: { "aria-label": `${champ === "arrivee" ? "Arrivée" : "Départ"} ${l.nom}` },
                          }}
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
  const annulation = useMutation({ mutationFn: annulerConge, onSuccess: invalider });
  const boutonAnnuler = (c: Conge) =>
    droits.annulerConge &&
    annulable(c) && (
      <BoutonAnnuler
        nom={`le congé de ${c.employe_nom}`}
        titre="Annuler ce congé ?"
        texte={`${c.type_libelle} de ${c.employe_nom} du ${jour(c.debut)} au ${jour(c.fin)} : ${
          c.statut === "acceptee" ? "les jours seront rendus à son solde." : "la demande sera retirée."
        }`}
        confirmer={() => annulation.mutate(c.id)}
        enCours={annulation.isPending}
      />
    );
  const choisi = employes.data?.find((e) => e.id === employe);

  return (
    <Stack spacing={2}>
      {droits.saisirConge && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack spacing={2}>
            <Typography variant="subtitle2">Saisir un congé pour un employé</Typography>
            <TextField
              select
              label="Employé"
              value={employe}
              onChange={(e) => setEmploye(e.target.value)}
              sx={{ maxWidth: 320 }}
            >
              {employes.data?.map((e) => (
                <MenuItem key={e.id} value={e.id}>
                  {e.prenom} {e.nom} · {e.magasin_nom}
                </MenuItem>
              ))}
            </TextField>
            {choisi && <SoldeConges solde={choisi.solde} />}
            {employe && (
              <FormulaireConge envoyer={(d) => saisie.mutate(d)} enCours={saisie.isPending} erreur={saisie.error} />
            )}
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
        <MenuItem value="annulee">Annulées</MenuItem>
        <MenuItem value="tous">Toutes</MenuItem>
      </TextField>
      {decision.isError && <Alert severity="error">{decision.error.message}</Alert>}
      {annulation.isError && <Alert severity="error">{annulation.error.message}</Alert>}
      {conges.data?.length === 0 && <Typography color="text.secondary">Aucune demande.</Typography>}
      {conges.data && conges.data.length > 0 && (
        <TableConges
          avecNom
          conges={conges.data}
          action={(c) =>
            !(droits.deciderConge && c.statut === "demandee") ? (
              boutonAnnuler(c)
            ) : (
              <Stack spacing={1}>
                <TextField
                  size="small"
                  label={`Commentaire ${c.employe_nom}`}
                  value={commentaires[c.id] ?? ""}
                  onChange={(e) => setCommentaires((m) => ({ ...m, [c.id]: e.target.value }))}
                  helperText="Obligatoire pour un refus."
                />
                <Stack direction="row" spacing={1}>
                  <Button
                    size="small"
                    variant="contained"
                    color="success"
                    onClick={() => decision.mutate({ conge: c, choix: "accepter" })}
                  >
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
                  {boutonAnnuler(c)}
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
  salaire_base: "",
  utilisateur: "",
};

function Employes({ creer, modifier }: { creer: boolean; modifier: boolean }) {
  const queryClient = useQueryClient();
  const [avecSortis, setAvecSortis] = useState(false);
  const employes = useQuery({
    queryKey: avecSortis ? ["employes", "tous"] : ["employes"],
    queryFn: avecSortis ? listerTousEmployes : listerEmployes,
  });
  const [edite, setEdite] = useState<Employe | null>(null);
  const [sortant, setSortant] = useState<Employe | null>(null);
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
        salaire_base: fiche.salaire_base || null,
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
              <TextField
                label="Salaire de base"
                value={fiche.salaire_base}
                onChange={changer("salaire_base")}
                helperText="Brut mensuel."
                slotProps={{ htmlInput: { inputMode: "decimal" } }}
              />
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
      <FormControlLabel
        control={<Checkbox checked={avecSortis} onChange={(e) => setAvecSortis(e.target.checked)} />}
        label="Afficher aussi les employés sortis"
      />
      {employes.data?.length === 0 && <Typography color="text.secondary">Aucun employé pour l'instant.</Typography>}
      {employes.data && employes.data.length > 0 && (
        <Table size="small" aria-label="Employés">
          <TableHead>
            <TableRow>
              <TableCell>Employé</TableCell>
              <TableCell>Embauche</TableCell>
              <TableCell align="right">Congés disponibles</TableCell>
              {modifier && <TableCell />}
            </TableRow>
          </TableHead>
          <TableBody>
            {employes.data.map((e) => (
              <TableRow key={e.id} sx={e.date_sortie ? { opacity: 0.6 } : undefined}>
                <TableCell>
                  {e.prenom} {e.nom}
                  {e.date_sortie && <Chip size="small" label={`Sorti le ${jour(e.date_sortie)}`} sx={{ ml: 1 }} />}
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
                {modifier && (
                  <TableCell align="right">
                    <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end" }}>
                      <Button size="small" onClick={() => setEdite(e)} aria-label={`Modifier ${e.prenom} ${e.nom}`}>
                        Modifier
                      </Button>
                      {!e.date_sortie && (
                        <Button
                          size="small"
                          color="error"
                          onClick={() => setSortant(e)}
                          aria-label={`Sortie de ${e.prenom} ${e.nom}`}
                        >
                          Sortie
                        </Button>
                      )}
                    </Stack>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      {edite && <FicheEmploye key={edite.id} employe={edite} onFerme={() => setEdite(null)} />}
      {sortant && <SortieEmploye key={sortant.id} employe={sortant} onFerme={() => setSortant(null)} />}
    </Stack>
  );
}

function invaliderEmployes(queryClient: ReturnType<typeof useQueryClient>) {
  for (const cle of ["employes", "presence", "recap-paie"]) {
    void queryClient.invalidateQueries({ queryKey: [cle] });
  }
}

/** Correction d'une fiche employé ; la date de sortie se corrige ici une fois enregistrée. */
function FicheEmploye({ employe, onFerme }: { employe: Employe; onFerme: () => void }) {
  const queryClient = useQueryClient();
  const [fiche, setFiche] = useState({
    nom: employe.nom,
    prenom: employe.prenom,
    poste: employe.poste,
    cin: employe.cin,
    telephone: employe.telephone,
    date_embauche: employe.date_embauche,
    date_sortie: employe.date_sortie ?? "",
    conges_par_mois: employe.conges_par_mois,
    solde_conges_initial: employe.solde_conges_initial,
    salaire_base: employe.salaire_base ?? "",
    utilisateur: employe.utilisateur ?? "",
  });
  const [magasin, setMagasin] = useState(employe.magasin);
  const changer = (champ: keyof typeof fiche) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setFiche((f) => ({ ...f, [champ]: e.target.value }));
  const enregistrement = useMutation({
    mutationFn: () =>
      modifierEmploye(employe.id, {
        ...fiche,
        magasin,
        date_sortie: fiche.date_sortie || null,
        conges_par_mois: fiche.conges_par_mois || "0",
        solde_conges_initial: fiche.solde_conges_initial || "0",
        salaire_base: fiche.salaire_base || null,
        utilisateur: fiche.utilisateur || null,
      }),
    onSuccess: () => {
      invaliderEmployes(queryClient);
      onFerme();
    },
  });
  return (
    <Dialog open onClose={onFerme} maxWidth="md" fullWidth>
      <DialogTitle>
        Fiche de {employe.prenom} {employe.nom} · {employe.matricule}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
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
            {employe.date_sortie && (
              <TextField
                type="date"
                label="Date de sortie"
                value={fiche.date_sortie}
                onChange={changer("date_sortie")}
                helperText="Videz-la pour le remettre dans l'effectif."
                slotProps={{ inputLabel: { shrink: true } }}
              />
            )}
          </Stack>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField
              label="Salaire de base"
              value={fiche.salaire_base}
              onChange={changer("salaire_base")}
              helperText="Brut mensuel."
              slotProps={{ htmlInput: { inputMode: "decimal" } }}
            />
            <TextField
              label="Jours de congé par mois"
              value={fiche.conges_par_mois}
              onChange={changer("conges_par_mois")}
              slotProps={{ htmlInput: { inputMode: "decimal" } }}
            />
            <TextField
              label="Solde de congés de départ"
              value={fiche.solde_conges_initial}
              onChange={changer("solde_conges_initial")}
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
              helperText="Identifiant de connexion."
            />
          </Stack>
          {enregistrement.isError && <Alert severity="error">{enregistrement.error.message}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onFerme}>Fermer</Button>
        <Button
          variant="contained"
          onClick={() => enregistrement.mutate()}
          disabled={!fiche.nom || !fiche.prenom || !fiche.poste || !fiche.date_embauche || enregistrement.isPending}
        >
          Enregistrer
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/** Départ d'un employé : sa fiche reste, il sort de l'effectif (présence, listes, paie) après cette date. */
function SortieEmploye({ employe, onFerme }: { employe: Employe; onFerme: () => void }) {
  const queryClient = useQueryClient();
  const [date, setDate] = useState(aujourdhui());
  const sortie = useMutation({
    mutationFn: () => modifierEmploye(employe.id, { date_sortie: date }),
    onSuccess: () => {
      invaliderEmployes(queryClient);
      onFerme();
    },
  });
  return (
    <Dialog open onClose={onFerme}>
      <DialogTitle>
        Sortie de {employe.prenom} {employe.nom}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <Typography>
            Sa fiche et son historique sont conservés. Il quitte les listes du personnel (affichez les employés sortis
            pour le retrouver) et, après cette date, la feuille de présence.
          </Typography>
          <TextField
            type="date"
            label="Dernier jour dans l'effectif"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            slotProps={{ inputLabel: { shrink: true }, htmlInput: { min: employe.date_embauche } }}
          />
          {sortie.isError && <Alert severity="error">{sortie.error.message}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onFerme}>Retour</Button>
        <Button variant="contained" color="error" onClick={() => sortie.mutate()} disabled={!date || sortie.isPending}>
          Enregistrer la sortie
        </Button>
      </DialogActions>
    </Dialog>
  );
}
