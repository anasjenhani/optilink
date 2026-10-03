import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
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
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listerMagasins } from "../api/magasins";
import { formaterTexte, type Monnaie } from "../api/monnaie";
import { lireReporting, type SectionReporting } from "../api/pilotage";

const aujourdhui = () => new Date().toLocaleDateString("en-CA");
const debutDuMois = () => `${aujourdhui().slice(0, 8)}01`;
const jour = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString("fr-FR");

function Chiffre({ libelle, valeur }: { libelle: string; valeur: string }) {
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="body2" color="text.secondary">
        {libelle}
      </Typography>
      <Typography variant="h5" component="p">
        {valeur}
      </Typography>
    </Paper>
  );
}

function Tableau({
  titre,
  colonnes,
  lignes,
}: {
  titre: string;
  colonnes: string[];
  lignes: (string | number)[][];
}) {
  return (
    <Box>
      <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
        {titre}
      </Typography>
      {lignes.length === 0 ? (
        <Typography color="text.secondary">Rien sur la période.</Typography>
      ) : (
        <Table size="small" aria-label={titre}>
          <TableHead>
            <TableRow>
              {colonnes.map((c, i) => (
                <TableCell key={c} align={i === 0 ? "left" : "right"}>
                  {c}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {lignes.map((ligne) => (
              <TableRow key={String(ligne[0])}>
                {ligne.map((v, i) => (
                  <TableCell key={i} align={i === 0 ? "left" : "right"}>
                    {v}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Box>
  );
}

function Section({ section, monnaie }: { section: SectionReporting; monnaie: Monnaie }) {
  const m = (montant: string) => formaterTexte(montant, monnaie);
  return (
    <Stack spacing={3}>
      <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))" }}>
        <Chiffre libelle="Chiffre d'affaires TTC" valeur={m(section.ca_ttc)} />
        <Chiffre libelle="Avoirs" valeur={m(section.avoirs_ttc)} />
        <Chiffre libelle="CA net TTC" valeur={m(section.ca_net_ttc)} />
        <Chiffre libelle="Nombre de ventes" valeur={String(section.nombre_ventes)} />
        <Chiffre libelle="Panier moyen" valeur={m(section.panier_moyen)} />
      </Box>
      <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { md: "1fr 1fr" } }}>
        <Tableau
          titre="Par magasin"
          colonnes={["Magasin", "Ventes", "CA TTC"]}
          lignes={section.par_magasin.map((l) => [l.magasin, l.nombre, m(l.ca_ttc)])}
        />
        <Tableau
          titre="Par vendeur"
          colonnes={["Vendeur", "Ventes", "CA TTC"]}
          lignes={section.par_vendeur.map((l) => [l.vendeur, l.nombre, m(l.ca_ttc)])}
        />
        <Tableau
          titre="Par famille d'articles"
          colonnes={["Famille", "Quantité", "CA TTC"]}
          lignes={section.par_famille.map((l) => [l.famille, l.quantite, m(l.ca_ttc)])}
        />
        <Tableau
          titre="Encaissements"
          colonnes={["Mode", "Montant"]}
          lignes={section.encaissements.map((l) => [l.mode, m(l.montant)])}
        />
      </Box>
      <Tableau
        titre="Par jour"
        colonnes={["Jour", "Ventes", "CA TTC"]}
        lignes={section.par_jour.map((l) => [jour(l.jour), l.nombre, m(l.ca_ttc)])}
      />
    </Stack>
  );
}

/** Chiffre d'affaires et ventes de la période, pour les magasins de son périmètre. */
export function Reporting() {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });
  const [filtre, setFiltre] = useState({ du: debutDuMois(), au: aujourdhui(), magasin: "" });
  const rapport = useQuery({ queryKey: ["reporting", filtre], queryFn: () => lireReporting(filtre) });
  const decimales = (devise: string) =>
    magasins.data?.find((mag) => mag.pays.devise === devise)?.pays.decimales ?? 3;
  const changer = (champ: keyof typeof filtre) => (e: { target: { value: string } }) =>
    setFiltre({ ...filtre, [champ]: e.target.value });

  return (
    <Card>
      <CardContent>
        <Stack spacing={3}>
          <Typography variant="h6" component="h2">
            Reporting des ventes
          </Typography>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField
              type="date"
              label="Du"
              value={filtre.du}
              onChange={changer("du")}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <TextField
              type="date"
              label="Au"
              value={filtre.au}
              onChange={changer("au")}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <TextField
              select
              label="Magasin"
              value={filtre.magasin || "tous"}
              onChange={(e) => setFiltre({ ...filtre, magasin: e.target.value === "tous" ? "" : e.target.value })}
              sx={{ minWidth: 220 }}
            >
              <MenuItem value="tous">Tous mes magasins</MenuItem>
              {magasins.data?.map((mag) => (
                <MenuItem key={mag.id} value={mag.id}>
                  {mag.nom}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
          {rapport.isError && <Alert severity="error">{rapport.error.message}</Alert>}
          {rapport.data?.length === 0 && <Typography color="text.secondary">Aucun magasin dans votre périmètre.</Typography>}
          {rapport.data?.map((section) => (
            <Stack key={section.devise} spacing={2}>
              {rapport.data.length > 1 && <Typography variant="h6">Magasins en {section.devise}</Typography>}
              <Section section={section} monnaie={{ devise: section.devise, decimales: decimales(section.devise) }} />
            </Stack>
          ))}
        </Stack>
      </CardContent>
    </Card>
  );
}
