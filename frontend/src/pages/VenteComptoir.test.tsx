import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { VenteComptoir } from "./VenteComptoir";

const TUNISIE = { code: "TN", nom: "Tunisie", devise: "TND", decimales: 3 };
const MAGASIN = { id: "m1", code: "T01", nom: "Tunis", societe: "Optique de Tunis", ville: "Tunis", pays: TUNISIE };
const CLIENT = {
  id: "c1",
  numero: 42,
  reference_externe: "",
  nom: "Ben Ali",
  prenom: "Sami",
  telephone: "98123456",
  telephone_2: "",
  ville: "Tunis",
  notes: "Client fidèle",
  solde: "-0.010",
};
const SOLAIRE = {
  id: "a1",
  reference: "SOL-1",
  libelle: "Ray-Ban Aviator",
  famille: "monture",
  prix_vente_ttc: "420.000",
  taux_tva: "19.00",
  devise: "TND",
  stock: 2,
};

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

function simuler() {
  const appels: { url: string; init?: RequestInit }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      appels.push({ url, init });
      if (url === "/api/v1/magasins/") return json({ results: [MAGASIN] });
      if (url.startsWith("/api/v1/clients/")) return json({ count: 1, results: [CLIENT] });
      if (url.startsWith("/api/v1/articles/")) return json({ results: [SOLAIRE] });
      return json({
        id: "v1",
        numero: "T01-T-2026-000001",
        devise: "TND",
        total_ttc: "420.000",
        reste_a_payer: "0.000",
        statut: "livree",
        peniche: null,
      });
    }),
  );
  return appels;
}

function afficher(creerClient = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <VenteComptoir creerClient={creerClient} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("client retrouvé dans le tableau par son n° de fiche, puis type de vente, puis encaissement", async () => {
  const appels = simuler();
  afficher();

  fireEvent.change(screen.getByLabelText("Filtrer N° Fiche"), { target: { value: "42" } });
  await waitFor(() => expect(appels.some((a) => a.url.includes("fiche=42"))).toBe(true));
  const ligne = (await screen.findByText("BEN ALI SAMI")).closest("tr")!;
  expect(within(ligne).getByText("-0,010")).toBeInTheDocument();
  expect(within(ligne).getByText("Client fidèle")).toBeInTheDocument();
  fireEvent.click(ligne);

  fireEvent.click(screen.getByRole("button", { name: /Lunettes solaires/ }));
  fireEvent.click(await screen.findByRole("button", { name: "Ajouter" }));
  expect(appels.some((a) => a.url.includes("type_vente=solaire"))).toBe(true);
  expect(screen.getByText("Client : BEN ALI Sami · fiche n° 42")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Encaisser" }));
  expect(await screen.findByText(/Ticket T01-T-2026-000001/)).toBeInTheDocument();
  const vente = appels.find((a) => a.url === "/api/v1/ventes/")!;
  expect(JSON.parse(vente.init?.body as string)).toMatchObject({ client: "c1", magasin: "m1" });
});

test("nouveau client : la fiche s'ouvre ; sans le droit, seul le client de passage reste", async () => {
  simuler();
  afficher();
  fireEvent.click(screen.getByRole("button", { name: "Nouveau Client" }));
  expect(await screen.findByRole("form", { name: "Nouveau client" })).toBeInTheDocument();

  vi.unstubAllGlobals();
  document.body.innerHTML = "";
  simuler();
  afficher(false);
  expect(screen.queryByRole("button", { name: "Nouveau Client" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Client de passage" }));
  expect(screen.getByRole("button", { name: /Produits et accessoires/ })).toBeInTheDocument();
});
