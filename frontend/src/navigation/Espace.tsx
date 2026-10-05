import ArrowBack from "@mui/icons-material/ArrowBack";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import ButtonBase from "@mui/material/ButtonBase";
import Stack from "@mui/material/Stack";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useEffect, useMemo, useState } from "react";

import type { EtatSession } from "../api/auth";
import { modulesPour, RACCOURCIS, type Module, type Tuile } from "./modules";

/** Lit « #/vente/comptoir » : le module, puis l'écran ouvert s'il y en a un. */
function lireAdresse() {
  const [module = "", ecran = ""] = window.location.hash.replace(/^#\/?/, "").split("/");
  return { module, ecran };
}

function useAdresse() {
  const [adresse, setAdresse] = useState(lireAdresse);
  useEffect(() => {
    const suivre = () => setAdresse(lireAdresse());
    window.addEventListener("hashchange", suivre);
    return () => window.removeEventListener("hashchange", suivre);
  }, []);
  const aller = (module: string, ecran = "") => {
    window.location.hash = ecran ? `/${module}/${ecran}` : `/${module}`;
  };
  return [adresse, aller] as const;
}

/** Bandeau bordeaux en tête de chaque module, comme dans l'ancien logiciel. */
function Bandeau({ titre }: { titre: string }) {
  return (
    <Box
      sx={{
        px: 4,
        py: 1.5,
        borderRadius: 1,
        color: "common.white",
        background: "linear-gradient(180deg, #c45a5a 0%, #9b1c1c 45%, #7a1010 100%)",
      }}
    >
      <Typography variant="h4" component="h2" sx={{ fontWeight: 500 }}>
        {titre}
      </Typography>
    </Box>
  );
}

function BoutonTuile({ tuile, onOuvrir }: { tuile: Tuile; onOuvrir: () => void }) {
  const Icone = tuile.icone;
  const disponible = Boolean(tuile.ecran);
  return (
    <ButtonBase
      onClick={onOuvrir}
      disabled={!disponible}
      title={disponible ? undefined : "Bientôt disponible"}
      sx={{
        width: "100%",
        minHeight: 68,
        px: 1.5,
        gap: 1.5,
        justifyContent: "flex-start",
        textAlign: "center",
        border: 1,
        borderColor: "grey.400",
        borderRadius: 1,
        background: "linear-gradient(180deg, #fbfbfb 0%, #e6e6e6 100%)",
        boxShadow: "0 1px 2px rgba(0,0,0,0.15)",
        opacity: disponible ? 1 : 0.5,
        "&:hover": { background: "linear-gradient(180deg, #ffffff 0%, #dbe9f7 100%)", borderColor: "primary.main" },
      }}
    >
      <Icone sx={{ fontSize: 34, color: tuile.couleur, flexShrink: 0 }} />
      <Box sx={{ flexGrow: 1 }}>
        <Typography sx={{ fontFamily: "Georgia, 'Times New Roman', serif", fontSize: 16, lineHeight: 1.2 }}>
          {tuile.libelle}
        </Typography>
        {!disponible && (
          <Typography variant="caption" color="text.secondary">
            À venir
          </Typography>
        )}
      </Box>
    </ButtonBase>
  );
}

/** La page d'un module : bandeau, recherche et grille de boutons. */
function GrilleTuiles({ tuiles, onOuvrir }: { tuiles: Tuile[]; onOuvrir: (tuile: Tuile) => void }) {
  return (
    <Box
      sx={{
        display: "grid",
        gap: 1.5,
        gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
      }}
    >
      {tuiles.map((t) => (
        <BoutonTuile key={t.id} tuile={t} onOuvrir={() => onOuvrir(t)} />
      ))}
    </Box>
  );
}

function PageModule({ module, onOuvrir }: { module: Module; onOuvrir: (tuile: Tuile) => void }) {
  const [recherche, setRecherche] = useState("");
  const filtre = recherche.trim().toLocaleLowerCase("fr");
  const tuiles = module.tuiles.filter((t) => t.libelle.toLocaleLowerCase("fr").includes(filtre));
  // Module rangé en catégories (Administration) : un sous-onglet par catégorie, comme dans /admin/.
  const categories = [...new Set(module.tuiles.flatMap((t) => (t.categorie ? [t.categorie] : [])))];
  const [categorieChoisie, setCategorie] = useState(categories[0] ?? "");
  return (
    <Stack spacing={2}>
      <Bandeau titre={module.libelle} />
      <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
        <Typography component="label" htmlFor="recherche-module" sx={{ fontWeight: 700 }}>
          Rechercher
        </Typography>
        <TextField
          id="recherche-module"
          size="small"
          value={recherche}
          onChange={(e) => setRecherche(e.target.value)}
          sx={{ flexGrow: 1, bgcolor: "background.paper" }}
        />
      </Stack>
      {categories.length === 0 && <GrilleTuiles tuiles={tuiles} onOuvrir={onOuvrir} />}
      {categories.length > 0 && !filtre && (
        <>
          <Tabs
            value={categorieChoisie}
            onChange={(_, valeur: string) => setCategorie(valeur)}
            variant="scrollable"
            aria-label={`Catégories ${module.libelle}`}
            sx={{ borderBottom: 1, borderColor: "divider", minHeight: 40 }}
          >
            {categories.map((c) => (
              <Tab key={c} value={c} label={c} sx={{ minHeight: 40, fontWeight: 600 }} />
            ))}
          </Tabs>
          <GrilleTuiles tuiles={tuiles.filter((t) => t.categorie === categorieChoisie)} onOuvrir={onOuvrir} />
        </>
      )}
      {categories.length > 0 &&
        filtre &&
        categories
          .filter((c) => tuiles.some((t) => t.categorie === c))
          .map((c) => (
            <Stack key={c} spacing={1}>
              <Typography variant="h6" component="h4" sx={{ fontWeight: 600 }}>
                {c}
              </Typography>
              <GrilleTuiles tuiles={tuiles.filter((t) => t.categorie === c)} onOuvrir={onOuvrir} />
            </Stack>
          ))}
      {tuiles.length === 0 && <Typography color="text.secondary">Aucune fonction ne correspond.</Typography>}
    </Stack>
  );
}

/** Espace de travail : onglets horizontaux par module, puis l'écran choisi. */
export function Espace({ session }: { session: EtatSession }) {
  const modules = useMemo(() => modulesPour(session), [session]);
  const [adresse, aller] = useAdresse();
  const module = modules.find((m) => m.id === adresse.module) ?? modules[0];
  const tuile = module.tuiles.find((t) => t.id === adresse.ecran && t.ecran);
  const raccourcis = RACCOURCIS.filter((r) =>
    modules.find((m) => m.id === r.module)?.tuiles.some((t) => t.id === r.tuile && t.ecran),
  );

  return (
    <Stack spacing={2}>
      <Box sx={{ borderBottom: 1, borderColor: "divider", bgcolor: "background.paper" }}>
        <Tabs
          value={module.id}
          onChange={(_, valeur: string) => aller(valeur)}
          variant="scrollable"
          aria-label="Modules"
        >
          {modules.map((m) => (
            <Tab key={m.id} value={m.id} label={m.libelle} sx={{ fontSize: 16, fontWeight: 600 }} />
          ))}
        </Tabs>
        {raccourcis.length > 0 && (
          <Stack
            component="nav"
            aria-label="Raccourcis"
            direction="row"
            sx={{ flexWrap: "wrap", gap: 1, px: 1, py: 1, borderTop: 1, borderColor: "divider" }}
          >
            {raccourcis.map((r) => {
              const actif = module.id === r.module && tuile?.id === r.tuile;
              return (
                <Button
                  key={r.tuile}
                  size="small"
                  variant={actif ? "contained" : "outlined"}
                  aria-current={actif ? "page" : undefined}
                  onClick={() => aller(r.module, r.tuile)}
                  sx={{ textTransform: "none" }}
                >
                  {r.libelle}
                </Button>
              );
            })}
          </Stack>
        )}
      </Box>
      {tuile?.ecran ? (
        <Stack spacing={2}>
          <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
            <Button startIcon={<ArrowBack />} onClick={() => aller(module.id)}>
              {module.libelle}
            </Button>
            <Typography variant="h6" component="p">
              {tuile.libelle}
            </Typography>
          </Stack>
          <Box key={tuile.id}>{tuile.ecran()}</Box>
        </Stack>
      ) : (
        <PageModule key={module.id} module={module} onOuvrir={(t) => aller(module.id, t.id)} />
      )}
    </Stack>
  );
}
