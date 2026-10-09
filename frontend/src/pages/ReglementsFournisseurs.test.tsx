import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";

import { pageCertificatRetenue, ReglementsFournisseurs } from "./ReglementsFournisseurs";

const REGLEMENT = {
  id: "r1",
  numero: "T01-RF2026-000001",
  magasin: "m1",
  magasin_nom: "Tunis Centre",
  societe: "Optique de Tunis",
  societe_matricule: "1234567A",
  societe_adresse: "Tunis",
  devise: "TND",
  decimales: 3,
  fournisseur: "f1",
  fournisseur_nom: "Optical Line",
  fournisseur_matricule: "7654321B",
  fournisseur_adresse: "Sfax",
  date_reglement: "2026-10-01",
  mode: "traite",
  mode_libelle: "Traite",
  reference: "TR-42",
  banque: "BIAT",
  echeance: "2026-12-31",
  statut: "a_echoir",
  statut_libelle: "À échoir",
  debite_le: null,
  montant: "1178.100",
  taux_retenue: "1.00",
  retenue: "11.900",
  total_regle: "1190.000",
  disponible: "0.000",
  observation: "",
  imputations: [
    {
      facture: "fa1",
      facture_numero: "T01-FA2026-000001",
      reference_fournisseur: "26/487",
      date_reference: "2026-09-10",
      facture_total_ttc: "1190.000",
      montant: "1190.000",
      le: "2026-10-01",
    },
  ],
  cree_par: "Sami",
  cree_le: "2026-10-01T10:00:00+01:00",
};

afterEach(() => vi.unstubAllGlobals());

test("l'échéancier liste les traites à échoir et les marque débitées", async () => {
  const envois: { url: string; corps: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        envois.push({ url, corps: JSON.parse(init.body as string) });
        return Promise.resolve(new Response(JSON.stringify({ ...REGLEMENT, statut: "debite" })));
      }
      return Promise.resolve(new Response(JSON.stringify({ results: [REGLEMENT] })));
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ReglementsFournisseurs droits={{ regler: true, debiter: true, annuler: true }} ongletInitial="echeancier" />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Optical Line")).toBeInTheDocument();
  expect(screen.getByText(/Traite TR-42/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Débité" }));
  await vi.waitFor(() => expect(envois[0].url).toBe("/api/v1/reglements-fournisseurs/r1/debiter/"));
});

test("le certificat de retenue reprend payeur, bénéficiaire et montants", () => {
  const page = pageCertificatRetenue(REGLEMENT as never);
  expect(page).toContain("Certificat de retenue à la source");
  expect(page).toContain("7654321B");
  expect(page).toContain("26/487");
  expect(page).toMatch(/11,900/);
});
