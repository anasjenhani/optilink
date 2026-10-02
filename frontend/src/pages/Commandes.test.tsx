import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";

import { Commandes } from "./Commandes";

const TUNIS = {
  id: "m1",
  code: "T01",
  nom: "Tunis",
  region: "Grand Tunis",
  ville: "Tunis",
  pays: { code: "TN", nom: "Tunisie", devise: "TND", decimales: 3, indicatif_telephonique: "+216", timbre_fiscal: "1.000", libelle_identifiant_prescripteur: "" },
};

function commande(reste: string) {
  return {
    id: "v1",
    numero: "T01-T2026-000003",
    devise: "TND",
    total_ttc: "649.500",
    reste_a_payer: reste,
    statut: reste === "0.000" ? "livree" : "en_commande",
    livraison_prevue_le: "2026-10-15",
    facture: null,
    client: { id: "c1", nom: "BEN SALAH Leila", matricule_fiscal: "" },
    lignes: [],
  };
}

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

afterEach(() => vi.unstubAllGlobals());

function afficher() {
  const envois: { url: string; corps: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (url === "/api/v1/magasins/") return json({ results: [TUNIS] });
      if (init?.method === "POST") {
        const corps = JSON.parse(init.body as string);
        envois.push({ url, corps });
        return json(commande(url.endsWith("/livrer/") ? "0.000" : "349.500"));
      }
      return json({ results: [commande("449.500")] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Commandes />
    </QueryClientProvider>,
  );
  return envois;
}

test("liste les commandes en cours avec leur reste et leur date prévue", async () => {
  afficher();
  expect(await screen.findByText("T01-T2026-000003")).toBeInTheDocument();
  expect(screen.getByText(/449,500\sTND/)).toBeInTheDocument();
  expect(screen.getByText("Prévue le 15/10/2026")).toBeInTheDocument();
});

test("encaisse un règlement puis livre contre le solde", async () => {
  const envois = afficher();
  fireEvent.change(await screen.findByLabelText("Montant T01-T2026-000003"), { target: { value: "100" } });
  fireEvent.click(screen.getByRole("button", { name: "Encaisser" }));
  expect(await screen.findByText(/reste 349,500\sTND/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Encaisser le solde et livrer" }));
  expect(await screen.findByText(/livrée, solde de 449,500\sTND encaissé/)).toBeInTheDocument();
  expect(envois).toEqual([
    { url: "/api/v1/ventes/v1/reglement/", corps: { paiements: [{ mode: "especes", montant: "100" }] } },
    { url: "/api/v1/ventes/v1/livrer/", corps: { paiements: [{ mode: "especes", montant: "449.500" }] } },
  ]);
});

test("une commande dont les verres ne sont pas reçus ne se livre pas", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url === "/api/v1/magasins/") return json({ results: [TUNIS] });
      return json({ results: [{ ...commande("449.500"), verres: "commandes" }] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Commandes />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Verres en attente du fournisseur")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Encaisser le solde et livrer" })).toBeDisabled();
});
