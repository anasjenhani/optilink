import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";

import { BordereauxPec } from "./BordereauxPec";

const PEC = (id: string, numero: string) => ({
  id,
  vente_numero: numero,
  vente_date: "2026-10-01T10:00:00+01:00",
  vente_total_ttc: "649.500",
  client: "BEN SALAH Amel",
  numero_affilie: "12345678",
  numero_dossier: "",
  montant: "150.000",
  montant_regle: null,
  motif_rejet: "",
  statut: "demandee",
  statut_libelle: "Demandée",
  lignes: [],
});

const BORDEREAU = {
  id: "b1",
  numero: "T01-BP2026-000001",
  magasin: "m1",
  magasin_nom: "Tunis Centre",
  devise: "TND",
  decimales: 3,
  organisme: "o1",
  organisme_nom: "CNAM",
  organisme_type: "Caisse",
  statut: "envoye",
  statut_libelle: "Envoyé",
  envoye_le: "2026-10-05",
  regle_le: null,
  mode_reglement: "",
  mode_reglement_libelle: "",
  reference_reglement: "",
  observation: "",
  total: "300.000",
  total_regle: null,
  cree_le: "2026-10-05T10:00:00+01:00",
  cree_par: "Sami",
  prises_en_charge: [PEC("p1", "T01-T2026-000001"), PEC("p2", "T01-T2026-000002")],
};

afterEach(() => vi.unstubAllGlobals());

test("saisit le règlement d'un bordereau envoyé, avec le motif d'une réduction", async () => {
  const envois: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        envois.push({ url, corps: JSON.parse(init.body as string) });
        return Promise.resolve(new Response(JSON.stringify({ ...BORDEREAU, statut: "regle" })));
      }
      return Promise.resolve(new Response(JSON.stringify({ results: [BORDEREAU] })));
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <BordereauxPec preparer regler />
    </QueryClientProvider>,
  );
  fireEvent.click(await screen.findByText("T01-BP2026-000001"));
  fireEvent.change(screen.getByLabelText("Réglé T01-T2026-000002"), { target: { value: "100" } });
  fireEvent.change(screen.getByLabelText("Motif T01-T2026-000002"), { target: { value: "Plafond" } });
  fireEvent.change(screen.getByLabelText("Référence (n° virement ou chèque)"), { target: { value: "VIR-1" } });
  expect(screen.getByText(/Total : 250,000/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Enregistrer le règlement" }));
  await vi.waitFor(() =>
    expect(envois).toEqual([
      {
        url: "/api/v1/bordereaux-pec/b1/regler/",
        corps: {
          le: expect.any(String),
          mode: "virement",
          reference: "VIR-1",
          lignes: [
            { prise_en_charge: "p1", montant_regle: "150.000", motif_rejet: "" },
            { prise_en_charge: "p2", montant_regle: "100", motif_rejet: "Plafond" },
          ],
        },
      },
    ]),
  );
});
