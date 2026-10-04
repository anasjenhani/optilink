import ContentCopy from "@mui/icons-material/ContentCopy";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import IconButton from "@mui/material/IconButton";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listerLentillesClient, type Article, type SaisieLentilles } from "../api/caisse";
import { listerPrescriptions, saisirPrescription, type Client, type MesureOeil } from "../api/clients";
import { enUnites, formater, type Monnaie } from "../api/monnaie";
import { Cadre, Champ, ChoixArticle, NOUVELLE, signe } from "./FicheLunette";

/** Lentille d'un œil telle qu'elle part au panier. */
export type LentilleChoisie = {
  article: Article;
  role: "lentille_d" | "lentille_g";
  quantite: number;
  remise_pct: string;
  numero_lot: string;
  date_peremption: string;
};

const BORDEAUX = "#8b1414";

type Correction = { sphere: string; cylindre: string; axe: string; addition: string; rayon: string; diametre: string };
const VIDE: Correction = { sphere: "", cylindre: "", axe: "", addition: "", rayon: "", diametre: "" };
const versCorrection = (m: MesureOeil): Correction => ({
  sphere: m.sphere ?? "",
  cylindre: m.cylindre ?? "",
  axe: m.axe == null ? "" : String(m.axe),
  addition: m.addition ?? "",
  rayon: m.rayon ?? "",
  diametre: m.diametre ?? "",
});

type Oeil = { article: Article | null; quantite: string; remise: string; lot: string; peremption: string };
const OEIL_VIDE: Oeil = { article: null, quantite: "1", remise: "", lot: "", peremption: "" };

function CorrectionOeil({
  titre,
  correction,
  onChange,
  saisieLibre,
}: {
  titre: string;
  correction: Correction;
  onChange: (c: Correction) => void;
  saisieLibre: boolean;
}) {
  const champ = (cle: keyof Correction, label: string, avecSigne = true) => (
    <Champ
      largeur={cle === "diametre" ? 92 : 72}
      label={label}
      valeur={avecSigne ? signe(correction[cle]) : correction[cle]}
      onChange={(v) => onChange({ ...correction, [cle]: v })}
      lectureSeule={!saisieLibre}
    />
  );
  return (
    <Cadre titre={titre}>
      <Stack direction="row" useFlexGap spacing={1} sx={{ flexWrap: "wrap" }}>
        {champ("sphere", "Sph")}
        {champ("cylindre", "Cyl")}
        {champ("axe", "Axe", false)}
        {champ("addition", "Add")}
        {champ("rayon", "Rayon", false)}
        {champ("diametre", "Diamètre", false)}
      </Stack>
    </Cadre>
  );
}

/**
 * Fiche « Lentilles » : la correction de lentilles (ordonnance reprise ou saisie, avec rayon et
 * diamètre), la lentille de chaque œil avec quantité, n° de lot, péremption et remise.
 * « Valider les lentilles » les ajoute à la visite ; les produits se cherchent en dessous.
 */
export function FicheLentilles({
  magasin,
  client,
  monnaie,
  numero,
  droits,
  onValider,
}: {
  magasin: string;
  client: Client | null;
  monnaie: Monnaie;
  numero: number;
  droits: { remise: boolean; voirOrdonnances: boolean; saisirOrdonnance: boolean };
  onValider: (lentilles: SaisieLentilles, choisies: LentilleChoisie[]) => void;
}) {
  const ordonnances = useQuery({
    queryKey: ["prescriptions", client?.id],
    queryFn: () => listerPrescriptions(client!.id),
    enabled: Boolean(client) && droits.voirOrdonnances,
  });
  const deja = useQuery({
    queryKey: ["lentilles", client?.id],
    queryFn: () => listerLentillesClient(client!.id),
    enabled: Boolean(client),
  });
  const ordonnancesLentilles = (ordonnances.data ?? []).filter((o) => o.type === "lentilles");

  const [ordonnance, setOrdonnance] = useState("");
  const [prescripteur, setPrescripteur] = useState("");
  const [dateOrdonnance, setDateOrdonnance] = useState("");
  const [od, setOd] = useState<Correction>(VIDE);
  const [og, setOg] = useState<Correction>(VIDE);
  const [droite, setDroite] = useState<Oeil>(OEIL_VIDE);
  const [gauche, setGauche] = useState<Oeil>(OEIL_VIDE);
  const [observation, setObservation] = useState("");
  const [erreur, setErreur] = useState("");
  const [envoi, setEnvoi] = useState(false);
  const saisieLibre = ordonnance === NOUVELLE;

  const avantRemise = (o: Oeil) =>
    o.article ? enUnites(o.article.prix_vente_ttc, monnaie.decimales) * Number(o.quantite || 0) : 0;
  const prix = (o: Oeil) => Math.round(avantRemise(o) * (1 - Number(o.remise || 0) / 100));

  function choisirOrdonnance(id: string) {
    setOrdonnance(id);
    const choisie = ordonnancesLentilles.find((o) => o.id === id);
    setOd(choisie ? versCorrection(choisie.mesures.od) : VIDE);
    setOg(choisie ? versCorrection(choisie.mesures.og) : VIDE);
  }

  async function valider() {
    setErreur("");
    if (!droite.article && !gauche.article) return setErreur("Choisir au moins une lentille.");
    if (!ordonnance)
      return setErreur(
        client
          ? "Choisir l'ordonnance de lentilles du client, ou en saisir une nouvelle."
          : "Choisir d'abord le client : la correction va sur sa fiche.",
      );
    if (saisieLibre && (!prescripteur || !dateOrdonnance || !od.sphere || !og.sphere))
      return setErreur("Nouvelle ordonnance : ophtalmologiste, date et sphère de chaque œil.");
    setEnvoi(true);
    try {
      let prescription = ordonnance;
      if (saisieLibre) {
        const oeil = (c: Correction) => ({
          sphere: c.sphere || "0",
          cylindre: c.cylindre || "0",
          axe: c.axe ? Number(c.axe) : null,
          addition: c.addition || null,
          rayon: c.rayon || null,
          diametre: c.diametre || null,
        });
        prescription = (
          await saisirPrescription({
            client: client!.id,
            magasin_saisie: magasin,
            type: "lentilles",
            date_prescription: dateOrdonnance,
            prescripteur,
            prescripteur_identifiant: "",
            mesures: { od: oeil(od), og: oeil(og) },
          })
        ).id;
      }
      const choisies: LentilleChoisie[] = [];
      for (const [o, role] of [
        [droite, "lentille_d"],
        [gauche, "lentille_g"],
      ] as const) {
        if (o.article)
          choisies.push({
            article: o.article,
            role,
            quantite: Math.max(1, Number(o.quantite) || 1),
            remise_pct: o.remise || "0",
            numero_lot: o.lot,
            date_peremption: o.peremption,
          });
      }
      onValider({ prescription, observation }, choisies);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setEnvoi(false);
    }
  }

  const ligne = (titre: string, couleur: string, o: Oeil, changer: (o: Oeil) => void, copier?: () => void) => (
    <Stack direction="row" useFlexGap spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
      <Typography sx={{ width: 96, fontWeight: 700, color: couleur }}>{titre}</Typography>
      <ChoixArticle
        magasin={magasin}
        famille="lentille"
        label="Désignation"
        valeur={o.article}
        onChange={(article) => changer({ ...o, article })}
        monnaie={monnaie}
      />
      {copier && (
        <Tooltip title="Même lentille que l'œil droit">
          <IconButton aria-label="Copier la lentille droite" onClick={copier}>
            <ContentCopy />
          </IconButton>
        </Tooltip>
      )}
      <Champ label="Qté" valeur={o.quantite} onChange={(v) => changer({ ...o, quantite: v })} largeur={60} />
      <TextField
        size="small"
        type="date"
        label="Date pér."
        value={o.peremption}
        onChange={(e) => changer({ ...o, peremption: e.target.value })}
        slotProps={{ inputLabel: { shrink: true } }}
        sx={{ width: 160, bgcolor: "#fffde7" }}
      />
      <Champ label="N° lot" valeur={o.lot} onChange={(v) => changer({ ...o, lot: v })} largeur={120} />
      <Champ label="Avant remise" valeur={formater(avantRemise(o), monnaie)} largeur={128} lectureSeule />
      {droits.remise && (
        <Champ label="Rem. %" valeur={o.remise} onChange={(v) => changer({ ...o, remise: v })} largeur={92} />
      )}
      <Champ label="Prix" valeur={formater(prix(o), monnaie)} largeur={128} lectureSeule />
    </Stack>
  );

  return (
    <Stack spacing={2} aria-label="Lentilles">
      <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ alignItems: { md: "flex-start" } }}>
        <Stack spacing={1.5} sx={{ flex: 1 }}>
          <Typography variant="h6" component="h3" sx={{ color: BORDEAUX }}>
            Lentilles n° {numero}
          </Typography>
          {droits.voirOrdonnances ? (
            <TextField
              select
              size="small"
              label="Ordonnance de lentilles"
              value={ordonnance}
              onChange={(e) => choisirOrdonnance(e.target.value)}
              disabled={!client}
              helperText={client ? undefined : "Choisir un client pour reprendre ou saisir son ordonnance"}
            >
              <MenuItem value="">–</MenuItem>
              {ordonnancesLentilles.map((o) => (
                <MenuItem key={o.id} value={o.id}>
                  {o.prescripteur} · {new Date(o.date_prescription).toLocaleDateString("fr-FR")}
                </MenuItem>
              ))}
              {droits.saisirOrdonnance && <MenuItem value={NOUVELLE}>Nouvelle ordonnance…</MenuItem>}
            </TextField>
          ) : (
            <Typography color="text.secondary">Votre rôle ne donne pas accès aux ordonnances.</Typography>
          )}
          {saisieLibre && (
            <Stack direction="row" spacing={1}>
              <TextField
                size="small"
                label="Ophtalmologiste"
                value={prescripteur}
                onChange={(e) => setPrescripteur(e.target.value)}
                sx={{ flex: 1 }}
              />
              <TextField
                size="small"
                type="date"
                label="Date ord."
                value={dateOrdonnance}
                onChange={(e) => setDateOrdonnance(e.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
              />
            </Stack>
          )}
        </Stack>
      </Stack>

      <Stack direction={{ xs: "column", lg: "row" }} spacing={2}>
        <CorrectionOeil titre="Œil droit" correction={od} onChange={setOd} saisieLibre={saisieLibre} />
        <CorrectionOeil titre="Œil gauche" correction={og} onChange={setOg} saisieLibre={saisieLibre} />
      </Stack>

      {ligne("Lentille D.", BORDEAUX, droite, setDroite)}
      {ligne(
        "Lentille G.",
        "success.dark",
        gauche,
        setGauche,
        droite.article ? () => setGauche({ ...droite }) : undefined,
      )}

      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ alignItems: { sm: "center" } }}>
        <TextField
          size="small"
          label="Obs."
          value={observation}
          onChange={(e) => setObservation(e.target.value)}
          sx={{ flex: 1 }}
        />
        <Typography variant="h6" sx={{ color: "error.main" }}>
          Total lentilles : {formater(prix(droite) + prix(gauche), monnaie)}
        </Typography>
        <Button variant="contained" size="large" disabled={envoi} onClick={() => void valider()}>
          Valider les lentilles
        </Button>
      </Stack>
      {erreur && <Alert severity="error">{erreur}</Alert>}

      {deja.data && deja.data.length > 0 && (
        <Stack spacing={1}>
          <Typography variant="subtitle2" color="primary">
            Lentilles déjà vendues à ce client
          </Typography>
          <Table size="small" aria-label="Lentilles du client">
            <TableHead>
              <TableRow>
                {[
                  "N°",
                  "Date",
                  "Total",
                  "Lentille droite",
                  "Qté",
                  "Péremption",
                  "Lentille gauche",
                  "Qté",
                  "Péremption",
                  "Péniche",
                ].map((t, i) => (
                  <TableCell key={`${t}-${i}`} sx={{ color: BORDEAUX, fontWeight: 700 }}>
                    {t}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {deja.data.map((l) => (
                <TableRow key={l.id}>
                  <TableCell>{l.id}</TableCell>
                  <TableCell>{new Date(l.date).toLocaleDateString("fr-FR")}</TableCell>
                  <TableCell>{formater(enUnites(l.total_ttc, monnaie.decimales), monnaie)}</TableCell>
                  <TableCell>{l.droite?.libelle ?? ""}</TableCell>
                  <TableCell>{l.droite?.quantite ?? ""}</TableCell>
                  <TableCell>
                    {l.droite?.date_peremption ? new Date(l.droite.date_peremption).toLocaleDateString("fr-FR") : ""}
                  </TableCell>
                  <TableCell>{l.gauche?.libelle ?? ""}</TableCell>
                  <TableCell>{l.gauche?.quantite ?? ""}</TableCell>
                  <TableCell>
                    {l.gauche?.date_peremption ? new Date(l.gauche.date_peremption).toLocaleDateString("fr-FR") : ""}
                  </TableCell>
                  <TableCell>{l.peniche ?? ""}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Stack>
      )}
    </Stack>
  );
}
