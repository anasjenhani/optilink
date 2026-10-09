import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";

import { Statistiques } from "./Statistiques";

afterEach(() => vi.unstubAllGlobals());

test("affiche le bénéfice par jour avec ses totaux", async () => {
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      urls.push(url);
      if (url.startsWith("/api/v1/magasins/")) return Promise.resolve(new Response(JSON.stringify({ results: [] })));
      return Promise.resolve(
        new Response(
          JSON.stringify({
            titre: "Bénéfice journalier",
            devise: "TND",
            decimales: 3,
            devises: ["TND"],
            du: "2026-10-01",
            au: "2026-10-09",
            colonnes: [
              { cle: "jour", libelle: "Jour", type: "date" },
              { cle: "ca_ht", libelle: "CA HT", type: "montant" },
              { cle: "marge", libelle: "Taux de marge", type: "pourcent" },
            ],
            lignes: [{ jour: "2026-10-02", ca_ht: "218.950", marge: "8.65" }],
            totaux: { ca_ht: "218.950", marge: "8.65" },
          }),
        ),
      );
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Statistiques rapport="benefice" />
    </QueryClientProvider>,
  );
  const tableau = await screen.findByRole("table", { name: "Bénéfice journalier" });
  const lignes = within(tableau).getAllByRole("row");
  expect(lignes[1]).toHaveTextContent("02/10/2026");
  expect(lignes[1]).toHaveTextContent("218,950");
  expect(lignes[2]).toHaveTextContent("Total");
  expect(lignes[2]).toHaveTextContent("8,65 %");
  expect(urls.some((u) => u.startsWith("/api/v1/statistiques/benefice/?du="))).toBe(true);
});
