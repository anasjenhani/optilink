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

import { type FactureAchatResume, type FiltresFactures, lireFacture, listerFactures } from "../api/facturesAchat";
import { listerMagasins } from "../api/magasins";
import { formaterTexte, type Monnaie } from "../api/monnaie";
import { BlocTotaux, BoutonImprimer, dateCourte, TableBons, TableLignes, TableRetours, TableTva } from "./FactureAchat";
import { BANDEAU, BORDEAUX, useApaise } from "./RechercheClients";

type Colonne = { cle: keyof FactureAchatResume; titre: string; filtre?: keyof FiltresFactures; montant?: boolean };

const COLONNES: Colonne[] = [
  { cle: "numero", titre: "Numéro", filtre: "numero" },
  { cle: "date_entree", titre: "Date d'entrée" },
  { cle: "fournisseur", titre: "Fournisseur", filtre: "fournisseur" },
  { cle: "reference_fournisseur", titre: "Réf. fournisseur", filtre: "reference_fournisseur" },
  { cle: "date_reference", titre: "Date réf." },
  { cle: "nombre_bons", titre: "BL" },
  { cle: "total_net_ht", titre: "Net HT", montant: true },
  { cle: "total_tva", titre: "TVA", montant: true },
  { cle: "total_ttc", titre: "TTC", montant: true },
  { cle: "paiement_libelle", titre: "Paiement" },
  { cle: "cree_par", titre: "Créé par" },
];

/** Facture achat enregistrée, en lecture, avec Imprimer. */
export function DetailFactureAchat({ id, monnaie, onFerme }: { id: string; monnaie: Monnaie; onFerme: () => void }) {
  const facture = useQuery({ queryKey: ["factures-achat", id], queryFn: () => lireFacture(id) });
  const f = facture.data;
  return (
    <Dialog open onClose={onFerme} maxWidth="xl" fullWidth>
      <DialogTitle sx={{ color: BORDEAUX, fontWeight: 700 }}>
        {f ? `Facture Achat ${f.numero}` : "Facture Achat"}
      </DialogTitle>
      <DialogContent>
        {facture.isError && <Alert severity="error">{facture.error.message}</Alert>}
        {f && (
          <Stack spacing={2}>
            <Typography>
              {f.fournisseur_code} · {f.fournisseur} · Référence fournisseur <strong>{f.reference_fournisseur}</strong>{" "}
              du {dateCourte(f.date_reference)} · entrée le {dateCourte(f.date_entree)} · {f.magasin}
            </Typography>
            <TableBons bons={f.bons} monnaie={monnaie} />
            {f.retours.length > 0 && <TableRetours retours={f.retours} monnaie={monnaie} />}
            <TableLignes lignes={f.lignes} retours={f.lignes_retour} monnaie={monnaie} />
            <Stack direction={{ xs: "column", lg: "row" }} spacing={2} sx={{ alignItems: "flex-start" }}>
              <TableTva lignes={f.detail_tva} monnaie={monnaie} />
              <BlocTotaux
                totaux={f}
                monnaie={monnaie}
                saisie={{
                  tauxRemiseEx: Number(f.taux_remise_ex).toFixed(2),
                  frais: f.frais_supplementaires,
                  timbre: f.timbre_fiscal,
                }}
              />
            </Stack>
            {(Number(f.ajustement) !== 0 || f.observation) && (
              <Typography variant="body2" color="text.secondary">
                {Number(f.ajustement) !== 0 && `Ajustement des totaux : ${formaterTexte(f.ajustement, monnaie)}. `}
                {f.observation}
              </Typography>
            )}
          </Stack>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3 }}>
        {f && (
          <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
            Créé par : {f.cree_par} · Le : {new Date(f.cree_le).toLocaleString("fr-FR")} · Facture Achat :{" "}
            <strong>{f.paiement_libelle}</strong>
          </Typography>
        )}
        {f && <BoutonImprimer facture={f} monnaie={monnaie} />}
        <Button onClick={onFerme}>Fermer</Button>
      </DialogActions>
    </Dialog>
  );
}

/** « Liste des Factures Achat » : filtres sous les colonnes, totaux en pied de tableau. */
export function ListeFacturesAchat() {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const pays = magasins.data?.[0]?.pays;
  const monnaie: Monnaie = pays ? { devise: pays.devise, decimales: pays.decimales } : { devise: "TND", decimales: 3 };
  const [filtres, setFiltres] = useState<FiltresFactures>({});
  const [page, setPage] = useState(1);
  const [ouvert, setOuvert] = useState<string | null>(null);
  const recherche = useApaise(filtres);
  const factures = useQuery({
    queryKey: ["factures-achat", "liste", recherche, page],
    queryFn: () => listerFactures(recherche, page),
    placeholderData: keepPreviousData,
  });
  const pages = Math.max(1, Math.ceil((factures.data?.count ?? 0) / 50));
  const filtrer = (cle: keyof FiltresFactures, valeur: string) => {
    setFiltres((f) => ({ ...f, [cle]: valeur }));
    setPage(1);
  };
  const afficher = (f: FactureAchatResume, c: Colonne) => {
    const valeur = f[c.cle];
    if (c.montant) return formaterTexte(String(valeur), monnaie);
    if (c.cle === "date_entree" || c.cle === "date_reference") return dateCourte(String(valeur));
    if (c.cle === "fournisseur") return `${f.fournisseur_code} · ${f.fournisseur}`;
    return valeur ?? "";
  };

  return (
    <Stack spacing={1}>
      <Box sx={{ px: 3, py: 1, borderRadius: 1, background: BANDEAU }}>
        <Typography variant="h5" component="h3" sx={{ color: "common.white", fontWeight: 500 }}>
          Liste des Factures Achat
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
      {factures.isError && <Alert severity="error">{factures.error.message}</Alert>}
      <TableContainer sx={{ maxHeight: 520, border: 1, borderColor: "grey.400", borderRadius: 1 }}>
        <Table stickyHeader size="small" aria-label="Factures achat">
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
            {factures.data?.results.map((f) => (
              <TableRow
                key={f.id}
                hover
                onClick={() => setOuvert(f.id)}
                sx={{ cursor: "pointer", "& td": { borderColor: "#d9a3a3", whiteSpace: "nowrap" } }}
              >
                {COLONNES.map((c) => (
                  <TableCell key={c.cle} align={c.montant ? "right" : "left"}>
                    {afficher(f, c)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
          {factures.data && (
            <TableFooter>
              <TableRow sx={{ "& td": { fontWeight: 700, color: "text.primary", fontSize: 14, bgcolor: "grey.100" } }}>
                <TableCell colSpan={6}>
                  {factures.data.count} facture{factures.data.count > 1 ? "s" : ""}
                </TableCell>
                <TableCell align="right">{formaterTexte(factures.data.totaux.total_net_ht, monnaie)}</TableCell>
                <TableCell align="right">{formaterTexte(factures.data.totaux.total_tva, monnaie)}</TableCell>
                <TableCell align="right">{formaterTexte(factures.data.totaux.total_ttc, monnaie)}</TableCell>
                <TableCell colSpan={2} />
              </TableRow>
            </TableFooter>
          )}
        </Table>
        {factures.data?.count === 0 && (
          <Box sx={{ p: 2 }}>
            <Typography color="text.secondary">Aucune facture achat.</Typography>
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
      {ouvert && <DetailFactureAchat id={ouvert} monnaie={monnaie} onFerme={() => setOuvert(null)} />}
    </Stack>
  );
}
