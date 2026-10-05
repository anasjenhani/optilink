import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import type { FactureAchat as Facture } from "../api/facturesAchat";
import { formaterTexte } from "../api/monnaie";
import { FactureAchat, pageFacture } from "./FactureAchat";

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

afterEach(() => vi.unstubAllGlobals());

const BL = {
  id: "b1",
  numero: "T01-R2026-000041",
  numero_bl: "26/00426",
  date_bl: "2026-04-11",
  remise_ex: "0.000",
  total_fodec: "0.000",
  total_net_ht: "4815.802",
  total_tva: "915.001",
  total_ttc: "5730.803",
};
const TOTAUX = {
  total_ht: "6019.753",
  total_remise: "1203.951",
  remise_ex: "0.000",
  total_net_ht: "4815.802",
  total_fodec: "0.000",
  total_tva: "915.001",
  total_ttc: "5731.803",
};

test("importe les BL du fournisseur et enregistre la facture", async () => {
  const appels: { url: string; methode?: string; corps?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      appels.push({ url, methode: init?.method, corps: init?.body ? JSON.parse(init.body as string) : undefined });
      if (url.startsWith("/api/v1/magasins/"))
        return json({ results: [{ id: "m1", nom: "Tunis", pays: { devise: "TND", decimales: 3 } }] });
      if (url.startsWith("/api/v1/fournisseurs/"))
        return json({ count: 1, results: [{ id: "f1", code: 25, nom: "Optical Line Trading" }] });
      if (url.includes("a-facturer")) return json({ timbre_fiscal: "1.000", bons: [BL], retours: [] });
      if (url.includes("apercu"))
        return json({
          ...TOTAUX,
          detail_tva: [{ taux: "19.00", base_ht: "4815.802", montant_tva: "915.001" }],
          lignes_retour: [],
          lignes: [
            {
              bon: BL.numero,
              article: "a1",
              famille: "monture",
              code: "0000004596",
              designation: "JC083 700",
              etui: false,
              quantite: 1,
              prix_achat_ht: "411.497",
              montant_ht: "411.497",
              taux_remise: "20.00",
              montant_remise: "82.299",
              net_ht: "329.198",
              taux_tva: "19.00",
              montant_ttc: "391.746",
              numero_serie: "",
            },
          ],
        });
      return json(
        { ...TOTAUX, numero: "T01-FA2026-000043", reference_fournisseur: "26/00487", bons: [BL], retours: [] },
        201,
      );
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <FactureAchat />
    </QueryClientProvider>,
  );
  fireEvent.change(screen.getByLabelText("Code Fournisseur / Raison sociale"), { target: { value: "25" } });
  fireEvent.click(await screen.findByText("25 · Optical Line Trading"));
  fireEvent.change(screen.getByLabelText("Référence Fournisseur"), { target: { value: "26/00487" } });
  fireEvent.change(screen.getByLabelText("Date Référence"), { target: { value: "2026-08-10" } });
  fireEvent.click(screen.getByRole("button", { name: "Importer BL" }));
  const dialogue = await screen.findByRole("dialog");
  fireEvent.click(await within(dialogue).findByRole("checkbox", { name: "Tout choisir" }));
  fireEvent.click(within(dialogue).getByRole("button", { name: "Importer" }));

  expect(await screen.findByText("JC083 700")).toBeInTheDocument();
  expect(screen.getByLabelText("Total TTC")).toHaveValue(formaterTexte("5731.803", { devise: "TND", decimales: 3 }));
  expect(screen.getByLabelText("Timbre Fiscal")).toHaveValue("1.000");
  fireEvent.click(screen.getByRole("button", { name: "Valider" }));
  expect(await screen.findByText(/Facture achat T01-FA2026-000043 enregistrée/)).toBeInTheDocument();
  expect(appels.find((a) => a.url === "/api/v1/factures-achat/" && a.methode === "POST")?.corps).toMatchObject({
    magasin: "m1",
    fournisseur: "f1",
    reference_fournisseur: "26/00487",
    date_reference: "2026-08-10",
    bons: ["b1"],
    timbre_fiscal: "1.000",
  });
});

test("la page imprimable reprend les lignes et les totaux", () => {
  const page = pageFacture(
    {
      ...TOTAUX,
      numero: "T01-FA2026-000043",
      fournisseur: "Optical <Line>",
      fournisseur_code: 25,
      reference_fournisseur: "26/00487",
      date_reference: "2026-08-10",
      date_entree: "2026-09-23",
      magasin: "Tunis",
      bons: [BL],
      retours: [],
      lignes: [],
      lignes_retour: [],
      detail_tva: [{ taux: "19.00", base_ht: "4815.802", montant_tva: "915.001" }],
      timbre_fiscal: "1.000",
      frais_supplementaires: "0.000",
      ajustement: "0.000",
      cree_par: "Fatma",
      cree_le: "2026-09-23T13:43:00Z",
      paiement_libelle: "Non payé",
    } as unknown as Facture,
    { devise: "TND", decimales: 3 },
  );
  expect(page).toContain("Facture Achat T01-FA2026-000043");
  expect(page).toContain("Optical &lt;Line&gt;");
  expect(page).toContain(formaterTexte("5731.803", { devise: "TND", decimales: 3 }));
});
