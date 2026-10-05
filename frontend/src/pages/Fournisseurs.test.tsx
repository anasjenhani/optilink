import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";

import { Fournisseurs } from "./Fournisseurs";

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

afterEach(() => vi.unstubAllGlobals());

test("cherche par colonne et crée un fournisseur avec sa fiche fiscale", async () => {
  const appels: { url: string; methode?: string; corps?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      appels.push({ url, methode: init?.method, corps: init?.body ? JSON.parse(init.body as string) : undefined });
      if (init?.method === "POST") return json({ id: "f9", code: 9, nom: "Hoya Tunisie" }, 201);
      return json({
        count: 1,
        results: [
          { id: "f1", code: 3, nom: "Essilor Tunisie", adresse: "Rue du Lac", ville: "Tunis", telephone: "71000000" },
        ],
      });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Fournisseurs droits={{ creer: true, modifier: true }} />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Essilor Tunisie")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Filtrer Ville"), { target: { value: "Tunis" } });
  await vi.waitFor(() => expect(appels.some((a) => a.url.includes("ville=Tunis"))).toBe(true));

  fireEvent.click(screen.getByRole("button", { name: "Ajouter" }));
  fireEvent.change(screen.getByLabelText("Raison sociale"), { target: { value: "Hoya Tunisie" } });
  fireEvent.change(screen.getByLabelText("Matricule fiscal"), { target: { value: "1234567/A/M/000" } });
  fireEvent.click(screen.getByRole("checkbox", { name: "FODEC (1 %)" }));
  fireEvent.click(screen.getByRole("tab", { name: "Adresse" }));
  fireEvent.change(screen.getByLabelText("Ville"), { target: { value: "Sfax" } });
  fireEvent.click(screen.getByRole("button", { name: "Valider" }));

  await vi.waitFor(() => expect(appels.some((a) => a.methode === "POST")).toBe(true));
  expect(appels.find((a) => a.methode === "POST")).toMatchObject({
    url: "/api/v1/fournisseurs/",
    corps: {
      nom: "Hoya Tunisie",
      matricule_fiscal: "1234567/A/M/000",
      fodec: true,
      ville: "Sfax",
      timbre_fiscal: true,
    },
  });
});
