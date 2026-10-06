import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { CassesVerres } from "./CassesVerres";

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

afterEach(() => vi.unstubAllGlobals());

const CASSE = {
  id: "c1",
  vente: "v1",
  vente_numero: "T01-T2026-000012",
  magasin: "T01",
  client: "Ben Salah Amel",
  verre: "Verre progressif",
  commande_fournisseur: "T01-CF2026-000003",
  fournisseur: "Essilor",
  cause: "atelier",
  cause_libelle: "Casse à l'atelier (montage)",
  observation: "",
  declaree_par: "opticien",
  cree_le: "2026-10-05T10:00:00Z",
};

function afficher(declarer: boolean, reponseAnnulation = () => Promise.resolve(new Response(null, { status: 204 }))) {
  const appels: { url: string; methode?: string; corps?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      appels.push({ url, methode: init?.method, corps: init?.body ? JSON.parse(init.body as string) : undefined });
      if (init?.method === "PATCH") return json({ ...CASSE, cause: "fournisseur" });
      if (init?.method === "DELETE") return reponseAnnulation();
      if (url.startsWith("/api/v1/casses-verres/")) return json({ results: [CASSE] });
      return json({ results: [] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <CassesVerres declarer={declarer} />
    </QueryClientProvider>,
  );
  return appels;
}

test("corriger la cause et l'observation d'une casse", async () => {
  const appels = afficher(true);
  fireEvent.click(await screen.findByRole("button", { name: "Modifier" }));
  fireEvent.mouseDown(within(screen.getByRole("dialog")).getByLabelText("Cause"));
  fireEvent.click(await screen.findByRole("option", { name: "Défaut du fournisseur" }));
  fireEvent.change(screen.getByLabelText("Observation"), { target: { value: "Traitement défectueux" } });
  fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  await waitFor(() =>
    expect(appels.find((a) => a.methode === "PATCH")).toEqual({
      url: "/api/v1/casses-verres/c1/",
      methode: "PATCH",
      corps: { cause: "fournisseur", observation: "Traitement défectueux" },
    }),
  );
});

test("annuler une casse déclarée par erreur, avec le refus du serveur", async () => {
  const appels = afficher(true, () =>
    json({ detail: "Le verre a déjà été recommandé au fournisseur : annulez d'abord cette commande." }, 400),
  );
  fireEvent.click(await screen.findByRole("button", { name: "Modifier" }));
  fireEvent.click(screen.getByRole("button", { name: "Annuler la casse" }));
  fireEvent.click(screen.getByRole("button", { name: "Oui, annuler la casse" }));
  expect(await screen.findByText(/déjà été recommandé/)).toBeInTheDocument();
  expect(appels.some((a) => a.url === "/api/v1/casses-verres/c1/" && a.methode === "DELETE")).toBe(true);
});

test("sans le droit de déclarer, pas de correction", async () => {
  afficher(false);
  expect(await screen.findByText("Verre progressif")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Modifier" })).not.toBeInTheDocument();
});
