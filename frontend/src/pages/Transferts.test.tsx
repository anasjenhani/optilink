import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { ListeTransferts, TransfertStock } from "./Transferts";

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

afterEach(() => vi.unstubAllGlobals());

const PAYS = { devise: "TND", decimales: 3 };
const MAGASINS = [
  {
    id: "m1",
    nom: "Tunis Centre",
    societe_id: "s1",
    type: "magasin",
    depot_central: true,
    pays: PAYS,
    depots: [
      { id: "v1", code: "T01", nom: "Dépôt Tunis Centre", type: "vente" },
      { id: "c1", code: "DEPCEN", nom: "Dépôt central", type: "central" },
    ],
  },
  {
    id: "m2",
    nom: "Lac",
    societe_id: "s1",
    type: "magasin",
    pays: PAYS,
    depots: [{ id: "v2", code: "T02", nom: "Dépôt Lac", type: "vente" }],
  },
];
const MONTURE = {
  id: "a1",
  reference: "MON-1",
  code_barres: "2000000000017",
  libelle: "Ray-Ban RB5154",
  famille: "monture",
  description: "",
  sur_commande: false,
  stock: 4,
  taux_tva: "19.00",
};
const TRANSFERT = {
  id: "t1",
  numero: "DEP-TR2026-000001",
  magasin: "Tunis Centre",
  magasin_id: "m1",
  depot_origine: "Dépôt central",
  destination: "Lac",
  destination_id: "m2",
  depot_destination: "Dépôt Lac",
  statut: "envoye",
  statut_libelle: "Envoyé (en route)",
  total_articles: 2,
  observation: "",
  envoye_par: "achats",
  cree_le: "2026-10-05T10:00:00Z",
  recu_par: "",
  recu_le: null,
  annule_par: "",
  annule_le: null,
  lignes: [
    { article: "a1", reference: "MON-1", code_barres: "", libelle: "Ray-Ban RB5154", famille: "monture", quantite: 2 },
  ],
};

function afficher(ecran: React.ReactNode) {
  let detail: unknown = TRANSFERT;
  const appels: { url: string; methode?: string; corps?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      appels.push({ url, methode: init?.method, corps: init?.body ? JSON.parse(init.body as string) : undefined });
      if (url.startsWith("/api/v1/magasins/")) return json({ results: MAGASINS });
      if (url.startsWith("/api/v1/articles/")) return json({ results: [MONTURE] });
      if (url.endsWith("/annuler/")) {
        detail = { ...TRANSFERT, statut: "annule", annule_par: "achats", annule_le: "2026-10-05T11:00:00Z" };
        return json(detail);
      }
      if (url.endsWith("/recevoir/")) return json({ ...TRANSFERT, statut: "recu", recu_le: "2026-10-05T12:00:00Z" });
      if (url === "/api/v1/transferts/t1/") return json(detail);
      if (url.startsWith("/api/v1/transferts/?")) return json({ count: 1, results: [TRANSFERT] });
      if (url === "/api/v1/transferts/") return json(TRANSFERT, 201);
      return json({ results: [] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      {ecran}
    </QueryClientProvider>,
  );
  return appels;
}

test("le dépôt central envoie des articles de son stock au dépôt d'un magasin", async () => {
  const appels = afficher(<TransfertStock />);
  // Le dépôt central est proposé d'abord comme départ.
  expect(await screen.findByText("Dépôt central (Tunis Centre)")).toBeInTheDocument();
  fireEvent.mouseDown(screen.getByLabelText("Vers le dépôt"));
  // Le dépôt de vente du même magasin est aussi proposé.
  expect(await screen.findByRole("option", { name: "Dépôt Tunis Centre (Tunis Centre)" })).toBeInTheDocument();
  fireEvent.click(await screen.findByRole("option", { name: "Dépôt Lac (Lac)" }));

  fireEvent.change(screen.getByLabelText(/Ajouter un article/), { target: { value: "RB" } });
  fireEvent.click(await screen.findByText("Ray-Ban RB5154"));
  const lignes = screen.getByRole("table", { name: "Articles à transférer" });
  fireEvent.change(within(lignes).getByLabelText("Quantité Ray-Ban RB5154"), { target: { value: "5" } });
  expect(screen.getByText("Quantité supérieure au stock du dépôt de départ.")).toBeInTheDocument();
  fireEvent.change(within(lignes).getByLabelText("Quantité Ray-Ban RB5154"), { target: { value: "2" } });
  fireEvent.click(screen.getByRole("button", { name: "Envoyer" }));

  expect(await screen.findByText(/Transfert DEP-TR2026-000001 envoyé à Lac · Dépôt Lac/)).toBeInTheDocument();
  expect(appels.find((a) => a.url === "/api/v1/transferts/" && a.methode === "POST")?.corps).toEqual({
    magasin: "m1",
    destination: "m2",
    depot_origine: "c1",
    depot_destination: "v2",
    observation: "",
    lignes: [{ article: "a1", quantite: 2 }],
  });
});

test("le magasin destinataire réceptionne le transfert", async () => {
  const appels = afficher(<ListeTransferts recevoir />);
  fireEvent.click(await screen.findByText("DEP-TR2026-000001"));
  fireEvent.click(await screen.findByRole("button", { name: "Réceptionner" }));
  expect(await screen.findByText(/Reçu le/)).toBeInTheDocument();
  expect(appels.some((a) => a.url === "/api/v1/transferts/t1/recevoir/" && a.methode === "POST")).toBe(true);
});

test("le dépôt annule un transfert pas encore reçu", async () => {
  const appels = afficher(<ListeTransferts recevoir={false} annuler />);
  fireEvent.click(await screen.findByText("DEP-TR2026-000001"));
  fireEvent.click(await screen.findByRole("button", { name: "Annuler le transfert" }));
  expect(screen.getByText(/Les articles reviennent au dépôt Tunis Centre · Dépôt central/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Oui, annuler" }));
  expect(await screen.findByText(/Annulé le .* par achats/)).toBeInTheDocument();
  expect(appels.some((a) => a.url === "/api/v1/transferts/t1/annuler/" && a.methode === "POST")).toBe(true);
  expect(screen.queryByRole("button", { name: "Annuler le transfert" })).not.toBeInTheDocument();
});

test("sans le droit d'envoyer, pas de bouton Annuler", async () => {
  afficher(<ListeTransferts recevoir />);
  fireEvent.click(await screen.findByText("DEP-TR2026-000001"));
  await screen.findByRole("button", { name: "Réceptionner" });
  expect(screen.queryByRole("button", { name: "Annuler le transfert" })).not.toBeInTheDocument();
});
