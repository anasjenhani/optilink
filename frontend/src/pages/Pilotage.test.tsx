import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";

import { Alertes } from "./Alertes";
import { Reporting } from "./Reporting";

const TUNISIE = { code: "TN", nom: "Tunisie", devise: "TND", decimales: 3 };
const MAGASIN = { id: "m1", code: "T01", nom: "L'Aouina", societe: "Optique de Tunis", ville: "Tunis", pays: TUNISIE };

function json(donnees: unknown) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status: 200 }));
}

function simuler(routes: Record<string, unknown>) {
  const appels: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      appels.push(url);
      const cle = Object.keys(routes).find((r) => url.startsWith(r));
      return json(cle ? routes[cle] : { results: [MAGASIN] });
    }),
  );
  return appels;
}

function afficher(page: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}>{page}</QueryClientProvider>);
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.location.hash = "";
});

test("chaque alerte mène à l'écran où la traiter", async () => {
  simuler({
    "/api/v1/pilotage/alertes/": [
      {
        code: "commandes_en_retard",
        gravite: "haute",
        titre: "Commandes en retard",
        detail: "2 commandes dont la date de livraison prévue est dépassée.",
        magasin: "L'Aouina",
        nombre: 2,
        module: "vente",
        ecran: "commandes",
      },
    ],
  });
  afficher(<Alertes />);

  expect(await screen.findByText("Commandes en retard · L'Aouina")).toBeInTheDocument();
  expect(screen.getByText("Urgent")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Traiter" }));
  expect(window.location.hash).toBe("#/vente/commandes");
});

test("sans alerte, tout est à jour", async () => {
  simuler({ "/api/v1/pilotage/alertes/": [] });
  afficher(<Alertes />);
  expect(await screen.findByText(/tout est à jour/)).toBeInTheDocument();
});

test("le reporting affiche les chiffres de la période en dinars", async () => {
  const appels = simuler({
    "/api/v1/pilotage/reporting/": [
      {
        devise: "TND",
        ca_ttc: "1250.500",
        ca_ht: "1050.840",
        avoirs_ttc: "50.000",
        ca_net_ttc: "1200.500",
        nombre_ventes: 4,
        panier_moyen: "312.625",
        par_magasin: [{ magasin: "L'Aouina", ca_ttc: "1250.500", nombre: 4 }],
        par_jour: [{ jour: "2026-10-03", ca_ttc: "1250.500", nombre: 4 }],
        par_vendeur: [{ vendeur: "Salma Ben Ali", ca_ttc: "1250.500", nombre: 4 }],
        par_famille: [{ famille: "Monture", ca_ttc: "900.000", quantite: 2 }],
        encaissements: [{ mode: "Espèces", montant: "1250.500" }],
      },
    ],
  });
  afficher(<Reporting />);

  const vendeurs = await screen.findByRole("table", { name: "Par vendeur" });
  expect(within(vendeurs).getByText("Salma Ben Ali")).toBeInTheDocument();
  expect(screen.getByText("Panier moyen").nextSibling?.textContent).toMatch(/312,625/);
  expect(appels.some((u) => u.startsWith("/api/v1/pilotage/reporting/?du="))).toBe(true);
});
