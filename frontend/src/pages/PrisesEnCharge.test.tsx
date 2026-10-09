import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { PrisesEnCharge } from "./PrisesEnCharge";

const PEC = {
  id: "p1",
  vente: "v1",
  vente_numero: "T01-T2026-000003",
  magasin: "T01",
  devise: "TND",
  client: "BEN SALAH Leila",
  organisme: "o1",
  organisme_nom: "CNAM",
  montant: "150.000",
  numero_dossier: "BS-118",
  statut: "demandee",
  statut_libelle: "Demandée",
  bordereau: null,
  montant_regle: null,
  motif_rejet: "",
  cree_le: "2026-10-04T10:00:00+01:00",
};

afterEach(() => vi.unstubAllGlobals());

test("liste les dossiers et fait avancer leur statut", async () => {
  const envois: { url: string; corps: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        envois.push({ url, corps: JSON.parse(init.body as string) });
        return Promise.resolve(new Response(JSON.stringify({ ...PEC, statut: "accordee" })));
      }
      if (url === "/api/v1/magasins/") return Promise.resolve(new Response(JSON.stringify({ results: [] })));
      return Promise.resolve(new Response(JSON.stringify({ results: [PEC] })));
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <PrisesEnCharge modifier />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("BEN SALAH Leila")).toBeInTheDocument();
  expect(screen.getByText("150,000 TND", { exact: false })).toBeInTheDocument();

  fireEvent.mouseDown(screen.getByRole("combobox", { name: /Statut T01-T2026-000003/ }));
  fireEvent.click(within(screen.getByRole("listbox")).getByRole("option", { name: "Accordée" }));
  await vi.waitFor(() =>
    expect(envois).toEqual([{ url: "/api/v1/prises-en-charge/p1/", corps: { statut: "accordee" } }]),
  );
});
