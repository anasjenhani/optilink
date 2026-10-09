import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import MenuItem from "@mui/material/MenuItem";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { enUnites, formater } from "../api/monnaie";
import {
  annulerAcompte,
  annulerMonAcompte,
  annulerPrime,
  deciderAcompte,
  deciderPrime,
  demanderAcompte,
  demanderMonAcompte,
  lireRecap,
  listerAcomptes,
  listerEmployes,
  listerPrimes,
  proposerPrime,
  verserAcompte,
  type Acompte,
  type ModeVersement,
  type Prime,
  type StatutAcompte,
  type StatutPrime,
  type TypePrime,
} from "../api/rh";
import { monnaieDe } from "./Banque";

// Les salaires sont payés dans la devise du pays ; la Tunisie d'abord.
const DINAR = monnaieDe("TND");
const dt = (montant: string | null) => (montant === null ? "—" : formater(enUnites(montant, DINAR.decimales), DINAR));
const moisEnLettres = (iso: string) =>
  new Date(`${iso.slice(0, 7)}-01T00:00:00`).toLocaleDateString("fr-FR", { month: "long", year: "numeric" });
const moisCourant = () => new Date().toLocaleDateString("en-CA").slice(0, 7);

const STATUTS_ACOMPTE: Record<
  StatutAcompte,
  { libelle: string; couleur: "default" | "info" | "warning" | "success" | "error" }
> = {
  demande: { libelle: "En attente", couleur: "info" },
  accorde: { libelle: "Accordé, à verser", couleur: "warning" },
  verse: { libelle: "Versé", couleur: "success" },
  refuse: { libelle: "Refusé", couleur: "error" },
  annule: { libelle: "Annulé", couleur: "default" },
};

const STATUTS_PRIME: Record<StatutPrime, { libelle: string; couleur: "default" | "info" | "success" | "error" }> = {
  proposee: { libelle: "Proposée", couleur: "info" },
  validee: { libelle: "Validée", couleur: "success" },
  refusee: { libelle: "Refusée", couleur: "error" },
  annulee: { libelle: "Annulée", couleur: "default" },
};

const TYPES_PRIME: { valeur: TypePrime; libelle: string }[] = [
  { valeur: "rendement", libelle: "Prime de rendement" },
  { valeur: "objectif", libelle: "Prime d'objectif (ventes)" },
  { valeur: "assiduite", libelle: "Prime d'assiduité" },
  { valeur: "fete", libelle: "Prime de fête (Aïd…)" },
  { valeur: "exceptionnelle", libelle: "Prime exceptionnelle" },
  { valeur: "autre", libelle: "Autre prime" },
];

const MODES: { valeur: ModeVersement; libelle: string }[] = [
  { valeur: "especes", libelle: "Espèces" },
  { valeur: "virement", libelle: "Virement" },
  { valeur: "cheque", libelle: "Chèque" },
];

/** Bouton « Annuler » qui demande confirmation avant d'agir. */
export function BoutonAnnuler({
  titre,
  texte,
  confirmer,
  enCours,
  nom,
}: {
  titre: string;
  texte: string;
  confirmer: () => void;
  enCours: boolean;
  /** Distingue les boutons d'une même liste pour les lecteurs d'écran. */
  nom: string;
}) {
  const [ouvert, setOuvert] = useState(false);
  return (
    <>
      <Button size="small" color="error" onClick={() => setOuvert(true)} aria-label={`Annuler ${nom}`}>
        Annuler
      </Button>
      {ouvert && (
        <Dialog open onClose={() => setOuvert(false)}>
          <DialogTitle>{titre}</DialogTitle>
          <DialogContent>
            <Typography>{texte}</Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setOuvert(false)}>Retour</Button>
            <Button
              variant="contained"
              color="error"
              disabled={enCours}
              onClick={() => {
                confirmer();
                setOuvert(false);
              }}
            >
              Confirmer l'annulation
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </>
  );
}

function TableAcomptes({
  acomptes,
  avecNom = false,
  action,
}: {
  acomptes: Acompte[];
  avecNom?: boolean;
  action?: (acompte: Acompte) => React.ReactNode;
}) {
  return (
    <Table size="small" aria-label="Acomptes">
      <TableBody>
        {acomptes.map((a) => (
          <TableRow key={a.id}>
            <TableCell>
              {avecNom && <strong>{a.employe_nom} · </strong>}
              {dt(a.montant)}
              <Typography variant="body2" color="text.secondary">
                Retenu sur la paie de {moisEnLettres(a.mois)}
                {a.motif && ` · ${a.motif}`}
                {a.verse_le && ` · versé le ${new Date(a.verse_le).toLocaleDateString("fr-FR")}`}
                {a.reference_versement && ` (${a.reference_versement})`}
              </Typography>
              {a.commentaire_decision && (
                <Typography variant="body2">
                  {a.decide_par} : « {a.commentaire_decision} »
                </Typography>
              )}
            </TableCell>
            <TableCell>
              <Chip size="small" color={STATUTS_ACOMPTE[a.statut].couleur} label={STATUTS_ACOMPTE[a.statut].libelle} />
            </TableCell>
            {action && <TableCell>{action(a)}</TableCell>}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function TablePrimes({
  primes,
  avecNom = false,
  action,
}: {
  primes: Prime[];
  avecNom?: boolean;
  action?: (prime: Prime) => React.ReactNode;
}) {
  return (
    <Table size="small" aria-label="Primes">
      <TableBody>
        {primes.map((p) => (
          <TableRow key={p.id}>
            <TableCell>
              {avecNom && <strong>{p.employe_nom} · </strong>}
              {p.type_libelle} · {dt(p.montant)}
              <Typography variant="body2" color="text.secondary">
                Paie de {moisEnLettres(p.mois)} · proposée par {p.proposee_par}
                {p.motif && ` · ${p.motif}`}
              </Typography>
              {p.commentaire_decision && (
                <Typography variant="body2">
                  {p.validee_par} : « {p.commentaire_decision} »
                </Typography>
              )}
            </TableCell>
            <TableCell>
              <Chip size="small" color={STATUTS_PRIME[p.statut].couleur} label={STATUTS_PRIME[p.statut].libelle} />
            </TableCell>
            {action && <TableCell>{action(p)}</TableCell>}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

/** Espace de l'employé : ses acomptes, une nouvelle demande, ses primes validées. */
export function MesAcomptes({
  acomptes,
  primes,
  salaire,
}: {
  acomptes: Acompte[];
  primes: Prime[];
  salaire: string | null;
}) {
  const queryClient = useQueryClient();
  const [montant, setMontant] = useState("");
  const [motif, setMotif] = useState("");
  const demande = useMutation({
    mutationFn: () => demanderMonAcompte({ montant, motif }),
    onSuccess: (espace) => {
      queryClient.setQueryData(["mon-espace-rh"], espace);
      setMontant("");
      setMotif("");
    },
  });
  const annulation = useMutation({
    mutationFn: annulerMonAcompte,
    onSuccess: (espace) => queryClient.setQueryData(["mon-espace-rh"], espace),
  });
  return (
    <Stack spacing={2}>
      <Typography variant="subtitle2">Demander un acompte sur le salaire de ce mois</Typography>
      {salaire && (
        <Typography variant="body2" color="text.secondary">
          Salaire de base {dt(salaire)} : la moitié au plus peut être avancée chaque mois.
        </Typography>
      )}
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <TextField
          label="Montant de l'acompte"
          value={montant}
          onChange={(e) => setMontant(e.target.value)}
          slotProps={{ htmlInput: { inputMode: "decimal" } }}
        />
        <TextField
          label="Motif de l'acompte"
          value={motif}
          onChange={(e) => setMotif(e.target.value)}
          sx={{ flexGrow: 1 }}
        />
      </Stack>
      {demande.isError && <Alert severity="error">{demande.error.message}</Alert>}
      <Button
        variant="contained"
        onClick={() => demande.mutate()}
        disabled={!montant || demande.isPending}
        sx={{ alignSelf: "flex-start" }}
      >
        Demander l'acompte
      </Button>
      {annulation.isError && <Alert severity="error">{annulation.error.message}</Alert>}
      {acomptes.length > 0 && (
        <TableAcomptes
          acomptes={acomptes}
          action={(a) =>
            a.statut === "demande" && (
              <BoutonAnnuler
                nom={`l'acompte de ${dt(a.montant)}`}
                titre="Retirer cette demande d'acompte ?"
                texte={`Votre demande de ${dt(a.montant)} sera annulée ; les RH ne la verront plus à décider.`}
                confirmer={() => annulation.mutate(a.id)}
                enCours={annulation.isPending}
              />
            )
          }
        />
      )}
      {primes.length > 0 && (
        <>
          <Typography variant="subtitle2">Mes primes</Typography>
          <TablePrimes primes={primes} />
        </>
      )}
    </Stack>
  );
}

function ChoixEmploye({ valeur, changer }: { valeur: string; changer: (id: string) => void }) {
  const employes = useQuery({ queryKey: ["employes"], queryFn: listerEmployes });
  return (
    <TextField select label="Employé" value={valeur} onChange={(e) => changer(e.target.value)} sx={{ minWidth: 260 }}>
      {employes.data?.map((e) => (
        <MenuItem key={e.id} value={e.id}>
          {e.prenom} {e.nom} · {e.magasin_nom}
        </MenuItem>
      ))}
    </TextField>
  );
}

function rafraichir(queryClient: ReturnType<typeof useQueryClient>) {
  for (const cle of ["acomptes-rh", "primes-rh", "recap-paie"]) {
    void queryClient.invalidateQueries({ queryKey: [cle] });
  }
}

/** Acomptes du personnel : demande pour un employé, décision et versement par les RH. */
export function Acomptes({
  demander,
  decider,
  annuler = false,
}: {
  demander: boolean;
  decider: boolean;
  annuler?: boolean;
}) {
  const queryClient = useQueryClient();
  const [statut, setStatut] = useState<StatutAcompte | "tous">(decider ? "demande" : "tous");
  const acomptes = useQuery({
    queryKey: ["acomptes-rh", statut],
    queryFn: () => listerAcomptes(statut === "tous" ? undefined : statut),
  });
  const [employe, setEmploye] = useState("");
  const [montant, setMontant] = useState("");
  const [motif, setMotif] = useState("");
  const [commentaires, setCommentaires] = useState<Record<string, string>>({});
  const [versements, setVersements] = useState<Record<string, { mode: ModeVersement; reference: string }>>({});
  const saisie = useMutation({
    mutationFn: () => demanderAcompte({ employe, montant, motif }),
    onSuccess: () => {
      setMontant("");
      setMotif("");
      rafraichir(queryClient);
    },
  });
  const action = useMutation({
    mutationFn: ({ acompte, quoi }: { acompte: Acompte; quoi: "accorder" | "refuser" | "verser" }) => {
      if (quoi === "verser") {
        const v = versements[acompte.id] ?? { mode: "especes", reference: "" };
        return verserAcompte(acompte.id, v.mode, v.reference);
      }
      return deciderAcompte(acompte.id, quoi, commentaires[acompte.id] ?? "");
    },
    onSuccess: () => rafraichir(queryClient),
  });
  const annulation = useMutation({ mutationFn: annulerAcompte, onSuccess: () => rafraichir(queryClient) });
  const boutonAnnuler = (a: Acompte) =>
    annuler &&
    (a.statut === "demande" || a.statut === "accorde") && (
      <BoutonAnnuler
        nom={`l'acompte de ${a.employe_nom}`}
        titre="Annuler cet acompte ?"
        texte={`L'acompte de ${dt(a.montant)} pour ${a.employe_nom} sera annulé : il ne sera ni versé ni retenu sur la paie.`}
        confirmer={() => annulation.mutate(a.id)}
        enCours={annulation.isPending}
      />
    );

  return (
    <Stack spacing={2}>
      {demander && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack spacing={2}>
            <Typography variant="subtitle2">Demander un acompte pour un employé</Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <ChoixEmploye valeur={employe} changer={setEmploye} />
              <TextField
                label="Montant"
                value={montant}
                onChange={(e) => setMontant(e.target.value)}
                slotProps={{ htmlInput: { inputMode: "decimal" } }}
              />
              <TextField label="Motif" value={motif} onChange={(e) => setMotif(e.target.value)} sx={{ flexGrow: 1 }} />
            </Stack>
            {saisie.isError && <Alert severity="error">{saisie.error.message}</Alert>}
            <Button
              variant="contained"
              onClick={() => saisie.mutate()}
              disabled={!employe || !montant || saisie.isPending}
              sx={{ alignSelf: "flex-start" }}
            >
              Enregistrer la demande
            </Button>
          </Stack>
        </Paper>
      )}
      <TextField
        select
        size="small"
        label="Afficher"
        value={statut}
        onChange={(e) => setStatut(e.target.value as StatutAcompte | "tous")}
        sx={{ maxWidth: 220 }}
      >
        <MenuItem value="demande">En attente</MenuItem>
        <MenuItem value="accorde">À verser</MenuItem>
        <MenuItem value="verse">Versés</MenuItem>
        <MenuItem value="tous">Tous</MenuItem>
      </TextField>
      {action.isError && <Alert severity="error">{action.error.message}</Alert>}
      {annulation.isError && <Alert severity="error">{annulation.error.message}</Alert>}
      {acomptes.data?.length === 0 && <Typography color="text.secondary">Aucun acompte.</Typography>}
      {acomptes.data && acomptes.data.length > 0 && (
        <TableAcomptes
          avecNom
          acomptes={acomptes.data}
          action={(a) => {
            if (!decider) return boutonAnnuler(a);
            if (a.statut === "demande") {
              return (
                <Stack spacing={1}>
                  <TextField
                    size="small"
                    label={`Commentaire ${a.employe_nom}`}
                    value={commentaires[a.id] ?? ""}
                    onChange={(e) => setCommentaires((m) => ({ ...m, [a.id]: e.target.value }))}
                    helperText="Obligatoire pour un refus."
                  />
                  <Stack direction="row" spacing={1}>
                    <Button
                      size="small"
                      variant="contained"
                      color="success"
                      onClick={() => action.mutate({ acompte: a, quoi: "accorder" })}
                    >
                      Accorder
                    </Button>
                    <Button
                      size="small"
                      color="error"
                      onClick={() => action.mutate({ acompte: a, quoi: "refuser" })}
                      disabled={!commentaires[a.id]?.trim()}
                    >
                      Refuser
                    </Button>
                    {boutonAnnuler(a)}
                  </Stack>
                </Stack>
              );
            }
            if (a.statut === "accorde") {
              const v = versements[a.id] ?? { mode: "especes" as ModeVersement, reference: "" };
              const changer = (nouveau: Partial<typeof v>) =>
                setVersements((m) => ({ ...m, [a.id]: { ...v, ...nouveau } }));
              return (
                <Stack spacing={1}>
                  <TextField
                    select
                    size="small"
                    label={`Versement ${a.employe_nom}`}
                    value={v.mode}
                    onChange={(e) => changer({ mode: e.target.value as ModeVersement })}
                  >
                    {MODES.map((m) => (
                      <MenuItem key={m.valeur} value={m.valeur}>
                        {m.libelle}
                      </MenuItem>
                    ))}
                  </TextField>
                  {v.mode !== "especes" && (
                    <TextField
                      size="small"
                      label="N° de virement ou de chèque"
                      value={v.reference}
                      onChange={(e) => changer({ reference: e.target.value })}
                    />
                  )}
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => action.mutate({ acompte: a, quoi: "verser" })}
                    disabled={v.mode !== "especes" && !v.reference.trim()}
                  >
                    Marquer versé
                  </Button>
                  {boutonAnnuler(a)}
                </Stack>
              );
            }
            return null;
          }}
        />
      )}
    </Stack>
  );
}

/** Primes : proposées par le responsable, validées par les RH. */
export function Primes({
  proposer,
  valider,
  annuler = false,
}: {
  proposer: boolean;
  valider: boolean;
  annuler?: boolean;
}) {
  const queryClient = useQueryClient();
  const [statut, setStatut] = useState<StatutPrime | "toutes">(valider ? "proposee" : "toutes");
  const primes = useQuery({
    queryKey: ["primes-rh", statut],
    queryFn: () => listerPrimes(statut === "toutes" ? undefined : statut),
  });
  const [saisie, setSaisie] = useState({
    employe: "",
    type: "objectif" as TypePrime,
    montant: "",
    mois: moisCourant(),
    motif: "",
  });
  const [commentaires, setCommentaires] = useState<Record<string, string>>({});
  const proposition = useMutation({
    mutationFn: () => proposerPrime({ ...saisie, mois: `${saisie.mois}-01` }),
    onSuccess: () => {
      setSaisie((s) => ({ ...s, montant: "", motif: "" }));
      rafraichir(queryClient);
    },
  });
  const decision = useMutation({
    mutationFn: ({ prime, choix }: { prime: Prime; choix: "valider" | "refuser" }) =>
      deciderPrime(prime.id, choix, commentaires[prime.id] ?? ""),
    onSuccess: () => rafraichir(queryClient),
  });
  const annulation = useMutation({ mutationFn: annulerPrime, onSuccess: () => rafraichir(queryClient) });

  return (
    <Stack spacing={2}>
      {proposer && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack spacing={2}>
            <Typography variant="subtitle2">Proposer une prime</Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <ChoixEmploye valeur={saisie.employe} changer={(employe) => setSaisie((s) => ({ ...s, employe }))} />
              <TextField
                select
                label="Type de prime"
                value={saisie.type}
                onChange={(e) => setSaisie((s) => ({ ...s, type: e.target.value as TypePrime }))}
                sx={{ minWidth: 220 }}
              >
                {TYPES_PRIME.map((t) => (
                  <MenuItem key={t.valeur} value={t.valeur}>
                    {t.libelle}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <TextField
                label="Montant de la prime"
                value={saisie.montant}
                onChange={(e) => setSaisie((s) => ({ ...s, montant: e.target.value }))}
                slotProps={{ htmlInput: { inputMode: "decimal" } }}
              />
              <TextField
                type="month"
                label="Paie du mois"
                value={saisie.mois}
                onChange={(e) => setSaisie((s) => ({ ...s, mois: e.target.value }))}
                slotProps={{ inputLabel: { shrink: true } }}
              />
              <TextField
                label="Motif de la prime"
                value={saisie.motif}
                onChange={(e) => setSaisie((s) => ({ ...s, motif: e.target.value }))}
                sx={{ flexGrow: 1 }}
              />
            </Stack>
            {proposition.isError && <Alert severity="error">{proposition.error.message}</Alert>}
            <Button
              variant="contained"
              onClick={() => proposition.mutate()}
              disabled={!saisie.employe || !saisie.montant || !saisie.mois || proposition.isPending}
              sx={{ alignSelf: "flex-start" }}
            >
              Proposer la prime
            </Button>
          </Stack>
        </Paper>
      )}
      <TextField
        select
        size="small"
        label="Afficher"
        value={statut}
        onChange={(e) => setStatut(e.target.value as StatutPrime | "toutes")}
        sx={{ maxWidth: 220 }}
      >
        <MenuItem value="proposee">À valider</MenuItem>
        <MenuItem value="validee">Validées</MenuItem>
        <MenuItem value="refusee">Refusées</MenuItem>
        <MenuItem value="toutes">Toutes</MenuItem>
      </TextField>
      {decision.isError && <Alert severity="error">{decision.error.message}</Alert>}
      {annulation.isError && <Alert severity="error">{annulation.error.message}</Alert>}
      {primes.data?.length === 0 && <Typography color="text.secondary">Aucune prime.</Typography>}
      {primes.data && primes.data.length > 0 && (
        <TablePrimes
          avecNom
          primes={primes.data}
          action={(p) =>
            p.statut === "proposee" &&
            (valider || annuler) && (
              <Stack spacing={1}>
                {valider && (
                  <TextField
                    size="small"
                    label={`Commentaire ${p.employe_nom}`}
                    value={commentaires[p.id] ?? ""}
                    onChange={(e) => setCommentaires((m) => ({ ...m, [p.id]: e.target.value }))}
                    helperText="Obligatoire pour un refus."
                  />
                )}
                <Stack direction="row" spacing={1}>
                  {valider && (
                    <>
                      <Button
                        size="small"
                        variant="contained"
                        color="success"
                        onClick={() => decision.mutate({ prime: p, choix: "valider" })}
                      >
                        Valider
                      </Button>
                      <Button
                        size="small"
                        color="error"
                        onClick={() => decision.mutate({ prime: p, choix: "refuser" })}
                        disabled={!commentaires[p.id]?.trim()}
                      >
                        Refuser
                      </Button>
                    </>
                  )}
                  {annuler && (
                    <BoutonAnnuler
                      nom={`la prime de ${p.employe_nom}`}
                      titre="Annuler cette prime ?"
                      texte={`La prime de ${dt(p.montant)} proposée pour ${p.employe_nom} sera retirée : elle ne sera pas versée.`}
                      confirmer={() => annulation.mutate(p.id)}
                      enCours={annulation.isPending}
                    />
                  )}
                </Stack>
              </Stack>
            )
          }
        />
      )}
    </Stack>
  );
}

/** Ce que la paie du mois retiendra (acomptes) et ajoutera (primes), par employé. */
export function RecapPaie() {
  const [mois, setMois] = useState(moisCourant());
  const recap = useQuery({
    queryKey: ["recap-paie", mois],
    queryFn: () => lireRecap(`${mois}-01`),
    enabled: Boolean(mois),
  });
  return (
    <Stack spacing={2}>
      <TextField
        type="month"
        label="Mois de paie"
        value={mois}
        onChange={(e) => setMois(e.target.value)}
        slotProps={{ inputLabel: { shrink: true } }}
        sx={{ maxWidth: 220 }}
      />
      {recap.data?.length === 0 && <Typography color="text.secondary">Aucun employé ce mois-là.</Typography>}
      {recap.data && recap.data.length > 0 && (
        <Table size="small" aria-label="Récapitulatif de paie">
          <TableHead>
            <TableRow>
              <TableCell>Employé</TableCell>
              <TableCell align="right">Salaire de base</TableCell>
              <TableCell align="right">Primes à verser</TableCell>
              <TableCell align="right">Acomptes à retenir</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {recap.data.map((l) => (
              <TableRow key={l.employe}>
                <TableCell>
                  {l.nom}
                  <Typography variant="body2" color="text.secondary">
                    {l.matricule} · {l.magasin}
                  </Typography>
                </TableCell>
                <TableCell align="right">{dt(l.salaire_base)}</TableCell>
                <TableCell align="right">{dt(l.primes)}</TableCell>
                <TableCell align="right">{dt(l.acomptes)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Stack>
  );
}
