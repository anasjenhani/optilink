import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";

import { ListeReceptions } from "./ListeReceptions";

const TUNIS = {
  id: "m1",
  nom: "Tunis",
  pays: { code: "TN", devise: "TND", decimales: 3 },
};
const BON = {
  id: "b1",
  numero: "T01-R2026-000001",
  magasin: "Tunis",
  date_saisie: "2026-10-05",
  fournisseur: "Essilor Tunisie",
  fournisseur_code: 3,
  numero_bl: "BL-77",
  date_bl: "2026-10-04",
  etat: "non_facture",
  etat_libelle: "Non facturé",
  numero_facture: "",
  observation: "",
  total_ht: "160.000",
  total_net_ht: "160.000",
  total_ttc: "192.304",
  type_bl: "Verre",
  total_articles: 2,
  cree_par: "opticien",
};

function json(donnees: unknown) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status: 200 }));
}

afterEach(() => vi.unstubAllGlobals());

test("liste les bons de réception avec filtres et totaux", async () => {
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      urls.push(url);
      if (url === "/api/v1/magasins/") return json({ results: [TUNIS] });
      if (url.startsWith("/api/v1/bons-reception/b1/"))
        return json({
          ...BON,
          lignes: [],
          detail_tva: [],
          taux_remise_ex: "0",
          total_remise: "0",
          remise_ex: "0",
          total_fodec: "0",
          total_tva: "32.304",
        });
      return json({
        count: 1,
        results: [BON],
        totaux: { total_ht: "160.000", total_net_ht: "160.000", total_ttc: "192.304", total_articles: 2 },
      });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ListeReceptions />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("T01-R2026-000001")).toBeInTheDocument();
  expect(screen.getByText("3 · Essilor Tunisie")).toBeInTheDocument();
  expect(screen.getByText("Non facturé")).toBeInTheDocument();
  expect(screen.getByText("1 bon")).toBeInTheDocument();
  expect(screen.getAllByText(/192,304/)).toHaveLength(2);

  fireEvent.change(screen.getByLabelText("Filtrer Réf. fournisseur"), { target: { value: "BL-77" } });
  await vi.waitFor(() => expect(urls.some((u) => u.includes("numero_bl=BL-77"))).toBe(true));

  fireEvent.click(screen.getByText("T01-R2026-000001"));
  expect(await screen.findByText("Bon de réception T01-R2026-000001")).toBeInTheDocument();
});
