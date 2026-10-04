import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import type { EtatSession } from "../api/auth";
import { Espace } from "./Espace";

function session(permissions: string[]): EtatSession {
  return {
    authentifie: true,
    mfa: "verifiee",
    utilisateur: { identifiant: "claire", nom_complet: "Claire Martin", permissions },
  };
}

function afficher(permissions: string[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve(new Response(JSON.stringify(url.includes("/suivi/") ? [] : { results: [] }), { status: 200 })),
    ),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Espace session={session(permissions)} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.location.hash = "";
});

test("les modules sont des onglets horizontaux, Vente d'abord", () => {
  afficher([]);
  const onglets = within(screen.getByRole("tablist", { name: "Modules" })).getAllByRole("tab");
  expect(onglets.map((o) => o.textContent)).toEqual([
    "Vente",
    "Stock",
    "Règlement",
    "Caisse",
    "SAV",
    "Facture",
    "Administration",
  ]);
  expect(screen.getByRole("heading", { name: "Vente" })).toBeInTheDocument();
});

test("un bouton ouvre son écran, et le retour ramène à la grille", async () => {
  afficher(["ventes.add_vente"]);
  fireEvent.click(screen.getByRole("button", { name: "Vente au Comptoir" }));

  expect(await screen.findByRole("heading", { name: "Caisse" })).toBeInTheDocument();
  expect(window.location.hash).toBe("#/vente/comptoir");
  fireEvent.click(screen.getByRole("button", { name: "Vente" }));
  expect(await screen.findByRole("heading", { name: "Vente" })).toBeInTheDocument();
});

test("sans le droit, le bouton disparaît ; une fonction pas encore faite est grisée", () => {
  afficher([]);
  expect(screen.queryByRole("button", { name: "Vente au Comptoir" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Nouvelle Visite/ })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Lunettes Vendues/ })).toBeDisabled();
  expect(screen.queryByRole("navigation", { name: "Raccourcis" })).not.toBeInTheDocument();
});

test("les boutons fixes sous le menu ouvrent les écrans du quotidien depuis tout onglet", async () => {
  afficher(["ventes.add_vente", "ventes.view_vente", "stock.view_article"]);
  const raccourcis = within(screen.getByRole("navigation", { name: "Raccourcis" }));
  expect(raccourcis.getAllByRole("button").map((b) => b.textContent)).toEqual([
    "Journée",
    "Nouvelle visite",
    "Suivi",
    "Recherche verre",
    "Recherche monture",
    "Recherche lentille",
  ]);
  fireEvent.click(screen.getByRole("tab", { name: "Caisse" }));
  fireEvent.click(raccourcis.getByRole("button", { name: "Suivi" }));
  expect(await screen.findByRole("heading", { name: "Suivi des visites" })).toBeInTheDocument();
  expect(window.location.hash).toBe("#/vente/suivi-visite");
  expect(raccourcis.getByRole("button", { name: "Suivi" })).toHaveAttribute("aria-current", "page");
});

test("la recherche filtre les boutons du module", () => {
  afficher(["ventes.add_vente"]);
  fireEvent.change(screen.getByLabelText("Rechercher"), { target: { value: "visite" } });

  expect(screen.getByRole("button", { name: /Nouvelle Visite/ })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Vente au Comptoir" })).not.toBeInTheDocument();
});

test("changer d'onglet affiche les boutons du module", async () => {
  afficher(["tresorerie.add_cloturecaisse"]);
  fireEvent.click(screen.getByRole("tab", { name: "Caisse" }));

  expect(await screen.findByRole("button", { name: "Session en Cours" })).toBeInTheDocument();
});
