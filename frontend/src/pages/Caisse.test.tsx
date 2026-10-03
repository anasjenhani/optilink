import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";

import { Caisse } from "./Caisse";

const TUNISIE = {
  code: "TN",
  nom: "Tunisie",
  devise: "TND",
  decimales: 3,
  indicatif_telephonique: "+216",
  timbre_fiscal: "1.000",
  libelle_identifiant_prescripteur: "N° d'inscription à l'Ordre des médecins",
};
const MAGASIN = { id: "m1", code: "T01", nom: "Tunis", societe: "Optique de Tunis", ville: "Tunis", pays: TUNISIE };
const MONTURE = {
  id: "a1",
  reference: "MON-1",
  libelle: "Monture titane",
  famille: "monture",
  prix_vente_ttc: "289.500",
  taux_tva: "19.00",
  devise: "TND",
  stock: 3,
};

const SOCIETE = { id: "c1", nom: "Optique Services", prenom: "SARL", telephone: "71000000" };

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Caisse />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

function simuler(reponseVente: () => Promise<Response>) {
  const ventes: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (url === "/api/v1/magasins/") return json({ results: [MAGASIN] });
      if (url.startsWith("/api/v1/articles/")) return json({ results: [MONTURE] });
      if (url.startsWith("/api/v1/clients/")) return json({ results: [SOCIETE] });
      ventes.push(JSON.parse(init?.body as string));
      return reponseVente();
    }),
  );
  return ventes;
}

async function remplirPanier() {
  afficher();
  fireEvent.change(await screen.findByLabelText(/Rechercher un article/), { target: { value: "mon" } });
  fireEvent.click(await screen.findByRole("button", { name: "Ajouter" }));
  fireEvent.click(screen.getByRole("button", { name: "Ajouter un" }));
}

test("encaisse le panier en dinars et affiche le ticket", async () => {
  const ventes = simuler(() =>
    json({ id: "v1", numero: "T01-T2026-000001", devise: "TND", total_ttc: "579.000", lignes: [] }, 201),
  );
  await remplirPanier();

  // Dinar à 3 décimales ; pas de timbre en caisse (il ne concerne que la facture).
  expect(screen.getByText(/Total : 579,000\sTND/)).toBeInTheDocument();
  expect(screen.queryByText(/timbre/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Encaisser" }));

  expect(await screen.findByText(/Ticket T01-T2026-000001/)).toBeInTheDocument();
  expect(ventes).toEqual([
    { magasin: "m1", lignes: [{ article: "a1", quantite: 2 }], paiements: [{ mode: "carte", montant: "579.000" }] },
  ]);
});

test("rattache un client au ticket", async () => {
  const ventes = simuler(() =>
    json({ id: "v2", numero: "T01-T2026-000002", devise: "TND", total_ttc: "579.000", lignes: [] }, 201),
  );
  await remplirPanier();
  fireEvent.click(screen.getByLabelText(/Rattacher un client/));
  fireEvent.change(screen.getByLabelText(/^Client/), { target: { value: "optique" } });
  fireEvent.click(await screen.findByText("OPTIQUE SERVICES SARL"));
  fireEvent.click(screen.getByRole("button", { name: "Encaisser" }));

  expect(await screen.findByText(/Ticket T01-T2026-000002/)).toBeInTheDocument();
  expect(ventes[0]).toMatchObject({ client: "c1" });
});

test("affiche le refus de l'API", async () => {
  simuler(() => json({ detail: "Stock insuffisant pour MON-1." }, 400));
  await remplirPanier();
  fireEvent.click(screen.getByRole("button", { name: "Encaisser" }));

  expect(await screen.findByText("Stock insuffisant pour MON-1.")).toBeInTheDocument();
});

test("un verre sur commande impose une commande avec acompte", async () => {
  const VERRE = { ...MONTURE, id: "a2", reference: "VER-1", libelle: "Verre progressif", famille: "verre", sur_commande: true, prix_vente_ttc: "180.000", stock: 0 };
  const ventes: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (url === "/api/v1/magasins/") return json({ results: [MAGASIN] });
      if (url.startsWith("/api/v1/articles/")) return json({ results: [VERRE] });
      ventes.push(JSON.parse(init?.body as string));
      return json(
        { id: "v3", numero: "T01-T2026-000003", devise: "TND", total_ttc: "360.000", reste_a_payer: "260.000", statut: "en_commande", peniche: 17, lignes: [] },
        201,
      );
    }),
  );
  afficher();
  fireEvent.change(await screen.findByLabelText(/Rechercher un article/), { target: { value: "ver" } });
  expect(await screen.findByText(/sur commande/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Ajouter" }));
  fireEvent.click(screen.getByRole("button", { name: "Ajouter un" }));

  expect(screen.getByRole("checkbox", { name: /Commande : verres commandés/ })).toBeChecked();
  fireEvent.change(screen.getByLabelText("Acompte"), { target: { value: "100" } });
  expect(screen.getByRole("button", { name: "Enregistrer la commande" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText(/Péniche/), { target: { value: "17" } });
  expect(screen.getByText(/Reste à la livraison : 260,000\sTND/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Enregistrer la commande" }));

  expect(
    await screen.findByText(/Commande T01-T2026-000003.*péniche 17, reste 260,000\sTND à la livraison/),
  ).toBeInTheDocument();
  expect(ventes[0]).toMatchObject({
    lignes: [{ article: "a2", quantite: 2 }],
    paiements: [{ mode: "carte", montant: "100.000" }],
    commande: true,
    peniche: 17,
  });
});

test("la douchette ajoute l'article au panier par son code-barres", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url === "/api/v1/magasins/") return json({ results: [MAGASIN] });
      return json({ results: [{ ...MONTURE, code_barres: "8053672000001" }] });
    }),
  );
  afficher();
  const champ = await screen.findByLabelText(/Rechercher un article/);
  fireEvent.change(champ, { target: { value: "8053672000001" } });
  fireEvent.keyDown(champ, { key: "Enter" });
  expect(await screen.findByText(/Total : 289,500\sTND/)).toBeInTheDocument();
  expect(champ).toHaveValue("");
});
