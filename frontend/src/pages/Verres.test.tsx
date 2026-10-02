import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";

import { Verres } from "./Verres";

const TUNIS = {
  id: "m1",
  code: "T01",
  nom: "Tunis",
  region: "Grand Tunis",
  ville: "Tunis",
  pays: { code: "TN", nom: "Tunisie", devise: "TND", decimales: 3, indicatif_telephonique: "+216", timbre_fiscal: "1.000", libelle_identifiant_prescripteur: "" },
};
const A_COMMANDER = [
  { ligne: 11, commande_client: "T01-T2026-000003", client: { id: "c1", nom: "BEN SALAH Leila" }, livraison_prevue_le: "2026-10-15", peniche: 5, article: "VER-1", libelle: "Verre progressif", quantite: 2, fournisseur: "f2", reference_fournisseur: "VX-16" },
];
const ENVOYEE = {
  id: "cf1",
  numero: "T01-C2026-000001",
  fournisseur: "Essilor Tunisie",
  reference_fournisseur: "ESS-1",
  statut: "envoyee",
  cree_le: "2026-10-02T09:00:00Z",
  lignes: [{ commande_client: "T01-T2026-000002", libelle: "Verre progressif", quantite: 2, details: "" }],
};

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

afterEach(() => vi.unstubAllGlobals());

function afficher() {
  const envois: { url: string; corps: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        envois.push({ url, corps: init.body ? JSON.parse(init.body as string) : null });
        if (url.endsWith("/receptionner/")) return json({ ...ENVOYEE, statut: "recue" });
        return json({ ...ENVOYEE, numero: "T01-C2026-000002" }, 201);
      }
      if (url === "/api/v1/magasins/") return json({ results: [TUNIS] });
      if (url === "/api/v1/fournisseurs/") return json({
          results: [
            { id: "f1", nom: "Essilor Tunisie", pays: "TN", telephone: "", email: "" },
            { id: "f2", nom: "Zeiss Tunisie", pays: "TN", telephone: "", email: "" },
          ],
        });
      if (url.includes("/a-commander/")) return json(A_COMMANDER);
      return json({ results: [ENVOYEE] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Verres />
    </QueryClientProvider>,
  );
  return envois;
}

test("commande au fournisseur les verres d'une commande client avec leurs détails", async () => {
  const envois = afficher();
  fireEvent.click(await screen.findByRole("checkbox", { name: "Commander T01-T2026-000003 Verre progressif" }));
  expect(screen.getByText(/péniche 5/)).toBeInTheDocument();
  expect(screen.getByText("Réf. fournisseur VX-16")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Détails T01-T2026-000003"), { target: { value: "OD -2.25 / OG -1.75" } });
  fireEvent.change(screen.getByLabelText("Réf. fournisseur"), { target: { value: "ESS-2" } });
  fireEvent.click(screen.getByRole("button", { name: "Commander au fournisseur" }));

  expect(await screen.findByText(/Commande T01-C2026-000002 envoyée à Essilor Tunisie/)).toBeInTheDocument();
  expect(envois[0]).toEqual({
    url: "/api/v1/commandes-fournisseurs/",
    corps: { magasin: "m1", fournisseur: "f2", reference_fournisseur: "ESS-2", lignes: [{ ligne: 11, details: "OD -2.25 / OG -1.75" }] },
  });
});

test("réceptionne une commande fournisseur", async () => {
  const envois = afficher();
  fireEvent.click(await screen.findByRole("button", { name: "Réceptionner" }));
  expect(await screen.findByText(/reçue : les commandes clients peuvent être livrées/)).toBeInTheDocument();
  expect(envois[0].url).toBe("/api/v1/commandes-fournisseurs/cf1/receptionner/");
});
