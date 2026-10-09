import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

import { ClotureMois, FacturationGroupee } from "./FacturationGroupee";

const MAGASIN = {
  id: "m1",
  code: "T01",
  nom: "Tunis Centre",
  societe: "Optique",
  societe_id: "s1",
  ville: "Tunis",
  nombre_peniches: 0,
  pays: { code: "TN", devise: "TND", decimales: 3, timbre_fiscal: "1.000" },
};

const VENTE = (id: string, numero: string) => ({
  id,
  numero,
  livree_le: "2026-09-15T10:00:00+01:00",
  client: null,
  client_id: null,
  total_ht: "243.277",
  total_tva: "46.223",
  total_ttc: "289.500",
  reste_a_payer: "0.000",
});

const ecran = (contenu: ReactNode) =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      {contenu}
    </QueryClientProvider>,
  );

afterEach(() => vi.unstubAllGlobals());

function simuler(reponses: (url: string) => unknown, envois: unknown[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        envois.push({ url, corps: JSON.parse(init.body as string) });
      }
      return Promise.resolve(new Response(JSON.stringify(reponses(url))));
    }),
  );
}

test("facture ensemble des ventes comptoir au nom d'une société", async () => {
  const envois: unknown[] = [];
  simuler((url) => {
    if (url.startsWith("/api/v1/magasins/")) return { results: [MAGASIN] };
    if (url.includes("a-facturer")) return [VENTE("v1", "T01-T2026-000001"), VENTE("v2", "T01-T2026-000002")];
    return {
      numero: "T01-F2026-000009",
      client_nom: "Lumière",
      nombre_ventes: 2,
      net_a_payer: "580.000",
    };
  }, envois);
  ecran(<FacturationGroupee comptoir />);

  fireEvent.click(await screen.findByLabelText("Tout cocher"));
  expect(screen.getByText(/2 ventes · 579,000/)).toBeInTheDocument();
  const generer = screen.getByRole("button", { name: "Générer la facture" });
  expect(generer).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Facturer au nom de"), {
    target: { value: "Lumière" },
  });
  fireEvent.change(screen.getByLabelText("Matricule fiscal"), {
    target: { value: "1234567A" },
  });
  fireEvent.click(generer);

  expect(await screen.findByText(/Facture T01-F2026-000009 au nom de Lumière/)).toBeInTheDocument();
  expect(envois).toEqual([
    {
      url: "/api/v1/factures-groupees/",
      corps: {
        magasin: "m1",
        ventes: ["v1", "v2"],
        client: null,
        client_nom: "Lumière",
        client_adresse: "",
        client_matricule_fiscal: "1234567A",
        mode_paiement_timbre: "especes",
      },
    },
  ]);
});

test("clôture le mois après confirmation", async () => {
  const envois: unknown[] = [];
  simuler((url) => {
    if (url.startsWith("/api/v1/magasins/")) return { results: [MAGASIN] };
    if (url.includes("preparation")) {
      return {
        annee: 2026,
        mois: 9,
        cloture: null,
        ventes: [VENTE("v1", "T01-T2026-000001")],
        detail_tva: [
          {
            taux: "19.00",
            total_ht: "243.277",
            total_tva: "46.223",
            total_ttc: "289.500",
          },
        ],
        total_ht: "243.277",
        total_tva: "46.223",
        total_ttc: "289.500",
      };
    }
    if (url === "/api/v1/clotures-mois/") return [];
    return {};
  }, envois);
  ecran(<ClotureMois cloturer />);

  expect(await screen.findByText(/1 ventes livrées en septembre 2026 sont encore sans facture/)).toBeInTheDocument();
  expect(screen.getByRole("table", { name: "TVA par taux" })).toHaveTextContent("19 %");
  fireEvent.click(screen.getByRole("button", { name: "Clôturer septembre 2026" }));
  fireEvent.click(await screen.findByRole("button", { name: "Clôturer" }));
  await vi.waitFor(() =>
    expect(envois).toEqual([
      {
        url: "/api/v1/clotures-mois/",
        corps: { magasin: "m1", annee: 2026, mois: 9 },
      },
    ]),
  );
});
