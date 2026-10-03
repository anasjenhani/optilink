import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";

import { Avoirs } from "./Avoirs";

const TUNIS = {
  id: "m1",
  code: "T01",
  nom: "Tunis",
  societe: "Optique de Tunis",
  ville: "Tunis",
  pays: { code: "TN", nom: "Tunisie", devise: "TND", decimales: 3, indicatif_telephonique: "+216", timbre_fiscal: "1.000", libelle_identifiant_prescripteur: "" },
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
          { id: "a1", numero: "T01-A2026-000001", vente: "T01-T2026-000001", facture: null, annulation: false, motif: "", devise: "TND", total_ttc: "289.500", montant_rembourse: "289.500", mode_remboursement: "especes" },
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
