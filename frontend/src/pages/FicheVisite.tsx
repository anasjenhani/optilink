import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
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
import { useState, type ReactNode } from "react";

import { listerMagasins } from "../api/magasins";
import { formaterTexte } from "../api/monnaie";
import { CAUSES_CASSE, declarerCasse, ficheVisite, type CauseCasse, type VerreCommande } from "../api/visites";

export const STATUTS_VENTE: Record<string, string> = {
  en_commande: "En commande",
  livree: "Livrée",
  annulee: "Annulée",
};

export const dateHeure = (iso: string) =>
  new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });

/** Décimales de la devise d'un magasin (3 pour le dinar), d'après son code. */
export function useMontant() {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  return (montant: string, devise: string, magasin?: string) =>
    formaterTexte(montant, {
      devise,
      decimales: magasins.data?.find((m) => m.code === magasin)?.pays.decimales ?? 3,
    });
}

function Section({ titre, children }: { titre: string; children: ReactNode }) {
  return (
    <Stack spacing={0.5}>
      <Typography variant="subtitle2" component="h3" color="primary">
        {titre}
      </Typography>
      {children}
    </Stack>
  );
}

function DeclarerCasse({ verre, onFait }: { verre: VerreCommande; onFait: () => void }) {
  const [cause, setCause] = useState<CauseCasse>("atelier");
  const [observation, setObservation] = useState("");
  const envoi = useMutation({
    mutationFn: () => declarerCasse({ ligne_commande: verre.id, cause, observation }),
    onSuccess: onFait,
  });
  return (
    <Stack spacing={1} sx={{ p: 1, border: 1, borderColor: "divider", borderRadius: 1 }}>
      <Typography variant="body2">
        Le verre « {verre.libelle} » repassera à commander, et le suivi de la visite y reviendra.
      </Typography>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
        <TextField
          select
          size="small"
          label="Cause"
          value={cause}
          onChange={(e) => setCause(e.target.value as CauseCasse)}
          sx={{ minWidth: 240 }}
        >
          {CAUSES_CASSE.map((c) => (
            <MenuItem key={c.valeur} value={c.valeur}>
              {c.libelle}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          size="small"
          label="Observation"
          value={observation}
          onChange={(e) => setObservation(e.target.value)}
          sx={{ flex: 1 }}
        />
        <Button variant="contained" color="warning" disabled={envoi.isPending} onClick={() => envoi.mutate()}>
          Déclarer la casse
        </Button>
      </Stack>
      {envoi.isError && <Alert severity="error">{envoi.error.message}</Alert>}
    </Stack>
  );
}

/** Fiche complète d'une visite, avec la déclaration de casse des verres reçus. */
export function FicheVisite({ id, casse = false, onFermer }: { id: string; casse?: boolean; onFermer: () => void }) {
  const queryClient = useQueryClient();
  const fiche = useQuery({ queryKey: ["fiche-visite", id], queryFn: () => ficheVisite(id) });
  const montant = useMontant();
  const [casseDe, setCasseDe] = useState<number | null>(null);
  const v = fiche.data;
  const m = (valeur: string) => (v ? montant(valeur, v.devise, v.magasin) : valeur);

  return (
    <Dialog open onClose={onFermer} fullWidth maxWidth="md" aria-labelledby="titre-fiche-visite">
      <DialogTitle id="titre-fiche-visite">Visite {v?.numero ?? ""}</DialogTitle>
      <DialogContent>
        {fiche.isError && <Alert severity="error">{fiche.error.message}</Alert>}
        {v && (
          <Stack spacing={2.5}>
            <Stack direction="row" sx={{ flexWrap: "wrap", gap: 1 }}>
              <Chip label={STATUTS_VENTE[v.statut] ?? v.statut} color={v.statut === "annulee" ? "error" : "primary"} />
              {v.etat_libelle && <Chip label={`Suivi : ${v.etat_libelle}`} />}
              {v.peniche !== null && <Chip label={`Péniche ${v.peniche}`} variant="outlined" />}
              {v.facture && <Chip label={`Facture ${v.facture}`} color="success" variant="outlined" />}
              {Number(v.reste_a_payer) > 0 && <Chip label={`Reste à payer ${m(v.reste_a_payer)}`} color="warning" />}
            </Stack>
            <Typography variant="body2" color="text.secondary">
              {dateHeure(v.cree_le)} · {v.magasin_nom} · vendeur {v.vendeur_nom}
              {v.livraison_prevue_le &&
                ` · livraison prévue le ${new Date(v.livraison_prevue_le).toLocaleDateString("fr-FR")}`}
            </Typography>

            <Section titre="Client">
              {v.client_fiche ? (
                <Typography variant="body2">
                  {v.client_fiche.nom} · fiche n° {v.client_fiche.numero}
                  {v.client_fiche.telephone && ` · ${v.client_fiche.telephone}`}
                  {v.client_fiche.organisme &&
                    ` · prise en charge ${v.client_fiche.organisme}${v.client_fiche.numero_affilie ? ` n° ${v.client_fiche.numero_affilie}` : ""}`}
                </Typography>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  Client de passage
                </Typography>
              )}
            </Section>

            <Section titre="Articles">
              <Table size="small" aria-label="Articles de la visite">
                <TableHead>
                  <TableRow>
                    <TableCell>Article</TableCell>
                    <TableCell align="right">Qté</TableCell>
                    <TableCell align="right">Prix unitaire</TableCell>
                    <TableCell align="right">Remise</TableCell>
                    <TableCell align="right">Total</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {v.lignes.map((l) => (
                    <TableRow key={l.id}>
                      <TableCell>
                        {l.libelle}
                        {l.quantite_reprise > 0 && (
                          <Typography variant="caption" color="error" component="div">
                            {l.quantite_reprise} repris par avoir
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell align="right">{l.quantite}</TableCell>
                      <TableCell align="right">{m(l.prix_unitaire_ttc)}</TableCell>
                      <TableCell align="right">{Number(l.remise_pct) ? `${Number(l.remise_pct)} %` : ""}</TableCell>
                      <TableCell align="right">{m(l.total_ttc)}</TableCell>
                    </TableRow>
                  ))}
                  <TableRow>
                    <TableCell colSpan={4} align="right">
                      <strong>Total TTC</strong>
                    </TableCell>
                    <TableCell align="right">
                      <strong>{m(v.total_ttc)}</strong>
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </Section>

            <Section titre="Règlements">
              {v.reglements.length === 0 && (
                <Typography variant="body2" color="text.secondary">
                  Aucun règlement.
                </Typography>
              )}
              {v.reglements.map((r, i) => (
                <Typography key={i} variant="body2">
                  {dateHeure(r.recu_le)} · {r.mode_libelle}
                  {r.reference ? ` n° ${r.reference}` : ""} · {m(r.montant)}
                  {r.statut && r.statut !== "encaisse" ? ` · ${r.statut_libelle}` : ""}
                  {r.recu_par && ` · encaissé par ${r.recu_par}`}
                </Typography>
              ))}
              {v.prises_en_charge.map((p, i) => (
                <Typography key={`pec-${i}`} variant="body2">
                  Prise en charge {p.organisme} · {m(p.montant)} · {p.statut_libelle}
                  {p.numero_dossier && ` · dossier ${p.numero_dossier}`}
                </Typography>
              ))}
            </Section>

            {v.verres_commandes.length > 0 && (
              <Section titre="Verres commandés">
                {v.verres_commandes.map((verre) => (
                  <Stack key={verre.id} spacing={1}>
                    <Stack direction="row" sx={{ alignItems: "center", flexWrap: "wrap", gap: 1 }}>
                      <Typography variant="body2" sx={{ flex: 1, minWidth: 0 }}>
                        {verre.libelle} · {verre.fournisseur} · {verre.commande_fournisseur} ·{" "}
                        {verre.statut === "recue"
                          ? `reçu le ${dateHeure(verre.recu_le ?? "")}`
                          : verre.statut === "envoyee"
                            ? "en attente du fournisseur"
                            : "commande annulée"}
                      </Typography>
                      {verre.casse && <Chip size="small" color="error" label={`Cassé : ${verre.casse}`} />}
                      {casse &&
                        verre.statut === "recue" &&
                        !verre.casse &&
                        v.statut === "en_commande" &&
                        casseDe !== verre.id && (
                          <Button size="small" color="warning" onClick={() => setCasseDe(verre.id)}>
                            Casse
                          </Button>
                        )}
                    </Stack>
                    {casseDe === verre.id && (
                      <DeclarerCasse
                        verre={verre}
                        onFait={() => {
                          setCasseDe(null);
                          void queryClient.invalidateQueries({ queryKey: ["fiche-visite", id] });
                          void queryClient.invalidateQueries({ queryKey: ["casses"] });
                          void queryClient.invalidateQueries({ queryKey: ["suivi"] });
                        }}
                      />
                    )}
                  </Stack>
                ))}
              </Section>
            )}

            {v.etapes.length > 0 && (
              <Section titre="Suivi de l'atelier">
                {v.etapes.map((e, i) => (
                  <Typography key={i} variant="body2">
                    {dateHeure(e.le)} · {e.etape_libelle} · {e.par}
                    {e.observation && ` · ${e.observation}`}
                  </Typography>
                ))}
              </Section>
            )}

            {v.avoirs.length > 0 && (
              <Section titre="Avoirs">
                {v.avoirs.map((a) => (
                  <Typography key={a.numero} variant="body2">
                    {a.numero} · {dateHeure(a.cree_le)} · {a.annulation ? "annulation" : "retour"} · {m(a.total_ttc)} ·{" "}
                    remboursé {m(a.montant_rembourse)} · {a.motif}
                  </Typography>
                ))}
              </Section>
            )}
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onFermer}>Fermer</Button>
      </DialogActions>
    </Dialog>
  );
}
