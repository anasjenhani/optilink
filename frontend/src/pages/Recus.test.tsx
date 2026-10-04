import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";

import { Recus } from "./Recus";

const MAGASIN = { id: "m1", code: "T01", nom: "Tunis Centre", pays: { devise: "TND", decimales: 3 } };
const RECU = {
  id: 9,
  recu_le: "2026-10-04T10:15:00+01:00",
  mode: "carte",
  mode_libelle: "Carte bancaire",
  montant: "100.000",
  recu_par: "Claire Martin",
  vente: "v1",
  vente_numero: "T01-T2026-000001",
  devise: "TND",
  total_ttc: "649.500",
  deja_regle: "200.000",
  reste_apres: "349.500",
  client: { numero: 7, nom: "BEN SALAH Amel", telephone: "98 123 456" },
  magasin: { nom: "Tunis Centre", adresse: "Tunis", telephone: "71 000 000", societe: "Optique de Tunis", matricule_fiscal: "1234567/A" },
};

afterEach(() => vi.unstubAllGlobals());

test("liste les reçus du jour et réimprime un reçu", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve(new Response(JSON.stringify(url === "/api/v1/magasins/" ? { results: [MAGASIN] } : [RECU]))),
    ),
  );
  const imprimer = vi.spyOn(window, "print").mockImplementation(() => {});
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Recus />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("BEN SALAH Amel")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Réimprimer" }));
  expect(await screen.findByText("REÇU DE RÈGLEMENT")).toBeInTheDocument();
  expect(screen.getByText(/349,500/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Imprimer" }));
  expect(imprimer).toHaveBeenCalled();
});
