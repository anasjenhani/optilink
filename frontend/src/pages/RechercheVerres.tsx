import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Checkbox from "@mui/material/Checkbox";
import Dialog from "@mui/material/Dialog";
import DialogContent from "@mui/material/DialogContent";
import FormControlLabel from "@mui/material/FormControlLabel";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { type Article, rechercherVerres, type SectionVerres, type VerreTrouve } from "../api/caisse";
import { enUnites, formater, type Monnaie } from "../api/monnaie";
import { BANDEAU, BORDEAUX, useApaise } from "./RechercheClients";

const SECTIONS: { cle: SectionVerres; titre: string }[] = [
  { cle: "stock_fournisseur", titre: "Verre Stock Fournisseur" },
  { cle: "prescription", titre: "Verre Prescription / RX / Importation" },
  { cle: "magasin", titre: "Verre Stock (Magasin)" },
];

const ENTETE = { color: BORDEAUX, fontWeight: 700, bgcolor: "grey.100", whiteSpace: "nowrap", py: 0.5 } as const;

const nombre = (valeur: string | null, decimales = 2) => (valeur === null ? "" : Number(valeur).toFixed(decimales));

/** Verre trouvé, sous la forme d'un article de la fiche lunette : la plage et son prix suivent. */
export function versArticle(v: VerreTrouve, section: SectionVerres): Article {
  const plage =
    v.sphere_debut === null
      ? ""
      : `sph ${nombre(v.sphere_debut)} à ${nombre(v.sphere_fin)} · cyl ${nombre(v.cylindre_debut)} à ${nombre(v.cylindre_fin)}`;
  return {
    id: v.article,
    reference: v.reference,
    libelle: v.designation,
    famille: "verre",
    code_barres: "",
    fournisseur: v.fournisseur,
    description: [plage, v.diametre && `Ø ${v.diametre}`, v.indice && `indice ${nombre(v.indice, 3)}`]
      .filter(Boolean)
      .join(" · "),
    caracteristiques: null,
    sur_commande: section !== "magasin",
    prix_vente_ttc: v.prix_vente_ttc ?? "0",
    taux_tva: "",
    devise: "",
    stock: v.quantite,
    plage: v.plage,
  };
}

/**
 * Recherche d'un verre, comme dans l'ancien logiciel : la désignation, puis trois listes (stock du
 * fournisseur, prescription, stock du magasin). Chaque ligne est une plage de puissances avec son prix ;
 * avec la correction de l'œil, seules les plages qui la couvrent restent. Un clic choisit le verre.
 */
export function RechercheVerres({
  ouvert,
  titre,
  magasin,
  monnaie,
  correction,
  onChoisir,
  onFerme,
}: {
  ouvert: boolean;
  titre: string;
  magasin: string;
  monnaie: Monnaie;
  correction: { sphere: string; cylindre: string };
  onChoisir: (article: Article) => void;
  onFerme: () => void;
}) {
  const [designation, setDesignation] = useState("");
  const avecCorrection = Boolean(correction.sphere || correction.cylindre);
  const [filtrer, setFiltrer] = useState(true);
  const texte = useApaise(designation);
  const filtre = filtrer && avecCorrection ? correction : {};
  const verres = useQuery({
    queryKey: ["recherche-verres", magasin, texte, filtre],
    queryFn: () => rechercherVerres(magasin, texte, filtre),
    enabled: ouvert && Boolean(magasin),
  });

  return (
    <Dialog open={ouvert} onClose={onFerme} fullWidth maxWidth="xl" aria-label={titre}>
      <Box sx={{ background: BANDEAU, color: "common.white", px: 3, py: 1 }}>
        <Typography variant="h5" component="h2" sx={{ fontWeight: 700 }}>
          Recherche … {titre}
        </Typography>
      </Box>
      <DialogContent sx={{ pt: 2 }}>
        <Stack spacing={2}>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ alignItems: { md: "center" } }}>
            <TextField
              label="Désignation"
              value={designation}
              onChange={(e) => setDesignation(e.target.value)}
              autoFocus
              size="small"
              sx={{ flex: 1, bgcolor: "#fffde7" }}
            />
            {avecCorrection && (
              <FormControlLabel
                control={<Checkbox checked={filtrer} onChange={(e) => setFiltrer(e.target.checked)} />}
                label={`Couvre la correction (sph ${correction.sphere || "—"}, cyl ${correction.cylindre || "—"})`}
              />
            )}
          </Stack>
          {verres.isError && <Alert severity="error">{String(verres.error)}</Alert>}
          {SECTIONS.map((s) => (
            <Section
              key={s.cle}
              titre={s.titre}
              lignes={verres.data?.[s.cle] ?? []}
              chargement={verres.isLoading}
              magasin={s.cle === "magasin"}
              monnaie={monnaie}
              onChoisir={(v) => {
                onChoisir(versArticle(v, s.cle));
                onFerme();
              }}
            />
          ))}
        </Stack>
      </DialogContent>
    </Dialog>
  );
}

function Section({
  titre,
  lignes,
  chargement,
  magasin,
  monnaie,
  onChoisir,
}: {
  titre: string;
  lignes: VerreTrouve[];
  chargement: boolean;
  magasin: boolean;
  monnaie: Monnaie;
  onChoisir: (v: VerreTrouve) => void;
}) {
  const colonnes = [
    "Sph Deb",
    "Sph Fin",
    "Cyl Deb",
    "Cyl Fin",
    "Diam",
    "Ind",
    "Fournisseur",
    "Désignation",
    "Prix vente TTC",
    ...(magasin ? ["Quantité"] : []),
  ];
  return (
    <Box component="section" aria-label={titre}>
      <Typography variant="h6" component="h3" sx={{ color: "#1a3fb0", textDecoration: "underline", fontWeight: 700 }}>
        {titre}
      </Typography>
      <TableContainer sx={{ maxHeight: 260, border: 1, borderColor: "grey.300" }}>
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              {colonnes.map((c) => (
                <TableCell key={c} sx={ENTETE}>
                  {c}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {lignes.map((v) => {
              const indisponible = magasin && !v.quantite;
              return (
                <TableRow
                  key={`${v.article}-${v.plage ?? ""}`}
                  hover={!indisponible}
                  onClick={indisponible ? undefined : () => onChoisir(v)}
                  sx={{
                    cursor: indisponible ? "not-allowed" : "pointer",
                    color: indisponible ? "text.disabled" : undefined,
                    "& td": { py: 0.25, fontWeight: 600, color: "inherit" },
                  }}
                  title={indisponible ? "Plus en stock dans ce magasin" : "Choisir ce verre"}
                >
                  <TableCell align="right">{nombre(v.sphere_debut)}</TableCell>
                  <TableCell align="right">{nombre(v.sphere_fin)}</TableCell>
                  <TableCell align="right">{nombre(v.cylindre_debut)}</TableCell>
                  <TableCell align="right">{nombre(v.cylindre_fin)}</TableCell>
                  <TableCell>{v.diametre}</TableCell>
                  <TableCell align="right">{nombre(v.indice, 3)}</TableCell>
                  <TableCell>{v.fournisseur}</TableCell>
                  <TableCell>{v.designation}</TableCell>
                  <TableCell align="right">
                    {v.prix_vente_ttc === null ? "" : formater(enUnites(v.prix_vente_ttc, monnaie.decimales), monnaie)}
                  </TableCell>
                  {magasin && <TableCell align="right">{v.quantite ?? 0}</TableCell>}
                </TableRow>
              );
            })}
            {!chargement && lignes.length === 0 && (
              <TableRow>
                <TableCell colSpan={colonnes.length} sx={{ color: "text.secondary" }}>
                  Aucun verre
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
