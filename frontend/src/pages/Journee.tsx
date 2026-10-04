import Alert from "@mui/material/Alert";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import MenuItem from "@mui/material/MenuItem";
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

import { listerMagasins } from "../api/magasins";
import { formaterTexte, type Monnaie } from "../api/monnaie";
import { lireJournee } from "../api/suivi";
import { Filtres } from "../navigation/Filtres";

const OUI_NON = (oui: string, non: string) => [
  { valeur: "" as const, libelle: "Tous" },
  { valeur: "oui" as const, libelle: oui },
  { valeur: "non" as const, libelle: non },
];

function aujourdhui() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** État de la journée de vente d'un magasin : chaque visite, ce qui est réglé et ce qui reste. */
export function Journee() {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [magasinChoisi, setMagasin] = useState("");
  const magasin = magasinChoisi || magasins.data?.[0]?.id || "";
  const decimales = magasins.data?.find((m) => m.id === magasin)?.pays.decimales ?? 3;
  const [date, setDate] = useState(aujourdhui);
  const [soldee, setSoldee] = useState<"" | "oui" | "non">("");
  const [livree, setLivree] = useState<"" | "oui" | "non">("");

  const journee = useQuery({
    queryKey: ["journee", magasin, date],
    queryFn: () => lireJournee(magasin, date),
    enabled: Boolean(magasin && date),
  });
  const monnaie: Monnaie = { devise: journee.data?.devise ?? "TND", decimales };
  const montant = (texte: string) => formaterTexte(texte, monnaie);
  const garder = (filtre: string, valeur: boolean) => filtre === "" || valeur === (filtre === "oui");
  const ventes = (journee.data?.ventes ?? []).filter((v) => garder(soldee, v.soldee) && garder(livree, v.livree));

  return (
    <Card>
      <CardContent>
        <Stack spacing={1.5}>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ alignItems: { sm: "center" } }}>
            <Typography variant="h6" component="h2" sx={{ flexGrow: 1 }}>
              Journée de vente
            </Typography>
            <TextField
              select
              size="small"
              label="Magasin"
              value={magasin}
              onChange={(e) => setMagasin(e.target.value)}
              sx={{ minWidth: 200 }}
            >
              {magasins.data?.map((m) => (
                <MenuItem key={m.id} value={m.id}>
                  {m.nom}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              size="small"
              type="date"
              label="Jour"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </Stack>
          {journee.isError && <Alert severity="error">{journee.error.message}</Alert>}
          {journee.data && (
            <Stack direction="row" sx={{ flexWrap: "wrap", gap: 1 }} aria-label="Totaux de la journée">
              <Chip label={`${journee.data.nombre_ventes} visite(s)`} />
              <Chip color="primary" label={`Ventes : ${montant(journee.data.total_ventes)}`} />
              <Chip label={`Réglé : ${montant(journee.data.regle_sur_ventes)}`} />
              {Number(journee.data.pris_en_charge) > 0 && (
                <Chip label={`Pris en charge : ${montant(journee.data.pris_en_charge)}`} />
              )}
              <Chip color="warning" label={`Reste à régler : ${montant(journee.data.reste_sur_ventes)}`} />
              <Chip color="success" label={`Encaissé ce jour : ${montant(journee.data.encaisse)}`} />
              {journee.data.encaisse_par_mode.map((m) => (
                <Chip key={m.mode} variant="outlined" label={`${m.mode} : ${montant(m.montant)}`} />
              ))}
            </Stack>
          )}
          <TableContainer sx={{ maxHeight: 460 }}>
            <Table size="small" stickyHeader aria-label="Visites de la journée" sx={{ "& td, & th": { whiteSpace: "nowrap" } }}>
              <TableHead>
                <TableRow>
                  {["N° fiche", "Tél", "Nom & prénom", "N° visite", "Heure", "Soldée", "Livrée", "Vendeur", "Total", "PEC client", "PEC visite", "Réglé", "Reste", "N° facture"].map(
                    (titre) => (
                      <TableCell key={titre} sx={{ fontWeight: 700, color: "primary.main" }}>
                        {titre}
                      </TableCell>
                    ),
                  )}
                </TableRow>
              </TableHead>
              <TableBody>
                {ventes.map((v) => (
                  <TableRow key={v.id} hover>
                    <TableCell>{v.client?.numero ?? ""}</TableCell>
                    <TableCell>{v.client?.telephone ?? ""}</TableCell>
                    <TableCell>{v.client?.nom ?? "Client de passage"}</TableCell>
                    <TableCell>{v.numero}</TableCell>
                    <TableCell>
                      {new Date(v.cree_le).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}
                    </TableCell>
                    <TableCell>{v.soldee ? "Oui" : "Non"}</TableCell>
                    <TableCell>{v.livree ? "Oui" : "Non"}</TableCell>
                    <TableCell>{v.vendeur}</TableCell>
                    <TableCell>{montant(v.total_ttc)}</TableCell>
                    <TableCell>{v.pec_client ?? ""}</TableCell>
                    <TableCell>{Number(v.pec_visite) ? montant(v.pec_visite) : ""}</TableCell>
                    <TableCell>{montant(v.regle)}</TableCell>
                    <TableCell>{montant(v.reste)}</TableCell>
                    <TableCell>{v.facture ?? ""}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          {journee.isSuccess && ventes.length === 0 && (
            <Typography color="text.secondary">Aucune visite ce jour-là pour ces filtres.</Typography>
          )}
          <Filtres libelle="Soldée" options={OUI_NON("Soldé", "Non soldé")} valeur={soldee} onChange={setSoldee} />
          <Filtres libelle="Livrée" options={OUI_NON("Livré", "Non livré")} valeur={livree} onChange={setLivree} />
        </Stack>
      </CardContent>
    </Card>
  );
}
