import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { Catalogue } from "./Catalogue";

const MAGASIN = { id: "m1", code: "T01", nom: "Tunis Centre", societe: "", ville: "Tunis", pays: { devise: "TND", decimales: 3 } };
const MONTURE = {
  id: "a1",
  reference: "MON-RB-001",
  libelle: "Monture Ray-Ban",
  famille: "monture",
  description: "Ray-Ban RB5154 · écaille · 51□21-145",
  caracteristiques: { marque: "Ray-Ban" },
  sur_commande: false,
  prix_vente_ttc: "489.000",
  taux_tva: "19.00",
  devise: "TND",
  stock: 10,
};
const VERRE = { ...MONTURE, id: "a2", reference: "VER-PR-007", libelle: "Verre progressif", famille: "verre", description: "Essilor Varilux Comfort · Progressif", sur_commande: true, stock: 0 };

afterEach(() => vi.unstubAllGlobals());

test("affiche le catalogue par famille avec les caractéristiques", async () => {
  const appels: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      appels.push(url);
      const donnees = url.startsWith("/api/v1/magasins/")
        ? { results: [MAGASIN] }
        : { results: url.includes("famille=verre") ? [VERRE] : [MONTURE] };
      return Promise.resolve(new Response(JSON.stringify(donnees), { status: 200 }));
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Catalogue />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Ray-Ban RB5154 · écaille · 51□21-145")).toBeInTheDocument();
  expect(appels).toContain("/api/v1/articles/?magasin=m1&recherche=&famille=monture");

  fireEvent.mouseDown(screen.getByRole("combobox", { name: "Famille" }));
  fireEvent.click(within(await screen.findByRole("listbox")).getByText("Verres"));
  expect(await screen.findByText("Essilor Varilux Comfort · Progressif")).toBeInTheDocument();
  expect(screen.getByText("sur commande")).toBeInTheDocument();
});
