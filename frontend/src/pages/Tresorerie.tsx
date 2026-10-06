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
import { enUnites, formater } from "../api/monnaie";
import {
  cloturer,
  corriger,
  listerClotures,
  listerDepensesOuvertes,
  lireSituation,
  saisirDepense,
  corrigerDepense,
  supprimerDepense,
  type Depense,
  verifierCloture,
  type CategorieDepense,
  type Cloture,
  type Comptage,
  type StatutCloture,
} from "../api/tresorerie";
import { Banque, monnaieDe, Versements } from "./Banque";

export type DroitsTresorerie = {
  cloturer: boolean;
  depenses: boolean;
  verifier: boolean;
  voirClotures: boolean;
  /** Déposer l'argent des clôtures validées, prévoir les versements. */
  versements?: boolean;
  /** Voir les comptes et les opérations. */
  banque?: boolean;
  rapprocher?: boolean;
  gererComptes?: boolean;
  modifierComptes?: boolean;
};

const STATUTS: Record<StatutCloture, { libelle: string; couleur: "info" | "success" | "error" }> = {
  envoyee: { libelle: "À vérifier", couleur: "info" },
  validee: { libelle: "Validée", couleur: "success" },
  rejetee: { libelle: "Rejetée", couleur: "error" },
};

const CATEGORIES: { valeur: CategorieDepense; libelle: string }[] = [
  { valeur: "fournitures", libelle: "Fournitures" },
  { valeur: "entretien", libelle: "Entretien et nettoyage" },
  { valeur: "transport", libelle: "Transport et courses" },
  { valeur: "restauration", libelle: "Restauration" },
  { valeur: "divers", libelle: "Divers" },
];

const dateHeure = (iso: string) => new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });

/** Caisse et banque : clôture quotidienne vérifiée par la finance, puis dépôt jusqu'à la banque. */
export function Tresorerie({ droits, ongletInitial }: { droits: DroitsTresorerie; ongletInitial?: string }) {
  const onglets = [
    droits.cloturer && { valeur: "cloture", libelle: "Clôture de caisse" },
    droits.depenses && { valeur: "depenses", libelle: "Dépenses de caisse" },
    droits.verifier && { valeur: "verifier", libelle: "À vérifier" },
    droits.voirClotures && { valeur: "historique", libelle: "Clôtures" },
    droits.versements && { valeur: "versements", libelle: "Versements" },
    droits.banque && { valeur: "banque", libelle: "Banque" },
  ].filter((o): o is { valeur: string; libelle: string } => Boolean(o));
  const [onglet, setOnglet] = useState(
    onglets.find((o) => o.valeur === ongletInitial)?.valeur ?? onglets[0]?.valeur ?? "historique",
  );
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = magasinChoisi || magasins.data?.[0]?.id || "";
  const parMagasin = onglet === "cloture" || onglet === "depenses";

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Trésorerie
          </Typography>
          <Tabs value={onglet} onChange={(_, valeur: string) => setOnglet(valeur)} variant="scrollable">
            {onglets.map((o) => (
              <Tab key={o.valeur} value={o.valeur} label={o.libelle} />
            ))}
          </Tabs>
          {parMagasin && (
            <TextField
              select
              label="Magasin"
              value={magasin}
              onChange={(e) => setMagasin(e.target.value)}
              sx={{ maxWidth: 260 }}
            >
              {magasins.data?.map((m) => (
                <MenuItem key={m.id} value={m.id}>
                  {m.nom}
                </MenuItem>
              ))}
            </TextField>
          )}
          {onglet === "cloture" && magasin && <ClotureDeCaisse key={magasin} magasin={magasin} />}
          {onglet === "depenses" && magasin && <Depenses key={magasin} magasin={magasin} />}
          {onglet === "verifier" && <AVerifier />}
          {onglet === "historique" && <Historique />}
          {onglet === "versements" && <Versements />}
          {onglet === "banque" && (
            <Banque
              droits={{
                gererComptes: Boolean(droits.gererComptes),
                rapprocher: Boolean(droits.rapprocher),
                operations: Boolean(droits.gererComptes && droits.versements),
                modifierComptes: Boolean(droits.modifierComptes),
              }}
            />
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}

const COMPTAGE_VIDE = {
  especes_comptees: "",
  cheques_comptes: "",
  nombre_cheques_comptes: "",
  cartes_comptees: "",
  fond_conserve: "",
  commentaire_caissier: "",
};

function ClotureDeCaisse({ magasin }: { magasin: string }) {
  const queryClient = useQueryClient();
  const situation = useQuery({ queryKey: ["situation-caisse", magasin], queryFn: () => lireSituation(magasin) });
  const rejetee = useQuery({
    queryKey: ["clotures", "rejetee", magasin],
    queryFn: () => listerClotures({ statut: "rejetee", magasin }).then((liste) => liste[0] ?? null),
    enabled: Boolean(situation.data?.cloture_rejetee),
  });
  const [saisie, setSaisie] = useState(COMPTAGE_VIDE);
  const [message, setMessage] = useState("");

  const comptage = (): Comptage => ({
    especes_comptees: saisie.especes_comptees || "0",
    cheques_comptes: saisie.cheques_comptes || "0",
    nombre_cheques_comptes: Number(saisie.nombre_cheques_comptes || 0),
    cartes_comptees: saisie.cartes_comptees || "0",
    fond_conserve: saisie.fond_conserve || "0",
    commentaire_caissier: saisie.commentaire_caissier,
  });
  const envoi = useMutation({
    mutationFn: () => (rejetee.data ? corriger(rejetee.data.id, comptage()) : cloturer(magasin, comptage())),
    onSuccess: (cloture) => {
      setMessage(`Clôture ${cloture.numero} envoyée à la finance pour vérification.`);
      setSaisie(COMPTAGE_VIDE);
      void queryClient.invalidateQueries({ queryKey: ["situation-caisse"] });
      void queryClient.invalidateQueries({ queryKey: ["clotures"] });
      void queryClient.invalidateQueries({ queryKey: ["depenses"] });
    },
  });

  if (!situation.data) return situation.isError ? <Alert severity="error">{situation.error.message}</Alert> : null;
  if (situation.data.cloture_rejetee && !rejetee.data) return null;

  // Après un rejet, on recompte la période de la clôture rejetée, pas la caisse du moment.
  const base = rejetee.data ?? situation.data;
  const monnaie = monnaieDe(base.devise);
  const u = (montant: string) => enUnites(montant || "0", monnaie.decimales);
  const lignes = [
    {
      mode: "Espèces",
      compte: "Espèces comptées",
      attendu: base.especes_attendues,
      champ: "especes_comptees" as const,
    },
    {
      mode: `Chèques (${base.nombre_cheques})`,
      compte: "Chèques comptés",
      attendu: base.cheques_attendus,
      champ: "cheques_comptes" as const,
    },
    {
      mode: "Cartes bancaires",
      compte: "Total des tickets carte",
      attendu: base.cartes_attendues,
      champ: "cartes_comptees" as const,
    },
  ];
  const changer = (champ: keyof typeof COMPTAGE_VIDE) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setSaisie((s) => ({ ...s, [champ]: e.target.value }));

  return (
    <Stack spacing={2}>
      {message && <Alert severity="success">{message}</Alert>}
      {rejetee.data && (
        <Alert severity="error">
          La clôture {rejetee.data.numero} a été rejetée par {rejetee.data.verifiee_par} : «{" "}
          {rejetee.data.commentaire_finance} ». Recomptez et renvoyez-la.
        </Alert>
      )}
      <Typography color="text.secondary">
        {base.debut ? `Depuis la clôture du ${dateHeure(base.debut)}` : "Depuis l'ouverture de la caisse"}
        {rejetee.data && ` jusqu'au ${dateHeure(rejetee.data.fin)}`}
      </Typography>
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle2">Dans la caisse, OptiLink attend</Typography>
        <Typography variant="body2" color="text.secondary">
          Fond de caisse {formater(u(base.fond_initial), monnaie)}
          {u(base.alimentations) > 0 && ` + alimentation ${formater(u(base.alimentations), monnaie)}`} + espèces
          encaissées {formater(u(base.encaisse_especes), monnaie)} − remboursements{" "}
          {formater(u(base.rembourse_especes), monnaie)} − dépenses {formater(u(base.depenses), monnaie)}
        </Typography>
      </Paper>
      <Table size="small" aria-label="Comptage de la caisse">
        <TableHead>
          <TableRow>
            <TableCell>Mode</TableCell>
            <TableCell align="right">Attendu</TableCell>
            <TableCell>Compté</TableCell>
            <TableCell align="right">Écart</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {lignes.map((l) => {
            const ecart = u(saisie[l.champ]) - u(l.attendu);
            return (
              <TableRow key={l.champ}>
                <TableCell>{l.mode}</TableCell>
                <TableCell align="right">{formater(u(l.attendu), monnaie)}</TableCell>
                <TableCell>
                  <TextField
                    size="small"
                    label={l.compte}
                    value={saisie[l.champ]}
                    onChange={changer(l.champ)}
                    slotProps={{ htmlInput: { inputMode: "decimal" } }}
                  />
                </TableCell>
                <TableCell align="right" sx={{ color: ecart === 0 ? "success.main" : "error.main" }}>
                  {saisie[l.champ] ? formater(ecart, monnaie) : "—"}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <TextField
          label="Nombre de chèques"
          value={saisie.nombre_cheques_comptes}
          onChange={changer("nombre_cheques_comptes")}
          slotProps={{ htmlInput: { inputMode: "numeric" } }}
        />
        <TextField
          label="Fond laissé en caisse"
          value={saisie.fond_conserve}
          onChange={changer("fond_conserve")}
          helperText="Espèces gardées pour demain."
          slotProps={{ htmlInput: { inputMode: "decimal" } }}
        />
        <Typography sx={{ alignSelf: "center" }}>
          Espèces à remettre : {formater(u(saisie.especes_comptees) - u(saisie.fond_conserve), monnaie)}
        </Typography>
      </Stack>
      <TextField
        label="Commentaire pour la finance"
        value={saisie.commentaire_caissier}
        onChange={changer("commentaire_caissier")}
        multiline
        minRows={2}
      />
      {envoi.isError && <Alert severity="error">{envoi.error.message}</Alert>}
      <Button
        variant="contained"
        onClick={() => envoi.mutate()}
        disabled={envoi.isPending || !saisie.especes_comptees}
        sx={{ alignSelf: "flex-start" }}
      >
        {rejetee.data ? "Renvoyer la clôture corrigée" : "Clôturer et envoyer à la finance"}
      </Button>
    </Stack>
  );
}

function Depenses({ magasin }: { magasin: string }) {
  const queryClient = useQueryClient();
  const depenses = useQuery({ queryKey: ["depenses", magasin], queryFn: () => listerDepensesOuvertes(magasin) });
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const pays = magasins.data?.find((m) => m.id === magasin)?.pays;
  const monnaie = pays ? { devise: pays.devise, decimales: pays.decimales } : monnaieDe("TND");
  const [categorie, setCategorie] = useState<CategorieDepense>("fournitures");
  const [motif, setMotif] = useState("");
  const [beneficiaire, setBeneficiaire] = useState("");
  const [montant, setMontant] = useState("");
  // Dépense en cours de correction (le formulaire la reprend), ou à supprimer (confirmation).
  const [enCorrection, setEnCorrection] = useState<Depense | null>(null);
  const [aSupprimer, setASupprimer] = useState<string | null>(null);
  const rafraichir = () => {
    void queryClient.invalidateQueries({ queryKey: ["depenses"] });
    void queryClient.invalidateQueries({ queryKey: ["situation-caisse"] });
  };
  const vider = () => {
    setEnCorrection(null);
    setCategorie("fournitures");
    setMotif("");
    setBeneficiaire("");
    setMontant("");
  };

  const saisie = useMutation({
    mutationFn: () =>
      enCorrection
        ? corrigerDepense(enCorrection.id, { categorie, motif, beneficiaire, montant })
        : saisirDepense({ magasin_id: magasin, categorie, motif, beneficiaire, montant }),
    onSuccess: () => {
      vider();
      rafraichir();
    },
  });
  const suppression = useMutation({
    mutationFn: (id: string) => supprimerDepense(id),
    onSuccess: () => {
      setASupprimer(null);
      rafraichir();
    },
  });
  const corriger = (d: Depense) => {
    setEnCorrection(d);
    setCategorie(d.categorie);
    setMotif(d.motif);
    setBeneficiaire(d.beneficiaire);
    setMontant(d.montant);
  };

  return (
    <Stack spacing={2}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <TextField
          select
          label="Catégorie"
          value={categorie}
          onChange={(e) => setCategorie(e.target.value as CategorieDepense)}
          sx={{ minWidth: 200 }}
        >
          {CATEGORIES.map((c) => (
            <MenuItem key={c.valeur} value={c.valeur}>
              {c.libelle}
            </MenuItem>
          ))}
        </TextField>
        <TextField label="Motif" value={motif} onChange={(e) => setMotif(e.target.value)} sx={{ flexGrow: 1 }} />
        <TextField label="Bénéficiaire" value={beneficiaire} onChange={(e) => setBeneficiaire(e.target.value)} />
        <TextField
          label="Montant"
          value={montant}
          onChange={(e) => setMontant(e.target.value)}
          slotProps={{ htmlInput: { inputMode: "decimal" } }}
          sx={{ maxWidth: 140 }}
        />
      </Stack>
      {saisie.isError && <Alert severity="error">{saisie.error.message}</Alert>}
      {suppression.isError && <Alert severity="error">{suppression.error.message}</Alert>}
      <Stack direction="row" spacing={1}>
        <Button variant="contained" onClick={() => saisie.mutate()} disabled={!motif || !montant || saisie.isPending}>
          {enCorrection ? "Enregistrer la correction" : "Enregistrer la dépense"}
        </Button>
        {enCorrection && <Button onClick={vider}>Abandonner la correction</Button>}
      </Stack>
      <Typography variant="subtitle2">Dépenses depuis la dernière clôture</Typography>
      {depenses.data?.length === 0 && <Typography color="text.secondary">Aucune dépense.</Typography>}
      {depenses.data && depenses.data.length > 0 && (
        <Table size="small" aria-label="Dépenses de caisse">
          <TableBody>
            {depenses.data.map((d) => (
              <TableRow key={d.id}>
                <TableCell>{dateHeure(d.payee_le)}</TableCell>
                <TableCell>
                  {d.motif}
                  <Typography variant="body2" color="text.secondary">
                    {CATEGORIES.find((c) => c.valeur === d.categorie)?.libelle}
                    {d.beneficiaire && ` · ${d.beneficiaire}`} · {d.saisie_par}
                  </Typography>
                </TableCell>
                <TableCell align="right">{formater(enUnites(d.montant, monnaie.decimales), monnaie)}</TableCell>
                <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                  {aSupprimer === d.id ? (
                    <>
                      Supprimer ?{" "}
                      <Button
                        size="small"
                        color="error"
                        disabled={suppression.isPending}
                        onClick={() => suppression.mutate(d.id)}
                      >
                        Oui
                      </Button>
                      <Button size="small" onClick={() => setASupprimer(null)}>
                        Non
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button size="small" onClick={() => corriger(d)} aria-label={`Modifier ${d.motif}`}>
                        Modifier
                      </Button>
                      <Button
                        size="small"
                        color="error"
                        onClick={() => setASupprimer(d.id)}
                        aria-label={`Supprimer ${d.motif}`}
                      >
                        Supprimer
                      </Button>
                    </>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Stack>
  );
}

function DetailCloture({ cloture }: { cloture: Cloture }) {
  const monnaie = monnaieDe(cloture.devise);
  const f = (montant: string) => formater(enUnites(montant, monnaie.decimales), monnaie);
  const lignes = [
    ["Espèces", cloture.especes_attendues, cloture.especes_comptees, cloture.ecart_especes],
    [
      `Chèques (${cloture.nombre_cheques_comptes}/${cloture.nombre_cheques})`,
      cloture.cheques_attendus,
      cloture.cheques_comptes,
      cloture.ecart_cheques,
    ],
    ["Cartes bancaires", cloture.cartes_attendues, cloture.cartes_comptees, cloture.ecart_cartes],
  ];
  return (
    <Stack spacing={1}>
      <Table size="small" aria-label={`Clôture ${cloture.numero}`}>
        <TableHead>
          <TableRow>
            <TableCell>Mode</TableCell>
            <TableCell align="right">Attendu</TableCell>
            <TableCell align="right">Compté</TableCell>
            <TableCell align="right">Écart</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {lignes.map(([mode, attendu, compte, ecart]) => (
            <TableRow key={mode}>
              <TableCell>{mode}</TableCell>
              <TableCell align="right">{f(attendu)}</TableCell>
              <TableCell align="right">{f(compte)}</TableCell>
              <TableCell align="right" sx={{ color: Number(ecart) === 0 ? "success.main" : "error.main" }}>
                {f(ecart)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <Typography variant="body2">
        Dépenses {f(cloture.depenses)} · fond laissé {f(cloture.fond_conserve)} · espèces à remettre{" "}
        <strong>{f(cloture.especes_a_remettre)}</strong>
      </Typography>
      {cloture.commentaire_caissier && (
        <Typography variant="body2">Caissier : « {cloture.commentaire_caissier} »</Typography>
      )}
      {cloture.commentaire_finance && (
        <Typography variant="body2">Finance : « {cloture.commentaire_finance} »</Typography>
      )}
    </Stack>
  );
}

function AVerifier() {
  const clotures = useQuery({
    queryKey: ["clotures", "envoyee"],
    queryFn: () => listerClotures({ statut: "envoyee" }),
  });
  if (clotures.data?.length === 0) return <Typography color="text.secondary">Aucune clôture à vérifier.</Typography>;
  return (
    <Stack spacing={2}>
      {clotures.data?.map((c) => (
        <Verification key={c.id} cloture={c} />
      ))}
    </Stack>
  );
}

function Verification({ cloture }: { cloture: Cloture }) {
  const queryClient = useQueryClient();
  const [commentaire, setCommentaire] = useState("");
  const decision = useMutation({
    mutationFn: (choix: "valider" | "rejeter") => verifierCloture(cloture.id, choix, commentaire),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["clotures"] }),
  });
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack spacing={1.5}>
        <Typography variant="subtitle1">
          {cloture.numero} · {cloture.magasin}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Clôturée par {cloture.cloturee_par} le {dateHeure(cloture.fin)}
        </Typography>
        <DetailCloture cloture={cloture} />
        <TextField
          size="small"
          label={`Commentaire ${cloture.numero}`}
          value={commentaire}
          onChange={(e) => setCommentaire(e.target.value)}
          helperText="Obligatoire pour un rejet."
        />
        {decision.isError && <Alert severity="error">{decision.error.message}</Alert>}
        <Stack direction="row" spacing={2}>
          <Button
            variant="contained"
            color="success"
            onClick={() => decision.mutate("valider")}
            disabled={decision.isPending}
          >
            Valider
          </Button>
          <Button
            color="error"
            onClick={() => decision.mutate("rejeter")}
            disabled={decision.isPending || !commentaire.trim()}
          >
            Rejeter
          </Button>
        </Stack>
      </Stack>
    </Paper>
  );
}

function Historique() {
  const clotures = useQuery({ queryKey: ["clotures", "toutes"], queryFn: () => listerClotures() });
  const [ouverte, setOuverte] = useState<string | null>(null);
  if (clotures.data?.length === 0) return <Typography color="text.secondary">Aucune clôture.</Typography>;
  return (
    <Table size="small" aria-label="Clôtures de caisse">
      <TableHead>
        <TableRow>
          <TableCell>Clôture</TableCell>
          <TableCell>Caissier</TableCell>
          <TableCell align="right">Écart espèces</TableCell>
          <TableCell>Statut</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {clotures.data?.flatMap((c) => {
          const monnaie = monnaieDe(c.devise);
          const lignes = [
            <TableRow
              key={c.id}
              hover
              onClick={() => setOuverte(ouverte === c.id ? null : c.id)}
              sx={{ cursor: "pointer" }}
            >
              <TableCell>
                {c.numero}
                <Typography variant="body2" color="text.secondary">
                  {c.magasin} · {dateHeure(c.fin)}
                </Typography>
              </TableCell>
              <TableCell>{c.cloturee_par}</TableCell>
              <TableCell align="right">{formater(enUnites(c.ecart_especes, monnaie.decimales), monnaie)}</TableCell>
              <TableCell>
                <Chip size="small" color={STATUTS[c.statut].couleur} label={STATUTS[c.statut].libelle} />
                {c.verifiee_par && (
                  <Typography variant="body2" color="text.secondary">
                    par {c.verifiee_par}
                  </Typography>
                )}
              </TableCell>
            </TableRow>,
          ];
          if (ouverte === c.id) {
            lignes.push(
              <TableRow key={`${c.id}-detail`}>
                <TableCell colSpan={4}>
                  <DetailCloture cloture={c} />
                </TableCell>
              </TableRow>,
            );
          }
          return lignes;
        })}
      </TableBody>
    </Table>
  );
}
