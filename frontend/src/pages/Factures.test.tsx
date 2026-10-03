import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";

import { Factures } from "./Factures";

const TUNIS = {
  id: "m1",
  code: "T01",
  nom: "Tunis",
  societe: "Optique de Tunis",
  ville: "Tunis",
  pays: {
    code: "TN",
    nom: "Tunisie",
    devise: "TND",
    decimales: 3,
    indicatif_telephonique: "+216",
    timbre_fiscal: "1.000",
    libelle_identifiant_prescripteur: "N° d'inscription à l'Ordre des médecins",
  },
};
const CLIENT = { id: "c1", nom: "OPTIQUE SERVICES SARL", matricule_fiscal: "1234567/A/M/000" };

function vente(reste: string) {
  return { id: "v1", numero: "T01-T2026-000001", devise: "TND", total_ttc: "289.500", reste_a_payer: reste, facture: null, client: CLIENT, lignes: [] };
}

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

afterEach(() => vi.unstubAllGlobals());

function afficher(reste: string) {
  const factures: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (url === "/api/v1/magasins/") return json({ results: [TUNIS] });
      if (url.startsWith("/api/v1/ventes/")) return json({ results: [vente(reste)] });
      factures.push(JSON.parse(init?.body as string));
      return json(
        { id: "f1", numero: "T01-F2026-000001", vente: "T01-T2026-000001", client: CLIENT, devise: "TND", total_ttc: "289.500", timbre_fiscal: "1.000", net_a_payer: "290.500" },
        201,
      );
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Factures />
    </QueryClientProvider>,
  );
  return factures;
}

async function chercherTicket() {
  fireEvent.change(screen.getByLabelText("N° de ticket"), { target: { value: "T01-T2026-000001" } });
  fireEvent.click(screen.getByRole("button", { name: "Rechercher" }));
  await screen.findByText(/Ticket T01-T2026-000001/);
}

test("facture une commande soldée, timbre payé par le client", async () => {
  const factures = afficher("0.000");
  await chercherTicket();
  expect(await screen.findByText(/Timbre fiscal à encaisser : 1,000\sTND/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Générer la facture" }));

  expect(await screen.findByText(/Facture T01-F2026-000001/)).toBeInTheDocument();
  expect(screen.getByText(/290,500\sTND/)).toBeInTheDocument();
  expect(factures).toEqual([{ vente: "v1", client: "c1", mode_paiement_timbre: "especes" }]);
});

test("refuse de facturer une commande pas entièrement payée", async () => {
  afficher("100.000");
  await chercherTicket();
  expect(screen.getByText(/pas entièrement payée : reste 100,000\sTND/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Générer la facture" })).not.toBeInTheDocument();
});
