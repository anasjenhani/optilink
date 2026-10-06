import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { imprimer } from "./FactureAchat";
import { Factures } from "./Factures";

vi.mock("./FactureAchat", async (original) => ({ ...(await original<object>()), imprimer: vi.fn() }));

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
  return {
    id: "v1",
    numero: "T01-T2026-000001",
    devise: "TND",
    total_ttc: "289.500",
    reste_a_payer: reste,
    facture: null,
    client: CLIENT,
    lignes: [],
  };
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
      if (init?.method !== "POST") return json({ count: 0, results: [] });
      factures.push(JSON.parse(init?.body as string));
      return json(
        {
          id: "f1",
          numero: "T01-F2026-000001",
          vente: "T01-T2026-000001",
          client: CLIENT,
          devise: "TND",
          total_ttc: "289.500",
          timbre_fiscal: "1.000",
          net_a_payer: "290.500",
        },
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

const EMISE = {
  id: "f7",
  numero: "T01-F2026-000007",
  magasin: "T01",
  vente: "T01-T2026-000042",
  client: {
    id: "c1",
    nom: "OPTIQUE SERVICES SARL",
    adresse: "12 rue de Marseille, Tunis",
    matricule_fiscal: "1234567/A/M/000",
  },
  cree_le: "2026-03-14T10:30:00+01:00",
  emise_par: "caissier",
  devise: "TND",
  total_ht: "243.277",
  total_tva: "46.223",
  total_ttc: "289.500",
  timbre_fiscal: "1.000",
  net_a_payer: "290.500",
  mode_paiement_timbre: "especes",
  lignes: [
    {
      id: 3,
      libelle: "Monture titane",
      quantite: 1,
      quantite_reprise: 0,
      prix_unitaire_ttc: "289.500",
      remise_pct: "0.00",
      taux_tva: "19.00",
      total_ttc: "289.500",
    },
  ],
};

function consulter(props: { generer?: boolean; consulter?: boolean } = {}) {
  const appels: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      appels.push(`${init?.method ?? "GET"} ${url}`);
      if (url === "/api/v1/magasins/") return json({ results: [TUNIS] });
      if (url === "/api/v1/factures/f7/") return json(EMISE);
      return json({ count: 1, results: [EMISE] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Factures {...props} />
    </QueryClientProvider>,
  );
  return appels;
}

test("liste les factures émises, filtre par numéro, ouvre le détail et réimprime", async () => {
  const appels = consulter();
  fireEvent.click(screen.getByRole("tab", { name: "Factures émises" }));
  const ligne = (await screen.findByText("T01-F2026-000007")).closest("tr")!;
  expect(ligne).toHaveTextContent("OPTIQUE SERVICES SARL");
  expect(ligne).toHaveTextContent("T01");
  expect(ligne).toHaveTextContent(/289,500\sTND/);
  expect(appels).toContain("GET /api/v1/factures/?page=1");

  fireEvent.change(screen.getByLabelText("N° de facture"), { target: { value: "T01-F2026-000007" } });
  await waitFor(() => expect(appels).toContain("GET /api/v1/factures/?page=1&numero=T01-F2026-000007"));

  fireEvent.click(ligne);
  const detail = await screen.findByRole("dialog");
  expect(await within(detail).findByText("Monture titane")).toBeInTheDocument();
  expect(within(detail).getByText(/Net à payer 290,500\sTND/)).toBeInTheDocument();
  expect(within(detail).queryByRole("button", { name: /Supprimer|Modifier/ })).not.toBeInTheDocument();
  fireEvent.click(within(detail).getByRole("button", { name: "Imprimer" }));
  expect(imprimer).toHaveBeenCalledWith(expect.stringContaining("Facture T01-F2026-000007"));
  expect(vi.mocked(imprimer).mock.calls[0][0]).toContain("12 rue de Marseille, Tunis");
  expect(appels.filter((a) => a.startsWith("POST"))).toEqual([]);
});

test("sans droit de facturer, seule la consultation s'affiche", async () => {
  consulter({ generer: false });
  expect(await screen.findByText("T01-F2026-000007")).toBeInTheDocument();
  expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("N° de ticket")).not.toBeInTheDocument();
});

test("sans droit de consulter, pas d'onglet des factures émises", () => {
  consulter({ consulter: false });
  expect(screen.getByLabelText("N° de ticket")).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "Factures émises" })).not.toBeInTheDocument();
});
