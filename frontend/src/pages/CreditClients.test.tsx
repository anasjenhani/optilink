import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";

import { CreditClients } from "./CreditClients";

const CHEQUE = {
  id: 7,
  mode: "cheque",
  mode_libelle: "Chèque",
  montant: "289.500",
  recu_le: "2026-10-01T10:00:00+01:00",
  reference: "0042",
  banque: "BIAT",
  echeance: "2026-11-15",
  statut: "encaisse",
  statut_libelle: "Encaissé",
  impaye_le: null,
  motif_impaye: "",
  vente: "v1",
  vente_numero: "T01-T2026-000001",
  vente_reste: "0.000",
  devise: "TND",
  magasin: "Tunis Centre",
  client: "BEN SALAH Amel",
  client_id: "c1",
  client_telephone: "98 123 456",
};

afterEach(() => vi.unstubAllGlobals());

const afficher = (onglet: "portefeuille" | "ventes") =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <CreditClients droits={{ regler: true, gerer: true }} ongletInitial={onglet} />
    </QueryClientProvider>,
  );

test("un chèque de l'échéancier se déclare impayé, avec la liste noire", async () => {
  const envois: { url: string; corps: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        envois.push({ url, corps: JSON.parse(init.body as string) });
        return Promise.resolve(new Response(JSON.stringify({ ...CHEQUE, statut: "impaye" })));
      }
      return Promise.resolve(new Response(JSON.stringify([CHEQUE])));
    }),
  );
  afficher("portefeuille");
  expect(await screen.findByText("Chèque n° 0042")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Impayé" }));
  fireEvent.change(screen.getByLabelText("Motif du rejet"), { target: { value: "Sans provision" } });
  fireEvent.click(screen.getByRole("button", { name: "Déclarer impayé" }));
  await vi.waitFor(() =>
    expect(envois).toEqual([
      {
        url: "/api/v1/credit-clients/paiements/7/impaye/",
        corps: { le: expect.any(String), motif: "Sans provision", liste_noire: true },
      },
    ]),
  );
});

test("les ventes à crédit montrent le reste dû et se règlent", async () => {
  const envois: { url: string; corps: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        envois.push({ url, corps: JSON.parse(init.body as string) });
        return Promise.resolve(new Response(JSON.stringify({})));
      }
      return Promise.resolve(
        new Response(
          JSON.stringify([
            {
              id: "v1",
              numero: "T01-T2026-000009",
              cree_le: "2026-10-01T10:00:00+01:00",
              livree_le: "2026-10-01T10:00:00+01:00",
              magasin: "Tunis Centre",
              devise: "TND",
              total_ttc: "289.500",
              reste_a_payer: "189.500",
              a_credit: true,
              credit_echeance: "2026-09-30",
              impayes: 0,
              client: "BEN SALAH Amel",
              client_id: "c1",
              client_telephone: "",
              en_retard: true,
            },
          ]),
        ),
      );
    }),
  );
  afficher("ventes");
  expect(await screen.findByText("T01-T2026-000009")).toBeInTheDocument();
  expect(screen.getAllByText(/189,500/).length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole("button", { name: "Régler" }));
  fireEvent.click(screen.getByRole("button", { name: "Encaisser" }));
  await vi.waitFor(() =>
    expect(envois).toEqual([
      {
        url: "/api/v1/ventes/v1/reglement/",
        corps: { paiements: [{ mode: "especes", montant: "189.500" }] },
      },
    ]),
  );
});
