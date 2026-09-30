import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";

import { Accueil } from "./Accueil";

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Accueil />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("affiche l'état renvoyé par l'API", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ statut: "ok", base_de_donnees: "ok", cache: "indisponible" })),
    ),
  );
  afficher();
  expect(await screen.findByText("Base de données")).toBeInTheDocument();
  expect(screen.getByText("indisponible")).toBeInTheDocument();
});

test("affiche une erreur si l'API ne répond pas", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 502 })));
  afficher();
  expect(await screen.findByText("API injoignable (502)")).toBeInTheDocument();
});
