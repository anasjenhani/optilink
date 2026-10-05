import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { BonRetour } from "./BonRetour";

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

afterEach(() => vi.unstubAllGlobals());

const NON_CONFORME = {
  id: 7,
  bon: "DEP-R2026-000003",
  numero_bl: "BL-88",
  date_bl: "2026-10-01",
  magasin: "Dépôt central",
  code: "2000000000017",
  designation: "Ray-Ban RB5154",
  quantite: 1,
  prix_achat_ht: "100.000",
  taux_remise: "0.00",
  taux_tva: "19.00",
  net_ht: "100.000",
  montant_ttc: "119.000",
  motif: "Branche rayée",
};

test("renvoie au fournisseur un article non conforme reçu au dépôt", async () => {
  const appels: { url: string; methode?: string; corps?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      appels.push({ url, methode: init?.method, corps: init?.body ? JSON.parse(init.body as string) : undefined });
      if (url.startsWith("/api/v1/magasins/"))
        return json({
          results: [{ id: "d1", nom: "Dépôt central", type: "depot", pays: { devise: "TND", decimales: 3 } }],
        });
      if (url.startsWith("/api/v1/fournisseurs/"))
        return json({ count: 1, results: [{ id: "f1", code: 25, nom: "Optical Line Trading", fodec: false }] });
      if (url.includes("a-retourner")) return json([NON_CONFORME]);
      if (url === "/api/v1/bons-retour/")
        return json(
          { id: "r1", numero: "DEP-BR2026-000001", fournisseur: "Optical Line Trading", total_ttc: "119.000" },
          201,
        );
      return json({ results: [] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <BonRetour />
    </QueryClientProvider>,
  );
  fireEvent.change(screen.getByLabelText("Code Fournisseur / Raison sociale"), { target: { value: "25" } });
  fireEvent.click(await screen.findByText("25 · Optical Line Trading"));
  fireEvent.click(screen.getByRole("button", { name: "Importer Non Conformes" }));
  const dialogue = await screen.findByRole("dialog");
  fireEvent.click(await within(dialogue).findByRole("checkbox", { name: "Tout choisir" }));
  fireEvent.click(within(dialogue).getByRole("button", { name: "Importer" }));

  const lignes = await screen.findByRole("table", { name: "Articles renvoyés" });
  expect(within(lignes).getByText("BL BL-88")).toBeInTheDocument();
  const totaux = screen.getByRole("table", { name: "Totaux du retour" });
  expect(within(totaux).getByText(/119,000/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Valider" }));

  expect(await screen.findByText(/Bon retour DEP-BR2026-000001 enregistré/)).toBeInTheDocument();
  expect(appels.find((a) => a.url === "/api/v1/bons-retour/" && a.methode === "POST")?.corps).toMatchObject({
    magasin: "d1",
    fournisseur: "f1",
    lignes: [{ ligne_reception: 7, motif: "Branche rayée" }],
  });
});
