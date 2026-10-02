import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";

import { Caisse } from "./Caisse";

const MAGASIN = { id: "m1", code: "M01", nom: "Lille", region: "Nord", ville: "Lille" };
const MONTURE = {
  id: "a1",
  reference: "MON-1",
  libelle: "Monture titane",
  famille: "monture",
  prix_vente_ttc: "149.90",
  taux_tva: "20.00",
  stock: 3,
};

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Caisse />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

function simuler(reponseVente: () => Promise<Response>) {
  const ventes: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (url === "/api/v1/magasins/") return json({ results: [MAGASIN] });
      if (url.startsWith("/api/v1/articles/")) return json({ results: [MONTURE] });
      ventes.push(JSON.parse(init?.body as string));
      return reponseVente();
    }),
  );
  return ventes;
}

async function remplirPanier() {
  afficher();
  fireEvent.change(await screen.findByLabelText(/Rechercher un article/), { target: { value: "mon" } });
  fireEvent.click(await screen.findByRole("button", { name: "Ajouter" }));
  fireEvent.click(screen.getByRole("button", { name: "Ajouter un" }));
}

test("encaisse le panier et affiche le numéro de facture", async () => {
  const ventes = simuler(() => json({ id: "v1", numero: "M01-2026-000001", total_ttc: "299.80", lignes: [] }, 201));
  await remplirPanier();

  expect(screen.getByText("Total : 299.80 €")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Encaisser" }));

  expect(await screen.findByText(/facture M01-2026-000001/)).toBeInTheDocument();
  expect(ventes).toEqual([
    {
      magasin: "m1",
      lignes: [{ article: "a1", quantite: 2 }],
      paiements: [{ mode: "carte", montant: "299.80" }],
    },
  ]);
});

test("affiche le refus de l'API", async () => {
  simuler(() => json({ detail: "Stock insuffisant pour MON-1." }, 400));
  await remplirPanier();
  fireEvent.click(screen.getByRole("button", { name: "Encaisser" }));

  expect(await screen.findByText("Stock insuffisant pour MON-1.")).toBeInTheDocument();
});
