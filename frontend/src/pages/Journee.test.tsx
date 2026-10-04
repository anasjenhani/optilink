import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { Journee } from "./Journee";

const MAGASIN = { id: "m1", code: "T01", nom: "Tunis Centre", pays: { devise: "TND", decimales: 3 } };
const vente = (numero: string, nom: string, soldee: boolean, livree: boolean) => ({
  id: numero,
  numero,
  cree_le: "2026-10-03T10:15:00+01:00",
  client: { numero: 12, nom, telephone: "98 123 456" },
  vendeur: "Claire Martin",
  total_ttc: "649.500",
  regle: soldee ? "649.500" : "200.000",
  pec_client: soldee ? null : "CNAM",
  pec_visite: "0.000",
  reste: soldee ? "0.000" : "449.500",
  soldee,
  livree,
  commande: !livree,
  facture: null,
});

afterEach(() => vi.unstubAllGlobals());

test("affiche les totaux de la journée et filtre les visites non soldées", async () => {
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      urls.push(url);
      if (url === "/api/v1/magasins/") return Promise.resolve(new Response(JSON.stringify({ results: [MAGASIN] })));
      return Promise.resolve(
        new Response(
          JSON.stringify({
            date: "2026-10-03",
            magasin: "Tunis Centre",
            devise: "TND",
            nombre_ventes: 2,
            total_ventes: "1299.000",
            regle_sur_ventes: "849.500",
            pris_en_charge: "0.000",
            reste_sur_ventes: "449.500",
            encaisse: "849.500",
            encaisse_par_mode: [{ mode: "Espèces", montant: "849.500" }],
            ventes: [vente("V-1", "BEN SALAH Amira", true, true), vente("V-2", "TRABELSI Karim", false, false)],
          }),
        ),
      );
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Journee />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("BEN SALAH Amira")).toBeInTheDocument();
  expect(screen.getByText(/Reste à régler : 449,500/)).toBeInTheDocument();
  expect(screen.getByRole("columnheader", { name: "PEC client" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "CNAM" })).toBeInTheDocument();
  expect(urls.some((u) => u.startsWith("/api/v1/ventes/journee/?magasin=m1&date="))).toBe(true);

  fireEvent.click(within(screen.getByRole("group", { name: "Soldée" })).getByRole("button", { name: "Non soldé" }));
  expect(screen.queryByText("BEN SALAH Amira")).not.toBeInTheDocument();
  expect(screen.getByText("TRABELSI Karim")).toBeInTheDocument();
});
