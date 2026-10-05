import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableFooter from "@mui/material/TableFooter";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { lireReception, listerReceptions, type BonReceptionResume, type FiltresReceptions } from "../api/achats";
import { listerMagasins } from "../api/magasins";
import { formaterTexte, type Monnaie } from "../api/monnaie";
import { BANDEAU, BORDEAUX, useApaise } from "./RechercheClients";

const dateCourte = (iso: string) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString("fr-FR") : "");

type Colonne = { cle: keyof BonReceptionResume; titre: string; filtre?: keyof FiltresReceptions; montant?: boolean };

const COLONNES: Colonne[] = [
  { cle: "numero", titre: "Numéro", filtre: "numero" },
  { cle: "date_saisie", titre: "Date" },
  { cle: "fournisseur", titre: "Fournisseur", filtre: "fournisseur" },
  { cle: "numero_bl", titre: "Réf. fournisseur", filtre: "numero_bl" },
  { cle: "etat_libelle", titre: "Etat" },
  { cle: "numero_facture", titre: "N° facture", filtre: "numero_facture" },
  { cle: "observation", titre: "Observation", filtre: "observation" },
  { cle: "date_bl", titre: "Date réf." },
  { cle: "total_ht", titre: "Total HT", montant: true },
  { cle: "total_net_ht", titre: "Net HT", montant: true },
  { cle: "total_ttc", titre: "TTC", montant: true },
  { cle: "type_bl", titre: "Type BL" },
  { cle: "total_articles", titre: "Total articles" },
];

function DetailReception({ id, monnaie, onFerme }: { id: string; monnaie: Monnaie; onFerme: () => void }) {
  const bon = useQuery({ queryKey: ["bons-reception", id], queryFn: () => lireReception(id) });
  const m = (valeur: string) => formaterTexte(valeur, monnaie);
  const b = bon.data;
  return (
    <Dialog open onClose={onFerme} maxWidth="lg" fullWidth>
      <DialogTitle>{b ? `Bon de réception ${b.numero}` : "Bon de réception"}</DialogTitle>
      <DialogContent>
        {bon.isError && <Alert severity="error">{bon.error.message}</Alert>}
        {b && (
          <Stack spacing={2}>
            <Typography>
              {b.fournisseur_code} · {b.fournisseur} · BL {b.numero_bl} du {dateCourte(b.date_bl)} · saisi le{" "}
              {dateCourte(b.date_saisie)} par {b.cree_par} · {b.etat_libelle}
            </Typography>
            <Table size="small" aria-label="Lignes du bon">
              <TableHead>
                <TableRow sx={{ "& th": { color: BORDEAUX, fontWeight: 700 } }}>
                  <TableCell>Bon commande</TableCell>
                  <TableCell>Code</TableCell>
                  <TableCell>Œil</TableCell>
                  <TableCell>Désignation</TableCell>
                  <TableCell align="right">Qté</TableCell>
                  <TableCell align="right">Prix achat HT</TableCell>
                  <TableCell align="right">Remise %</TableCell>
                  <TableCell align="right">Net HT</TableCell>
                  <TableCell align="right">TVA %</TableCell>
                  <TableCell align="right">TTC</TableCell>
                  <TableCell>Non conforme</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {b.lignes.map((l, i) => (
                  <TableRow key={i} sx={l.non_conforme ? { bgcolor: "#fdecea" } : undefined}>
                    <TableCell>{l.commande}</TableCell>
                    <TableCell>{l.article.reference}</TableCell>
                    <TableCell>{l.oeil}</TableCell>
                    <TableCell>{l.designation}</TableCell>
                    <TableCell align="right">{l.quantite}</TableCell>
                    <TableCell align="right">{m(l.prix_achat_ht)}</TableCell>
                    <TableCell align="right">{Number(l.taux_remise)}</TableCell>
                    <TableCell align="right">{m(l.net_ht)}</TableCell>
                    <TableCell align="right">{Number(l.taux_tva)}</TableCell>
                    <TableCell align="right">{m(l.montant_ttc)}</TableCell>
                    <TableCell>{l.non_conforme ? `Oui : ${l.motif}` : ""}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Typography>
              Total HT {m(b.total_ht)} · Remise {m(b.total_remise)} · Remise exceptionnelle {m(b.remise_ex)} · Net HT{" "}
              {m(b.total_net_ht)} · FODEC {m(b.total_fodec)} · TVA {m(b.total_tva)} ·{" "}
              <strong>TTC {m(b.total_ttc)}</strong>
            </Typography>
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onFerme}>Fermer</Button>
      </DialogActions>
    </Dialog>
  );
}

/** « Liste des Bons de Réceptions » : filtres sous les colonnes, totaux en pied de tableau. */
export function ListeReceptions() {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const pays = magasins.data?.[0]?.pays;
  const monnaie: Monnaie = pays ? { devise: pays.devise, decimales: pays.decimales } : { devise: "TND", decimales: 3 };
  const [filtres, setFiltres] = useState<FiltresReceptions>({});
  const [page, setPage] = useState(1);
  const [ouvert, setOuvert] = useState<string | null>(null);
  const recherche = useApaise(filtres);
  const bons = useQuery({
    queryKey: ["bons-reception", "liste", recherche, page],
    queryFn: () => listerReceptions(recherche, page),
    placeholderData: keepPreviousData,
  });
  const pages = Math.max(1, Math.ceil((bons.data?.count ?? 0) / 50));
  const filtrer = (cle: keyof FiltresReceptions, valeur: string) => {
    setFiltres((f) => ({ ...f, [cle]: valeur }));
    setPage(1);
  };
  const afficher = (bon: BonReceptionResume, c: Colonne) => {
    const valeur = bon[c.cle];
    if (c.montant) return formaterTexte(String(valeur), monnaie);
    if (c.cle === "date_saisie" || c.cle === "date_bl") return dateCourte(String(valeur));
    if (c.cle === "fournisseur") return `${bon.fournisseur_code} · ${bon.fournisseur}`;
    return valeur ?? "";
  };

  return (
    <Stack spacing={1}>
      <Box sx={{ px: 3, py: 1, borderRadius: 1, background: BANDEAU }}>
        <Typography variant="h5" component="h3" sx={{ color: "common.white", fontWeight: 500 }}>
          Liste des Bons de Réceptions
        </Typography>
      </Box>
      <Stack direction="row" spacing={2}>
        <TextField
          size="small"
          type="date"
          label="Du"
          value={filtres.du ?? ""}
          onChange={(e) => filtrer("du", e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <TextField
          size="small"
          type="date"
          label="Au"
          value={filtres.au ?? ""}
          onChange={(e) => filtrer("au", e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
        />
      </Stack>
      {bons.isError && <Alert severity="error">{bons.error.message}</Alert>}
      <TableContainer sx={{ maxHeight: 520, border: 1, borderColor: "grey.400", borderRadius: 1 }}>
        <Table stickyHeader size="small" aria-label="Bons de réception">
          <TableHead>
            <TableRow>
              {COLONNES.map((c) => (
                <TableCell
                  key={c.cle}
                  align={c.montant ? "right" : "left"}
                  sx={{ color: BORDEAUX, fontWeight: 700, bgcolor: "grey.100", whiteSpace: "nowrap" }}
                >
                  {c.titre}
                </TableCell>
              ))}
            </TableRow>
            <TableRow>
              {COLONNES.map((c) => (
                <TableCell key={c.cle} sx={{ top: 37, p: 0.5, bgcolor: "grey.300" }}>
                  {c.filtre && (
                    <TextField
                      size="small"
                      fullWidth
                      value={filtres[c.filtre] ?? ""}
                      onChange={(e) => filtrer(c.filtre!, e.target.value)}
                      slotProps={{
                        htmlInput: { "aria-label": `Filtrer ${c.titre}` },
                        input: { sx: { bgcolor: "common.white", height: 28, fontSize: 14 } },
                      }}
                    />
                  )}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {bons.data?.results.map((bon) => (
              <TableRow
                key={bon.id}
                hover
                onClick={() => setOuvert(bon.id)}
                sx={{ cursor: "pointer", "& td": { borderColor: "#d9a3a3", whiteSpace: "nowrap" } }}
              >
                {COLONNES.map((c) => (
                  <TableCell key={c.cle} align={c.montant ? "right" : "left"}>
                    {afficher(bon, c)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
          {bons.data && (
            <TableFooter>
              <TableRow sx={{ "& td": { fontWeight: 700, color: "text.primary", fontSize: 14, bgcolor: "grey.100" } }}>
                <TableCell colSpan={8}>
                  {bons.data.count} bon{bons.data.count > 1 ? "s" : ""}
                </TableCell>
                <TableCell align="right">{formaterTexte(bons.data.totaux.total_ht, monnaie)}</TableCell>
                <TableCell align="right">{formaterTexte(bons.data.totaux.total_net_ht, monnaie)}</TableCell>
                <TableCell align="right">{formaterTexte(bons.data.totaux.total_ttc, monnaie)}</TableCell>
                <TableCell />
                <TableCell>{bons.data.totaux.total_articles}</TableCell>
              </TableRow>
            </TableFooter>
          )}
        </Table>
        {bons.data?.count === 0 && (
          <Box sx={{ p: 2 }}>
            <Typography color="text.secondary">Aucun bon de réception.</Typography>
          </Box>
        )}
      </TableContainer>
      {pages > 1 && (
        <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end", alignItems: "center" }}>
          <Button size="small" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            Précédente
          </Button>
          <Typography variant="body2">
            Page {page} / {pages}
          </Typography>
          <Button size="small" disabled={page >= pages} onClick={() => setPage(page + 1)}>
            Suivante
          </Button>
        </Stack>
      )}
      {ouvert && <DetailReception id={ouvert} monnaie={monnaie} onFerme={() => setOuvert(null)} />}
    </Stack>
  );
}
