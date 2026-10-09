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
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemText from "@mui/material/ListItemText";
import MenuItem from "@mui/material/MenuItem";
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

import { listerFournisseurs } from "../api/achats";
import { chercherClients, nomClient, type Client } from "../api/clients";
import { listerMagasins } from "../api/magasins";
import {
  changerEtapeSav,
  ETAPES_SAV,
  listerDossiersSav,
  MOTIFS_SAV,
  ouvrirDossierSav,
  type DossierSav,
  type EtapeSav,
  type MotifSav,
} from "../api/sav";
import { listerVisites } from "../api/visites";

const FILTRES = [
  { valeur: "ouverts", libelle: "En cours" },
  { valeur: "retard", libelle: "En retard" },
  { valeur: "pret", libelle: "Prêts à rendre" },
  { valeur: "rendu", libelle: "Rendus" },
  { valeur: "annule", libelle: "Annulés" },
  { valeur: "", libelle: "Tous" },
];

const date = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("fr-FR") : "—");

/**
 * Service après-vente : ce que les clients rapportent (casse, réglage, défaut…), son passage à
 * l'atelier ou chez le fournisseur, puis sa remise au client. Une réparation payante s'encaisse
 * en caisse comme une vente.
 */
export function Sav({
  creer,
  modifier,
  filtreInitial = "ouverts",
}: {
  creer: boolean;
  modifier: boolean;
  filtreInitial?: string;
}) {
  const [filtre, setFiltre] = useState(filtreInitial);
  const [recherche, setRecherche] = useState("");
  const [ouverture, setOuverture] = useState(false);
  const [choisi, setChoisi] = useState<string | null>(null);
  const liste = useQuery({
    queryKey: ["sav", filtre, recherche],
    queryFn: () =>
      listerDossiersSav({
        etape: filtre === "retard" ? "" : filtre,
        retard: filtre === "retard",
        q: recherche,
      }),
  });
  const dossier = liste.data?.find((d) => d.id === choisi);

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Stack direction="row" spacing={2} sx={{ alignItems: "center", flexWrap: "wrap" }} useFlexGap>
            <Typography variant="h6" component="h2" sx={{ flexGrow: 1 }}>
              Dossiers SAV
            </Typography>
            {creer && (
              <Button variant="contained" onClick={() => setOuverture(true)}>
                Nouveau dossier SAV
              </Button>
            )}
          </Stack>
          <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap" }}>
            <TextField
              select
              size="small"
              label="Dossiers"
              value={filtre}
              onChange={(e) => setFiltre(e.target.value)}
              sx={{ minWidth: 200 }}
            >
              {FILTRES.map((f) => (
                <MenuItem key={f.valeur} value={f.valeur}>
                  {f.libelle}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              size="small"
              label="Rechercher (n°, client, téléphone, article)"
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
              sx={{ minWidth: 320 }}
            />
          </Stack>
          {liste.isError && <Alert severity="error">{liste.error.message}</Alert>}
          {liste.data?.length === 0 && <Typography color="text.secondary">Aucun dossier.</Typography>}
          {liste.data && liste.data.length > 0 && (
            <Table size="small" aria-label="Dossiers SAV">
              <TableHead>
                <TableRow>
                  <TableCell>N°</TableCell>
                  <TableCell>Reçu le</TableCell>
                  <TableCell>Client</TableCell>
                  <TableCell>Article</TableCell>
                  <TableCell>Motif</TableCell>
                  <TableCell>Étape</TableCell>
                  <TableCell>Retour prévu</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {liste.data.map((d) => (
                  <TableRow key={d.id} hover sx={{ cursor: "pointer" }} onClick={() => setChoisi(d.id)}>
                    <TableCell>{d.numero}</TableCell>
                    <TableCell>{date(d.cree_le)}</TableCell>
                    <TableCell>
                      {d.client_nom}
                      {d.client_telephone && (
                        <Typography variant="caption" sx={{ display: "block" }} color="text.secondary">
                          {d.client_telephone}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>{d.designation}</TableCell>
                    <TableCell>
                      {d.motif_libelle}
                      {d.sous_garantie && <Chip size="small" label="Garantie" sx={{ ml: 1 }} />}
                    </TableCell>
                    <TableCell>{d.etape_libelle}</TableCell>
                    <TableCell>
                      {d.en_retard ? (
                        <Chip size="small" color="error" label={`En retard · ${date(d.retour_prevu_le)}`} />
                      ) : (
                        date(d.retour_prevu_le)
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Stack>
      </CardContent>
      {ouverture && <Ouverture onFermer={() => setOuverture(false)} />}
      {dossier && <Suivi dossier={dossier} modifier={modifier} onFermer={() => setChoisi(null)} />}
    </Card>
  );
}

function Ouverture({ onFermer }: { onFermer: () => void }) {
  const queryClient = useQueryClient();
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = magasinChoisi || magasins.data?.[0]?.id || "";
  const [rechercheClient, setRechercheClient] = useState("");
  const [client, setClient] = useState<Client | null>(null);
  const [vente, setVente] = useState("");
  const [designation, setDesignation] = useState("");
  const [motif, setMotif] = useState<MotifSav>("casse");
  const [description, setDescription] = useState("");
  const [garantie, setGarantie] = useState(false);
  const [retourPrevu, setRetourPrevu] = useState("");
  const clients = useQuery({
    queryKey: ["clients", rechercheClient],
    queryFn: () => chercherClients(rechercheClient),
    enabled: !client && rechercheClient.trim().length >= 2,
  });
  const visites = useQuery({
    queryKey: ["visites", "client", client?.id, magasin],
    queryFn: () => listerVisites({ client: client!.id, magasin }),
    enabled: Boolean(client && magasin),
  });
  const ouvrir = useMutation({
    mutationFn: () =>
      ouvrirDossierSav({
        magasin,
        client: client!.id,
        vente: vente || null,
        designation,
        motif,
        description,
        sous_garantie: garantie,
        retour_prevu_le: retourPrevu || null,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["sav"] });
      onFermer();
    },
  });

  return (
    <Dialog open onClose={onFermer} fullWidth maxWidth="sm">
      <DialogTitle>Nouveau dossier SAV</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          {(magasins.data?.length ?? 0) > 1 && (
            <TextField select size="small" label="Magasin" value={magasin} onChange={(e) => setMagasin(e.target.value)}>
              {magasins.data?.map((m) => (
                <MenuItem key={m.id} value={m.id}>
                  {m.nom}
                </MenuItem>
              ))}
            </TextField>
          )}
          {client ? (
            <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
              <Typography sx={{ flexGrow: 1 }}>{nomClient(client)}</Typography>
              <Button
                size="small"
                onClick={() => {
                  setClient(null);
                  setVente("");
                }}
              >
                Changer
              </Button>
            </Stack>
          ) : (
            <>
              <TextField
                size="small"
                label="Client (nom, téléphone, n° de fiche)"
                value={rechercheClient}
                onChange={(e) => setRechercheClient(e.target.value)}
                autoFocus
              />
              {clients.data && (
                <List dense aria-label="Clients trouvés" sx={{ maxHeight: 200, overflow: "auto" }}>
                  {clients.data.length === 0 && <Typography color="text.secondary">Aucun client.</Typography>}
                  {clients.data.map((c) => (
                    <ListItemButton key={c.id} onClick={() => setClient(c)}>
                      <ListItemText primary={nomClient(c)} secondary={c.telephone} />
                    </ListItemButton>
                  ))}
                </List>
              )}
            </>
          )}
          {client && (
            <TextField
              select
              size="small"
              label="Visite d'origine (facultatif)"
              value={vente}
              onChange={(e) => setVente(e.target.value)}
            >
              <MenuItem value="">Aucune</MenuItem>
              {visites.data?.results.map((v) => (
                <MenuItem key={v.id} value={v.id}>
                  {v.numero} · {date(v.cree_le)}
                </MenuItem>
              ))}
            </TextField>
          )}
          <TextField
            size="small"
            label="Article rapporté"
            placeholder="ex. Monture Ray-Ban, branche cassée"
            value={designation}
            onChange={(e) => setDesignation(e.target.value)}
          />
          <TextField
            select
            size="small"
            label="Motif"
            value={motif}
            onChange={(e) => setMotif(e.target.value as MotifSav)}
          >
            {MOTIFS_SAV.map((m) => (
              <MenuItem key={m.valeur} value={m.valeur}>
                {m.libelle}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            size="small"
            label="Description"
            multiline
            minRows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
            <FormControlLabel
              control={<Checkbox checked={garantie} onChange={(e) => setGarantie(e.target.checked)} />}
              label="Sous garantie"
            />
            <TextField
              size="small"
              type="date"
              label="Retour prévu le"
              value={retourPrevu}
              onChange={(e) => setRetourPrevu(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </Stack>
          {ouvrir.isError && <Alert severity="error">{ouvrir.error.message}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onFermer}>Annuler</Button>
        <Button
          variant="contained"
          disabled={!client || !magasin || !designation.trim() || ouvrir.isPending}
          onClick={() => ouvrir.mutate()}
        >
          Enregistrer
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function Suivi({ dossier, modifier, onFermer }: { dossier: DossierSav; modifier: boolean; onFermer: () => void }) {
  const queryClient = useQueryClient();
  const suivantes = ETAPES_SAV.filter((e) => e.valeur !== dossier.etape && e.valeur !== "recu");
  const [etape, setEtape] = useState<EtapeSav | "">("");
  const [commentaire, setCommentaire] = useState("");
  const [fournisseur, setFournisseur] = useState(dossier.fournisseur ?? "");
  const [retourPrevu, setRetourPrevu] = useState(dossier.retour_prevu_le ?? "");
  const [solution, setSolution] = useState(dossier.solution);
  const fournisseurs = useQuery({
    queryKey: ["fournisseurs"],
    queryFn: listerFournisseurs,
    enabled: etape === "fournisseur",
  });
  const changement = useMutation({
    mutationFn: () =>
      changerEtapeSav(dossier.id, {
        etape: etape as EtapeSav,
        commentaire,
        fournisseur: etape === "fournisseur" ? fournisseur || null : null,
        retour_prevu_le: retourPrevu || null,
        solution,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["sav"] });
      setEtape("");
      setCommentaire("");
    },
  });

  return (
    <Dialog open onClose={onFermer} fullWidth maxWidth="sm">
      <DialogTitle>
        Dossier {dossier.numero} · {dossier.etape_libelle}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={2}>
          <Typography>
            <strong>{dossier.client_nom}</strong> {dossier.client_telephone && `· ${dossier.client_telephone}`}
            <br />
            {dossier.designation} · {dossier.motif_libelle}
            {dossier.sous_garantie && " · sous garantie"}
            {dossier.vente_numero && ` · visite ${dossier.vente_numero}`}
            {dossier.fournisseur_nom && ` · fournisseur ${dossier.fournisseur_nom}`}
          </Typography>
          {dossier.description && <Typography color="text.secondary">{dossier.description}</Typography>}
          {dossier.solution && <Typography>Solution : {dossier.solution}</Typography>}
          <Table size="small" aria-label="Historique">
            <TableBody>
              {dossier.evenements.map((e, i) => (
                <TableRow key={i}>
                  <TableCell>{new Date(e.le).toLocaleString("fr-FR")}</TableCell>
                  <TableCell>{e.etape_libelle}</TableCell>
                  <TableCell>{e.commentaire}</TableCell>
                  <TableCell>{e.par}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {modifier && dossier.est_ouvert && (
            <>
              <TextField
                select
                size="small"
                label="Passer à l'étape"
                value={etape}
                onChange={(e) => setEtape(e.target.value as EtapeSav)}
              >
                {suivantes.map((e) => (
                  <MenuItem key={e.valeur} value={e.valeur}>
                    {e.libelle}
                  </MenuItem>
                ))}
              </TextField>
              {etape === "fournisseur" && (
                <TextField
                  select
                  size="small"
                  label="Fournisseur"
                  value={fournisseur}
                  onChange={(e) => setFournisseur(e.target.value)}
                >
                  {fournisseurs.data?.map((f) => (
                    <MenuItem key={f.id} value={f.id}>
                      {f.nom}
                    </MenuItem>
                  ))}
                </TextField>
              )}
              {(etape === "atelier" || etape === "fournisseur") && (
                <TextField
                  size="small"
                  type="date"
                  label="Retour prévu le"
                  value={retourPrevu}
                  onChange={(e) => setRetourPrevu(e.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
              )}
              {(etape === "pret" || etape === "rendu") && (
                <TextField
                  size="small"
                  label="Solution apportée"
                  value={solution}
                  onChange={(e) => setSolution(e.target.value)}
                />
              )}
              {etape && (
                <TextField
                  size="small"
                  label={etape === "annule" ? "Motif de l'annulation" : "Commentaire"}
                  value={commentaire}
                  onChange={(e) => setCommentaire(e.target.value)}
                />
              )}
              {changement.isError && <Alert severity="error">{changement.error.message}</Alert>}
            </>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onFermer}>Fermer</Button>
        {modifier && dossier.est_ouvert && (
          <Button variant="contained" disabled={!etape || changement.isPending} onClick={() => changement.mutate()}>
            Valider l'étape
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
