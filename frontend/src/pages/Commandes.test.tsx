import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { Commandes } from "./Commandes";

const TUNIS = {
  id: "m1",
  code: "T01",
  nom: "Tunis",
  societe: "Optique de Tunis",
  ville: "Tunis",
  pays: { code: "TN", nom: "Tunisie", devise: "TND", decimales: 3, indicatif_telephonique: "+216", timbre_fiscal: "1.000", libelle_identifiant_prescripteur: "" },
};

function commande(reste: string) {
  return {
    id: "v1",
    numero: "T01-T2026-000003",
    devise: "TND",
    total_ttc: "649.500",
    pris_en_charge: "0.000",
    reste_a_payer: reste,
    statut: reste === "0.000" ? "livree" : "en_commande",
    livraison_prevue_le: "2026-10-15",
    peniche: 17,
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

test("retrouve une commande par sa péniche", async () => {
  afficher();
  expect(await screen.findByText("T01-T2026-000003")).toBeInTheDocument();
  expect(screen.getByText("17")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Chercher par péniche"), { target: { value: "18" } });
  expect(screen.queryByText("T01-T2026-000003")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Chercher par péniche"), { target: { value: "17" } });
  expect(screen.getByText("T01-T2026-000003")).toBeInTheDocument();
});

test("saisit la part prise en charge par la CNAM sur une commande", async () => {
  const envois: { url: string; corps: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (url === "/api/v1/magasins/") return json({ results: [TUNIS] });
      if (url === "/api/v1/organismes/")
        return json([{ id: "o1", nom: "CNAM", type: "caisse", type_libelle: "Caisse d'assurance maladie", pays: "TN" }]);
      if (init?.method === "POST") {
        envois.push({ url, corps: JSON.parse(init.body as string) });
        return json({ id: "p1", organisme_nom: "CNAM", montant: "150.000" }, 201);
      }
      return json({ results: [commande("449.500")] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Commandes saisirPec />
    </QueryClientProvider>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "Prise en charge" }));
  const dialogue = await screen.findByRole("dialog", { name: /Prise en charge/ });
  await within(dialogue).findByText(/CNAM/);
  fireEvent.change(within(dialogue).getByLabelText("Montant pris en charge"), { target: { value: "150" } });
  fireEvent.change(within(dialogue).getByLabelText(/N° de dossier/), { target: { value: "BS-118" } });
  fireEvent.click(within(dialogue).getByRole("button", { name: "Enregistrer" }));

  expect(await screen.findByText(/Prise en charge CNAM de 150,000/)).toBeInTheDocument();
  expect(envois).toEqual([
    {
      url: "/api/v1/prises-en-charge/",
      corps: { vente: "v1", organisme: "o1", montant: "150", numero_dossier: "BS-118" },
    },
  ]);
});
