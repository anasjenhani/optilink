import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { Corbeille, type DroitsCorbeille } from "./Corbeille";

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

afterEach(() => vi.unstubAllGlobals());

const ELEMENT = {
  id: 7,
  type_libelle: "Dépense de caisse",
  libelle: "Café clients",
  nombre_objets: 1,
  supprime_par: "opticien",
  supprime_le: "2026-10-06T09:00:00Z",
  expire_le: "2026-11-05T09:00:00Z",
  jours_de_grace: 30,
};

function afficher(droits: DroitsCorbeille, restauration = () => Promise.resolve(new Response(null, { status: 204 }))) {
  const appels: { url: string; methode?: string }[] = [];
  let restaure = false;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      appels.push({ url, methode: init?.method });
      if (init?.method === "POST") {
        restaure = true;
        return restauration();
      }
      if (init?.method === "DELETE") {
        restaure = true;
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      return json({ results: restaure ? [] : [ELEMENT] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Corbeille droits={droits} />
    </QueryClientProvider>,
  );
  return appels;
}

test("restaurer un élément supprimé par erreur", async () => {
  const appels = afficher({ restaurer: true, vider: false });
  expect(await screen.findByText("Café clients")).toBeInTheDocument();
  expect(screen.getByText(/pendant 30 jours/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Effacer Café clients" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Restaurer Café clients" }));
  expect(await screen.findByText("« Café clients » est restauré.")).toBeInTheDocument();
  expect(appels).toContainEqual({ url: "/api/v1/corbeille/7/restaurer/", methode: "POST" });
  expect(await screen.findByText("La corbeille est vide.")).toBeInTheDocument();
});

test("une restauration impossible affiche la raison", async () => {
  afficher({ restaurer: true, vider: false }, () =>
    json({ detail: "« Café clients » existe déjà : rien n'a été restauré." }, 400),
  );
  fireEvent.click(await screen.findByRole("button", { name: "Restaurer Café clients" }));
  expect(await screen.findByText(/existe déjà/)).toBeInTheDocument();
});

test("effacer définitivement demande une confirmation", async () => {
  const appels = afficher({ restaurer: false, vider: true });
  fireEvent.click(await screen.findByRole("button", { name: "Effacer Café clients" }));
  fireEvent.click(screen.getByRole("button", { name: "Non" }));
  expect(appels.some((a) => a.methode === "DELETE")).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Effacer Café clients" }));
  fireEvent.click(screen.getByRole("button", { name: "Oui" }));
  await waitFor(() => expect(appels).toContainEqual({ url: "/api/v1/corbeille/7/", methode: "DELETE" }));
  expect(await screen.findByText("Élément supprimé définitivement.")).toBeInTheDocument();
});
