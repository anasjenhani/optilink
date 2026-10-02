import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";

import { Imports } from "./Imports";

const MAGASIN = { id: "m1", code: "T01", nom: "Tunis Centre", region: "", ville: "Tunis", pays: { devise: "TND", decimales: 3 } };

afterEach(() => vi.unstubAllGlobals());

function afficher(reponse: (url: string, corps: FormData) => { status: number; donnees: unknown }) {
  const envois: { url: string; corps: Record<string, string> }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (url === "/api/v1/magasins/") return Promise.resolve(new Response(JSON.stringify({ results: [MAGASIN] })));
      const corps = init?.body as FormData;
      envois.push({
        url,
        corps: Object.fromEntries([...corps.entries()].map(([k, v]) => [k, v instanceof File ? v.name : v])),
      });
      const { status, donnees } = reponse(url, corps);
      return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Imports droits={{ catalogue: true, stock: true }} />
    </QueryClientProvider>,
  );
  return envois;
}

const choisir = (titre: string, nom: string) =>
  fireEvent.change(screen.getByLabelText(`Fichier ${titre}`), {
    target: { files: [new File(["x"], nom, { type: "text/csv" })] },
  });

test("vérifie, alerte sur les articles existants, puis importe avec le jeton", async () => {
  const envois = afficher((_, corps) => {
    const apercu = corps.get("apercu") === "true";
    return {
      status: 200,
      donnees: {
        apercu,
        lignes: 3,
        crees: 2,
        modifies: 1,
        erreurs: [],
        alertes: [{ ligne: 2, message: "MON-1 existe déjà au catalogue : il sera mis à jour (en stock : Tunis Centre 4)." }],
        jeton: apercu ? "j-123" : "",
      },
    };
  });
  choisir("Catalogue", "catalogue.xlsx");
  const importer = () => screen.getAllByRole("button", { name: "2. Importer" })[0];
  expect(importer()).toBeDisabled();
  fireEvent.click(screen.getAllByRole("button", { name: "1. Vérifier" })[0]);
  expect(await screen.findByText("Fichier vérifié : 3 ligne(s), 2 créé(s), 1 mis à jour à l'import.")).toBeInTheDocument();
  expect(
    screen.getByText("Ligne 2 : MON-1 existe déjà au catalogue : il sera mis à jour (en stock : Tunis Centre 4)."),
  ).toBeInTheDocument();
  fireEvent.click(importer());
  expect(await screen.findByText("Import terminé : 2 créé(s), 1 mis à jour.")).toBeInTheDocument();
  expect(envois.map((e) => [e.url, e.corps.apercu, e.corps.jeton, e.corps.fichier])).toEqual([
    ["/api/v1/imports/catalogue/", "true", undefined, "catalogue.xlsx"],
    ["/api/v1/imports/catalogue/", "false", "j-123", "catalogue.xlsx"],
  ]);
});

test("une entrée de stock en erreur ne peut pas être importée", async () => {
  const envois = afficher(() => ({
    status: 400,
    donnees: {
      apercu: true,
      lignes: 2,
      crees: 1,
      modifies: 0,
      erreurs: [{ ligne: 3, message: "Article inconnu : 999." }],
      alertes: [],
      jeton: "",
    },
  }));
  await screen.findByText("Tunis Centre");
  fireEvent.change(screen.getByLabelText("N° du bon de livraison"), { target: { value: "BL-778" } });
  choisir("Entrées de stock", "bl.csv");
  fireEvent.click(screen.getAllByRole("button", { name: "1. Vérifier" })[1]);
  expect(await screen.findByText("Ligne 3 : Article inconnu : 999.")).toBeInTheDocument();
  expect(screen.getByText(/Rien n'a été enregistré/)).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "2. Importer" })[1]).toBeDisabled();
  expect(envois[0]).toEqual({
    url: "/api/v1/imports/stock/",
    corps: { fichier: "bl.csv", magasin: "m1", piece: "BL-778", apercu: "true" },
  });
});
