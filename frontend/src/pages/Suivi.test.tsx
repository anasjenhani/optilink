import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { Suivi } from "./Suivi";

const LIGNE = {
  id: "v1",
  numero: "T01-2026-000042",
  magasin: "T01",
  cree_le: "2026-10-03T10:15:00+01:00",
  client: { numero: 226, nom: "RKHAMI Ramzi", telephone: "98 000 000" },
  peniche: 49,
  monture: { reference: "PLQ73 700Y", code_barres: "0000006090" },
  type: "verre",
  stockable: false,
  etat: "montage",
  etat_libelle: "Montage en cours",
  observation: "",
  livraison_prevue_le: null,
  reste_a_payer: "100.000",
};

afterEach(() => vi.unstubAllGlobals());

test("filtre par état et fait passer une visite au contrôle qualité", async () => {
  const appels: { url: string; corps?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      appels.push({ url, corps: init?.body ? JSON.parse(String(init.body)) : undefined });
      if (url === "/api/v1/magasins/") return Promise.resolve(new Response(JSON.stringify({ results: [] })));
      if (url.startsWith("/api/v1/ventes/suivi/")) return Promise.resolve(new Response(JSON.stringify([LIGNE])));
      return Promise.resolve(new Response(JSON.stringify({})));
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Suivi modifier />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("RKHAMI Ramzi")).toBeInTheDocument();
  expect(screen.getByText("PLQ73 700Y")).toBeInTheDocument();
  // Par défaut : les visites à commander du mois en cours.
  const premier = new URL(appels.find((a) => a.url.startsWith("/api/v1/ventes/suivi/"))!.url, "http://x");
  expect(premier.searchParams.get("etat")).toBe("a_commander");
  expect(premier.searchParams.get("annee")).toBe(String(new Date().getFullYear()));

  fireEvent.click(within(screen.getByRole("group", { name: "État" })).getByRole("button", { name: "Montage en cours" }));
  expect(
    within(screen.getByRole("group", { name: "État" })).getByRole("button", { name: "Montage en cours" }),
  ).toHaveAttribute("aria-pressed", "true");

  fireEvent.click(await screen.findByRole("button", { name: "Étape" }));
  fireEvent.mouseDown(screen.getByRole("combobox", { name: "Étape" }));
  fireEvent.click(await screen.findByRole("option", { name: "Contrôle qualité" }));
  fireEvent.change(screen.getByLabelText("Observation"), { target: { value: "Centrage vérifié" } });
  fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  await screen.findAllByText("RKHAMI Ramzi");
  await vi.waitFor(() =>
    expect(appels).toContainEqual({
      url: "/api/v1/ventes/v1/etape/",
      corps: { etape: "controle", observation: "Centrage vérifié" },
    }),
  );
});
