import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import FormControlLabel from "@mui/material/FormControlLabel";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import Print from "@mui/icons-material/Print";
import JsBarcode from "jsbarcode";
import { useEffect, useRef, useState } from "react";

/** Formats d'étiquettes courants des imprimantes code-barres (largeur × hauteur, mm). */
export const FORMATS = [
  { valeur: "50x25", libelle: "50 × 25 mm", largeur: 50, hauteur: 25 },
  { valeur: "38x25", libelle: "38 × 25 mm", largeur: 38, hauteur: 25 },
  { valeur: "57x32", libelle: "57 × 32 mm", largeur: 57, hauteur: 32 },
  { valeur: "40x20", libelle: "40 × 20 mm", largeur: 40, hauteur: 20 },
] as const;

const CLE_FORMAT = "optilink.etiquette.format";

function lireFormat() {
  try {
    return localStorage.getItem(CLE_FORMAT) ?? FORMATS[0].valeur;
  } catch {
    return FORMATS[0].valeur;
  }
}

function garderFormat(valeur: string) {
  try {
    localStorage.setItem(CLE_FORMAT, valeur);
  } catch {
    // Navigation privée : le format n'est pas retenu.
  }
}

/** EAN-13 si le code en est un (clé juste), sinon Code 128 (codes fournisseurs avec lettres…). */
export function formatCode(code: string): "EAN13" | "CODE128" {
  if (!/^\d{13}$/.test(code)) return "CODE128";
  const somme = [...code.slice(0, 12)].reduce((s, c, i) => s + Number(c) * (i % 2 ? 3 : 1), 0);
  return (10 - (somme % 10)) % 10 === Number(code[12]) ? "EAN13" : "CODE128";
}

export function dessiner(svg: SVGSVGElement, code: string, options: { hauteur?: number; largeur?: number } = {}) {
  JsBarcode(svg, code, {
    format: formatCode(code),
    height: options.hauteur ?? 60,
    width: options.largeur ?? 2,
    fontSize: 14,
    margin: 4,
    flat: true,
  });
}

const echapper = (texte: string) =>
  texte.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] as string);

/** Page d'impression : une étiquette par page, à la taille du rouleau. */
export function pageEtiquettes(p: {
  svg: string;
  titre: string;
  reference: string;
  prix: string;
  copies: number;
  largeur: number;
  hauteur: number;
}) {
  const etiquette = `<div class="e"><div class="t">${echapper(p.titre)}</div>${p.svg}<div class="b"><span>${echapper(
    p.reference,
  )}</span><strong>${echapper(p.prix)}</strong></div></div>`;
  return `<!doctype html><html><head><meta charset="utf-8"><title>Étiquettes</title><style>
@page { size: ${p.largeur}mm ${p.hauteur}mm; margin: 0; }
html, body { margin: 0; padding: 0; font-family: Arial, sans-serif; }
.e { width: ${p.largeur}mm; height: ${p.hauteur}mm; box-sizing: border-box; padding: 1mm 1.5mm;
  display: flex; flex-direction: column; justify-content: space-between; overflow: hidden;
  page-break-after: always; break-after: page; }
.e:last-child { page-break-after: auto; break-after: auto; }
.t { font-size: 7pt; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
svg { width: 100%; height: auto; max-height: ${p.hauteur - 9}mm; }
.b { display: flex; justify-content: space-between; font-size: 7pt; }
</style></head><body>${etiquette.repeat(p.copies)}</body></html>`;
}

/**
 * Onglet « Code A Barre » : le code dessiné et l'impression d'étiquettes. L'impression ouvre la fenêtre
 * d'impression du navigateur au format de l'étiquette : choisir l'imprimante code-barres (le navigateur la
 * retient pour la fois suivante).
 */
export function EtiquetteCodeBarres({
  code,
  titre,
  reference,
  prix,
}: {
  code: string;
  titre: string;
  reference: string;
  prix: string;
}) {
  const apercu = useRef<SVGSVGElement>(null);
  const [format, setFormat] = useState(lireFormat);
  const [copies, setCopies] = useState("1");
  const [avecPrix, setAvecPrix] = useState(true);
  const [erreur, setErreur] = useState("");

  useEffect(() => {
    if (!apercu.current || !code) return;
    try {
      dessiner(apercu.current, code);
      setErreur("");
    } catch {
      setErreur(`Le code « ${code} » ne peut pas être dessiné.`);
    }
  }, [code]);

  if (!code)
    return (
      <Typography color="text.secondary" sx={{ py: 2 }}>
        Le code monture est attribué à la validation de la fiche : validez-la, puis rouvrez-la pour imprimer.
      </Typography>
    );

  const imprimer = () => {
    const choisi = FORMATS.find((f) => f.valeur === format) ?? FORMATS[0];
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    dessiner(svg, code, { hauteur: 50, largeur: 2 });
    const cadre = document.createElement("iframe");
    cadre.setAttribute("aria-hidden", "true");
    cadre.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0";
    document.body.appendChild(cadre);
    const doc = cadre.contentDocument;
    if (!doc || !cadre.contentWindow) return;
    doc.open();
    doc.write(
      pageEtiquettes({
        svg: svg.outerHTML,
        titre,
        reference,
        prix: avecPrix ? prix : "",
        copies: Math.min(Math.max(Number(copies) || 1, 1), 200),
        largeur: choisi.largeur,
        hauteur: choisi.hauteur,
      }),
    );
    doc.close();
    const fenetre = cadre.contentWindow;
    fenetre.onafterprint = () => cadre.remove();
    setTimeout(() => {
      fenetre.focus();
      fenetre.print();
    }, 100);
  };

  return (
    <Stack direction="row" spacing={4} useFlexGap sx={{ flexWrap: "wrap", alignItems: "flex-start" }}>
      <Box sx={{ bgcolor: "common.white", p: 1, border: 1, borderColor: "grey.300", borderRadius: 1 }}>
        <svg ref={apercu} role="img" aria-label={`Code-barres ${code}`} />
      </Box>
      <Stack spacing={2}>
        {erreur && <Alert severity="error">{erreur}</Alert>}
        <Stack direction="row" spacing={2}>
          <TextField
            select
            size="small"
            label="Format étiquette"
            value={format}
            onChange={(e) => {
              setFormat(e.target.value);
              garderFormat(e.target.value);
            }}
            sx={{ width: 170 }}
          >
            {FORMATS.map((f) => (
              <MenuItem key={f.valeur} value={f.valeur}>
                {f.libelle}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            size="small"
            label="Nombre d'étiquettes"
            value={copies}
            onChange={(e) => setCopies(e.target.value.replace(/\D/g, ""))}
            slotProps={{ htmlInput: { inputMode: "numeric" } }}
            sx={{ width: 160 }}
          />
        </Stack>
        <FormControlLabel
          label="Prix sur l'étiquette"
          control={<Checkbox size="small" checked={avecPrix} onChange={(e) => setAvecPrix(e.target.checked)} />}
        />
        <Box>
          <Button variant="contained" startIcon={<Print />} onClick={imprimer} disabled={Boolean(erreur)}>
            Imprimer
          </Button>
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 380 }}>
          Dans la fenêtre d'impression, choisissez l'imprimante code-barres : le navigateur la garde pour les
          impressions suivantes.
        </Typography>
      </Stack>
    </Stack>
  );
}
