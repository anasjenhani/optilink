import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { Inventaire } from "./Inventaire";

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

afterEach(() => vi.unstubAllGlobals());

const PAYS = { devise: "TND", decimales: 3 };
const MAGASINS = [
  { id: "m1", nom: "Tunis Centre", societe_id: "s1", type: "magasin", pays: PAYS },
  { id: "d1", nom: "Dépôt central", societe_id: "s1", type: "depot", pays: PAYS },
];
const ETUI = {
  article: "a2",
  reference: "ETUI",
  code_barres: "6190000000017",
  libelle: "Étui",
  famille: "divers",
  stock_theorique: 5,
  quantite_comptee: 0,
  comptee: false,
  ecart: -5,
  observation: "",
};
const INVENTAIRE = {
  id: "i1",
  numero: "DEP-IN2026-000001",
  magasin: "Dépôt central",
  magasin_id: "d1",
  famille: "",
  famille_libelle: "Tout le stock",
  marque: "",
  nature: "",
  fournisseur: "",
  perimetre: "Tout le stock",
  statut: "en_cours",
  statut_libelle: "En cours de comptage",
  articles_comptes: 0,
  observation: "",
  cree_par: "achats",
  cree_le: "2026-10-05T10:00:00Z",
  valide_par: "",
  valide_le: null,
  lignes: [ETUI],
};
const COMPTE = {
  ...INVENTAIRE,
  articles_comptes: 1,
  lignes: [{ ...ETUI, quantite_comptee: 4, comptee: true, ecart: -1 }],
};

function afficher(droits = { ouvrir: true, compter: true, valider: true }) {
  const appels: { url: string; methode?: string; corps?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      appels.push({ url, methode: init?.method, corps: init?.body ? JSON.parse(init.body as string) : undefined });
      if (url.startsWith("/api/v1/magasins/")) return json({ results: MAGASINS });
      if (url.startsWith("/api/v1/articles/")) return json({ results: [] });
      if (url === "/api/v1/inventaires/choix/")
        return json({ marques: ["Ray-Ban"], fournisseurs: [{ id: "f1", nom: "Luxottica" }] });
      if (url.endsWith("/compter/")) return json(COMPTE);
      if (url.endsWith("/valider/"))
        return json({
          ...COMPTE,
          statut: "valide",
          statut_libelle: "Validé",
          valide_par: "resp",
          valide_le: "2026-10-05T12:00:00Z",
        });
      if (url === "/api/v1/inventaires/i1/") return json(INVENTAIRE);
      if (url.startsWith("/api/v1/inventaires/?")) return json({ count: 1, results: [INVENTAIRE] });
      if (url === "/api/v1/inventaires/") return json(INVENTAIRE, 201);
      return json({ results: [] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Inventaire droits={droits} />
    </QueryClientProvider>,
  );
  return appels;
}

test("ouvrir un inventaire au dépôt, scanner, voir l'écart puis valider", async () => {
  const appels = afficher();
  expect(await screen.findByText("Dépôt central (dépôt central)")).toBeInTheDocument();
  fireEvent.mouseDown(screen.getByLabelText("Nature"));
  fireEvent.click(await screen.findByRole("option", { name: "Lunette Solaire" }));
  fireEvent.click(screen.getByRole("button", { name: "Créer un inventaire" }));
  expect(await screen.findByText("Inventaire DEP-IN2026-000001")).toBeInTheDocument();
  expect(appels.find((a) => a.url === "/api/v1/inventaires/" && a.methode === "POST")?.corps).toEqual({
    magasin: "d1",
    famille: "monture",
    marque: "",
    nature: "solaire",
    fournisseur: null,
    observation: "",
  });
  const table = screen.getByRole("table", { name: "Articles de l'inventaire" });
  expect(within(table).getByText("(non compté)")).toBeInTheDocument();
  expect(within(table).getAllByText("-5")).toHaveLength(2); // ligne et total

  fireEvent.change(screen.getByLabelText("Quantité"), { target: { value: "4" } });
  const scan = screen.getByLabelText("Code barre ou référence");
  fireEvent.change(scan, { target: { value: "6190000000017" } });
  fireEvent.keyDown(scan, { key: "Enter" });
  expect(await within(table).findAllByText("-1")).toHaveLength(2);
  expect(appels.find((a) => a.url.endsWith("/compter/"))?.corps).toEqual({ code: "6190000000017", quantite: 4 });
  expect(screen.getByText("Étui : 4 compté(s)")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Valider" }));
  expect(screen.getByText(/corrigé pour 1 article\(s\) avec écart/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Valider et corriger le stock" }));
  expect(await screen.findByText(/le stock a été corrigé/)).toBeInTheDocument();
  expect(screen.queryByLabelText("Code barre ou référence")).not.toBeInTheDocument();
});

test("un vendeur compte mais ne peut ni ouvrir ni valider", async () => {
  afficher({ ouvrir: false, compter: true, valider: false });
  fireEvent.click(await screen.findByText("DEP-IN2026-000001"));
  expect(await screen.findByLabelText("Code barre ou référence")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Valider" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Créer un inventaire" })).not.toBeInTheDocument();
});
