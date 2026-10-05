import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { Avoirs } from "./Avoirs";
import { imprimer } from "./FactureAchat";

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
    libelle_identifiant_prescripteur: "",
  },
};

function vente(statut: string) {
  return {
    id: "v1",
    numero: "T01-T2026-000001",
    devise: "TND",
    total_ttc: "579.000",
    reste_a_payer: "0.000",
    statut,
    livraison_prevue_le: null,
    facture: null,
    client: null,
    lignes: [{ id: 7, libelle: "Monture titane", quantite: 2, quantite_reprise: 0, total_ttc: "579.000" }],
  };
}

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

afterEach(() => vi.unstubAllGlobals());

function afficher(statut: string) {
  const envois: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (url === "/api/v1/magasins/") return json({ results: [TUNIS] });
      if (init?.method === "POST") {
        envois.push(JSON.parse(init.body as string));
        return json(
          {
            id: "a1",
            numero: "T01-A2026-000001",
            vente: "T01-T2026-000001",
            facture: null,
            annulation: false,
            motif: "",
            devise: "TND",
            total_ttc: "289.500",
            montant_rembourse: "289.500",
            mode_remboursement: "especes",
          },
          201,
        );
      }
      return json({ results: [vente(statut)] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Avoirs />
    </QueryClientProvider>,
  );
  return envois;
}

async function chercher() {
  fireEvent.change(screen.getByLabelText("N° de ticket ou de commande"), { target: { value: "T01-T2026-000001" } });
  fireEvent.click(screen.getByRole("button", { name: "Rechercher" }));
  await screen.findByText(/T01-T2026-000001 :/);
}

test("reprend un article défectueux sans le remettre en stock", async () => {
  const envois = afficher("livree");
  await chercher();
  fireEvent.change(screen.getByLabelText("Quantité Monture titane"), { target: { value: "1" } });
  fireEvent.click(screen.getByRole("checkbox", { name: "Remettre en stock Monture titane" }));
  fireEvent.change(screen.getByLabelText("Motif"), { target: { value: "Charnière cassée" } });
  fireEvent.click(screen.getByRole("button", { name: "Émettre l'avoir" }));

  expect(await screen.findByText(/Avoir T01-A2026-000001.*289,500\sTND remboursé/)).toBeInTheDocument();
  expect(envois).toEqual([
    {
      vente: "v1",
      motif: "Charnière cassée",
      mode_remboursement: "especes",
      lignes: [{ ligne: 7, quantite: 1, remis_en_stock: false }],
    },
  ]);
});

test("une commande non livrée ne peut qu'être annulée", async () => {
  const envois = afficher("en_commande");
  await chercher();
  expect(screen.queryByRole("button", { name: "Émettre l'avoir" })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Motif"), { target: { value: "Client a changé d'avis" } });
  fireEvent.click(screen.getByRole("button", { name: "Annuler la commande" }));
  await screen.findByText(/Avoir T01-A2026-000001/);
  expect(envois).toEqual([
    { vente: "v1", motif: "Client a changé d'avis", mode_remboursement: "especes", annulation: true },
  ]);
});

const EMIS = {
  id: "a3",
  numero: "T01-A2026-000003",
  magasin: "T01",
  vente: "T01-T2026-000042",
  facture: "T01-F2026-000007",
  client: { id: "c1", nom: "BEN SALAH Amira", societe: "", matricule_fiscal: "" },
  annulation: false,
  motif: "Charnière cassée",
  cree_le: "2026-03-20T16:05:00+01:00",
  emis_par: "caissier",
  devise: "TND",
  total_ht: "243.277",
  total_tva: "46.223",
  total_ttc: "289.500",
  montant_rembourse: "289.500",
  mode_remboursement: "especes",
  lignes: [{ libelle: "Monture titane", quantite: 1, taux_tva: "19.00", total_ttc: "289.500", remis_en_stock: false }],
};

function consulter(props: { emettre?: boolean; consulter?: boolean } = {}) {
  const appels: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      appels.push(`${init?.method ?? "GET"} ${url}`);
      if (url === "/api/v1/magasins/") return json({ results: [TUNIS] });
      if (url === "/api/v1/avoirs/a3/") return json(EMIS);
      return json({ count: 1, results: [EMIS] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Avoirs {...props} />
    </QueryClientProvider>,
  );
  return appels;
}

test("liste les avoirs émis, filtre par numéro et par type, ouvre le détail et réimprime", async () => {
  const appels = consulter();
  fireEvent.click(screen.getByRole("tab", { name: "Avoirs émis" }));
  const ligne = (await screen.findByText("T01-A2026-000003")).closest("tr")!;
  expect(ligne).toHaveTextContent("Reprise");
  expect(ligne).toHaveTextContent("BEN SALAH Amira");
  expect(ligne).toHaveTextContent(/289,500\sTND/);
  expect(appels).toContain("GET /api/v1/avoirs/?page=1");

  fireEvent.change(screen.getByLabelText("N° d'avoir"), { target: { value: "T01-A2026-000003" } });
  fireEvent.mouseDown(screen.getByRole("combobox", { name: "Type" }));
  fireEvent.click(await screen.findByRole("option", { name: "Annulations" }));
  await waitFor(() => expect(appels).toContain("GET /api/v1/avoirs/?page=1&numero=T01-A2026-000003&annulation=true"));

  fireEvent.click(ligne);
  const detail = await screen.findByRole("dialog");
  expect(await within(detail).findByText("Monture titane")).toBeInTheDocument();
  expect(within(detail).getByText("Motif : Charnière cassée")).toBeInTheDocument();
  expect(within(detail).getByText("Non")).toBeInTheDocument();
  expect(within(detail).queryByRole("button", { name: /Supprimer|Modifier/ })).not.toBeInTheDocument();
  fireEvent.click(within(detail).getByRole("button", { name: "Imprimer" }));
  expect(imprimer).toHaveBeenCalledWith(expect.stringContaining("Avoir T01-A2026-000003"));
  expect(vi.mocked(imprimer).mock.calls[0][0]).toContain("Facture : T01-F2026-000007");
  expect(appels.filter((a) => a.startsWith("POST"))).toEqual([]);
});

test("sans droit d'émettre, seule la consultation s'affiche", async () => {
  consulter({ emettre: false });
  expect(await screen.findByText("T01-A2026-000003")).toBeInTheDocument();
  expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("N° de ticket ou de commande")).not.toBeInTheDocument();
});

test("sans droit de consulter, pas d'onglet des avoirs émis", () => {
  consulter({ consulter: false });
  expect(screen.getByLabelText("N° de ticket ou de commande")).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "Avoirs émis" })).not.toBeInTheDocument();
});
