import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { Sav } from "./Sav";

const DOSSIER = {
  id: "d1",
  numero: "T01-S2026-000001",
  magasin: "m1",
  magasin_nom: "Tunis Centre",
  client: "c1",
  client_nom: "BEN SALAH Amel",
  client_telephone: "98 123 456",
  vente: null,
  vente_numero: null,
  article: null,
  designation: "Monture Ray-Ban, branche cassée",
  motif: "casse",
  motif_libelle: "Casse",
  description: "",
  sous_garantie: true,
  fournisseur: null,
  fournisseur_nom: null,
  etape: "recu",
  etape_libelle: "Reçu au magasin",
  est_ouvert: true,
  en_retard: true,
  retour_prevu_le: "2026-10-01",
  solution: "",
  cree_le: "2026-09-25T10:00:00+01:00",
  cree_par: "Sami",
  evenements: [
    { etape: "recu", etape_libelle: "Reçu au magasin", commentaire: "", le: "2026-09-25T10:00:00+01:00", par: "Sami" },
  ],
};

afterEach(() => vi.unstubAllGlobals());

const afficher = () =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Sav creer modifier filtreInitial="retard" />
    </QueryClientProvider>,
  );

test("liste les dossiers en retard et fait avancer l'étape", async () => {
  const appels: { url: string; corps?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      appels.push({ url, corps: init?.body ? JSON.parse(init.body as string) : undefined });
      if (init?.method === "POST")
        return Promise.resolve(new Response(JSON.stringify({ ...DOSSIER, etape: "atelier" })));
      return Promise.resolve(new Response(JSON.stringify({ results: [DOSSIER] })));
    }),
  );
  afficher();
  expect(await screen.findByText("BEN SALAH Amel")).toBeInTheDocument();
  expect(appels[0].url).toBe("/api/v1/sav/?retard=1");
  expect(screen.getByText(/En retard · 01\/10\/2026/)).toBeInTheDocument();

  fireEvent.click(screen.getByText("T01-S2026-000001"));
  fireEvent.mouseDown(screen.getByRole("combobox", { name: "Passer à l'étape" }));
  fireEvent.click(within(screen.getByRole("listbox")).getByRole("option", { name: "À l'atelier" }));
  fireEvent.click(screen.getByRole("button", { name: "Valider l'étape" }));
  await vi.waitFor(() =>
    expect(appels.find((a) => a.url === "/api/v1/sav/d1/etape/")?.corps).toMatchObject({ etape: "atelier" }),
  );
});

test("ouvre un dossier pour un client trouvé", async () => {
  const appels: { url: string; corps?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      appels.push({ url, corps: init?.body ? JSON.parse(init.body as string) : undefined });
      if (url === "/api/v1/magasins/")
        return Promise.resolve(new Response(JSON.stringify({ results: [{ id: "m1", nom: "Tunis", pays: {} }] })));
      if (url.startsWith("/api/v1/clients/"))
        return Promise.resolve(
          new Response(
            JSON.stringify({ results: [{ id: "c1", nom: "Ben Salah", prenom: "Amel", numero: 12, telephone: "" }] }),
          ),
        );
      if (init?.method === "POST") return Promise.resolve(new Response(JSON.stringify(DOSSIER), { status: 201 }));
      return Promise.resolve(new Response(JSON.stringify({ count: 0, results: [] })));
    }),
  );
  afficher();
  fireEvent.click(screen.getByRole("button", { name: "Nouveau dossier SAV" }));
  fireEvent.change(screen.getByLabelText("Client (nom, téléphone, n° de fiche)"), { target: { value: "ben" } });
  fireEvent.click(await screen.findByText(/BEN SALAH Amel · fiche n° 12/));
  fireEvent.change(screen.getByLabelText("Article rapporté"), { target: { value: "Lunettes solaires" } });
  fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  await vi.waitFor(() =>
    expect(appels.find((a) => a.url === "/api/v1/sav/" && a.corps)?.corps).toMatchObject({
      magasin: "m1",
      client: "c1",
      designation: "Lunettes solaires",
      motif: "casse",
    }),
  );
});
