import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { MouvementsStock } from "./MouvementsStock";

const TUNIS = { id: "m1", nom: "Tunis", pays: { code: "TN", devise: "TND", decimales: 3 } };
const SFAX = { id: "m2", nom: "Sfax", pays: { code: "TN", devise: "TND", decimales: 3 } };
const RECEPTION = {
  id: 7,
  magasin: "m1",
  magasin_nom: "Tunis",
  article: "a1",
  article_reference: "MON-1",
  article_libelle: "Monture titane",
  quantite: 5,
  type: "reception",
  type_libelle: "Réception",
  reference: "BL-42",
  utilisateur: "magasinier",
  horodatage: "2026-10-01T09:30:00Z",
};
const VENTE = {
  ...RECEPTION,
  id: 8,
  quantite: -1,
  type: "vente",
  type_libelle: "Vente",
  reference: "T01-T2026-000003",
  utilisateur: "",
};

function json(donnees: unknown) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status: 200 }));
}

afterEach(() => vi.unstubAllGlobals());

function afficher(count = 2) {
  const urls: string[] = [];
  const envois: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method && init.method !== "GET") envois.push(url);
      urls.push(url);
      if (url === "/api/v1/magasins/") return json({ results: [TUNIS, SFAX] });
      return json({ count, results: [RECEPTION, VENTE] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MouvementsStock />
    </QueryClientProvider>,
  );
  return Object.assign(urls, { envois });
}

const derniere = (urls: string[]) => urls.filter((u) => u.startsWith("/api/v1/mouvements-stock/")).at(-1);

test("liste les mouvements en lecture seule", async () => {
  const urls = afficher();
  await screen.findByText("BL-42");
  const lignes = within(screen.getByRole("table", { name: "Mouvements de stock" })).getAllByRole("row");
  expect(within(lignes[1]).getByText("MON-1")).toBeInTheDocument();
  expect(within(lignes[1]).getByText("Monture titane")).toBeInTheDocument();
  expect(within(lignes[1]).getByText("Réception")).toBeInTheDocument();
  expect(within(lignes[1]).getByText("+5")).toBeInTheDocument();
  expect(within(lignes[1]).getByText("BL-42")).toBeInTheDocument();
  expect(within(lignes[1]).getByText("magasinier")).toBeInTheDocument();
  expect(within(lignes[2]).getByText("-1")).toBeInTheDocument();
  expect(screen.getByText("2 mouvements")).toBeInTheDocument();
  expect(derniere(urls)).toBe("/api/v1/mouvements-stock/?page=1");
  // Rien à modifier ni à supprimer : aucun bouton d'action sur l'écran.
  expect(screen.queryByRole("button", { name: /Modifier|Supprimer|Enregistrer/ })).not.toBeInTheDocument();
  expect(urls.envois).toEqual([]);
});

test("filtre par magasin, article, type et période", async () => {
  const urls = afficher();
  await screen.findAllByText("Monture titane");
  fireEvent.mouseDown(screen.getByRole("combobox", { name: "Magasin" }));
  fireEvent.click(await screen.findByRole("option", { name: "Sfax" }));
  fireEvent.change(screen.getByLabelText("Article"), { target: { value: "MON" } });
  fireEvent.mouseDown(screen.getByRole("combobox", { name: "Type" }));
  fireEvent.click(await screen.findByRole("option", { name: "Transfert reçu" }));
  fireEvent.change(screen.getByLabelText("Du"), { target: { value: "2026-10-01" } });
  fireEvent.change(screen.getByLabelText("Au"), { target: { value: "2026-10-05" } });
  await waitFor(() =>
    expect(derniere(urls)).toBe(
      "/api/v1/mouvements-stock/?page=1&magasin=m2&article=MON&type=transfert_entree&du=2026-10-01&au=2026-10-05",
    ),
  );
});

test("pagine les mouvements par 50", async () => {
  const urls = afficher(120);
  expect(await screen.findByText("Page 1 / 3")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Suivante" }));
  await waitFor(() => expect(derniere(urls)).toBe("/api/v1/mouvements-stock/?page=2"));
  expect(await screen.findByText("Page 2 / 3")).toBeInTheDocument();
});
