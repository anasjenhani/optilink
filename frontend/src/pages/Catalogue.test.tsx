import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { Catalogue } from "./Catalogue";

const MAGASIN = {
  id: "m1",
  code: "T01",
  nom: "Tunis Centre",
  societe: "",
  ville: "Tunis",
  pays: { devise: "TND", decimales: 3 },
};
const MONTURE = {
  id: "a1",
  reference: "MON-RB-001",
  libelle: "Monture Ray-Ban",
  famille: "monture",
  description: "Ray-Ban RB5154 · écaille · 51□21-145",
  caracteristiques: { marque: "Ray-Ban" },
  sur_commande: false,
  prix_vente_ttc: "489.000",
  taux_tva: "19.00",
  devise: "TND",
  stock: 10,
};
const VERRE = {
  ...MONTURE,
  id: "a2",
  reference: "VER-PR-007",
  libelle: "Verre progressif",
  famille: "verre",
  description: "Essilor Varilux Comfort · Progressif",
  sur_commande: true,
  stock: 0,
};

afterEach(() => vi.unstubAllGlobals());

test("affiche le catalogue par famille avec les caractéristiques", async () => {
  const appels: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      appels.push(url);
      const donnees = url.startsWith("/api/v1/magasins/")
        ? { results: [MAGASIN] }
        : { results: url.includes("famille=verre") ? [VERRE] : [MONTURE] };
      return Promise.resolve(new Response(JSON.stringify(donnees), { status: 200 }));
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Catalogue />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Ray-Ban RB5154 · écaille · 51□21-145")).toBeInTheDocument();
  expect(appels).toContain("/api/v1/articles/?magasin=m1&recherche=&famille=monture");

  fireEvent.mouseDown(screen.getByRole("combobox", { name: "Famille" }));
  fireEvent.click(within(await screen.findByRole("listbox")).getByText("Verres"));
  expect(await screen.findByText("Essilor Varilux Comfort · Progressif")).toBeInTheDocument();
  expect(screen.getByText("sur commande")).toBeInTheDocument();
});

const json = (donnees: unknown) => Promise.resolve(new Response(JSON.stringify(donnees), { status: 200 }));
const FICHE_VERRE = {
  id: "a2",
  reference: "VER-PR-007",
  libelle: "Verre progressif",
  famille: "verre",
  code_barres: "",
  fournisseur: "f1",
  fournisseur_nom: "Essilor Tunisie",
  fournisseur_code: 4,
  reference_fournisseur: "",
  est_actif: true,
  stockable: false,
  suivi_numero_serie: false,
  promotion: false,
  etui_special: false,
  fodec: false,
  observation: "",
  monture: null,
  verre: { marque: "Essilor", gamme: "Varilux Comfort", geometrie: "progressif", indice: "1.600", matiere: "" },
  lentille: null,
  prix: null,
  dernier_achat: null,
  stocks: [],
  cree_par: null,
  cree_le: "2026-10-05T10:00:00Z",
};

test("verres : « Nouvel article » et un clic sur la ligne ouvrent la fiche article, selon les droits", async () => {
  const appels: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      appels.push(url);
      if (url.startsWith("/api/v1/magasins/")) return json({ results: [MAGASIN] });
      if (url.startsWith("/api/v1/fiches-articles/a2/")) return json(FICHE_VERRE);
      return json({ results: [VERRE] });
    }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const { rerender } = render(
    <QueryClientProvider client={client}>
      <Catalogue familleInitiale="verre" />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Essilor Varilux Comfort · Progressif")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Nouvel article" })).not.toBeInTheDocument();

  rerender(
    <QueryClientProvider client={client}>
      <Catalogue familleInitiale="verre" fiche={{ creer: true, modifier: true }} />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Nouvel article" }));
  const nouvelle = await screen.findByRole("dialog");
  expect(within(nouvelle).getByText("Fiche Verre")).toBeInTheDocument();
  expect(within(nouvelle).getByLabelText(/Géométrie/)).toBeInTheDocument();
  fireEvent.click(within(nouvelle).getByRole("button", { name: "Annuler" }));
  await vi.waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

  fireEvent.click(screen.getByText("Verre progressif"));
  const fiche = await screen.findByRole("dialog");
  expect(await within(fiche).findByLabelText("Gamme")).toHaveValue("Varilux Comfort");
  expect(appels).toContain("/api/v1/fiches-articles/a2/?magasin=m1");
  expect(within(fiche).getByRole("button", { name: "Valider [F4]" })).toBeInTheDocument();
});

test("montures : le bouton reste « Nouvelle monture » et ouvre la fiche monture", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.startsWith("/api/v1/magasins/")) return json({ results: [MAGASIN] });
      if (url.includes("suggestions"))
        return json({ marque: [], modele: [], forme: [], couleur: [], couleur_verres: [] });
      return json({ results: [MONTURE] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Catalogue fiche={{ creer: true, modifier: false }} />
    </QueryClientProvider>,
  );
  await screen.findByText("Monture Ray-Ban");
  expect(screen.queryByRole("button", { name: "Nouvel article" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Nouvelle monture" }));
  expect(await screen.findByText("Fiche Monture")).toBeInTheDocument();
});
