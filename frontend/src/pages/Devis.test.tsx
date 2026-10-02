import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { Devis, type DroitsDevis } from "./Devis";

const TUNIS = {
  id: "m1",
  code: "T01",
  nom: "Tunis",
  region: "Grand Tunis",
  ville: "Tunis",
  pays: {
    code: "TN",
    nom: "Tunisie",
    devise: "TND",
    decimales: 3,
    indicatif_telephonique: "+216",
    timbre_fiscal: "1.000",
    libelle_identifiant_prescripteur: "N° d'inscription à l'Ordre des médecins",
  },
};
const CLIENT = { id: "c1", nom: "Ben Salah", prenom: "Leila", telephone: "98000000" };
const ARTICLES = [
  { id: "a1", reference: "MON-1", libelle: "Monture titane", famille: "monture", prix_vente_ttc: "289.500", taux_tva: "19.00", devise: "TND", stock: 3 },
  { id: "a2", reference: "VER-1", libelle: "Verre progressif", famille: "verre", prix_vente_ttc: "180.000", taux_tva: "7.00", devise: "TND", stock: 0 },
];
const ORDONNANCE = { id: "p1", type: "lunettes", date_prescription: "2026-09-01", prescripteur: "Dr Trabelsi", mesures: {}, saisie_par: "x" };

function devis(statut: string, valable = "2099-12-31") {
  return {
    id: "d1",
    numero: "T01-D2026-000001",
    client: { id: "c1", nom: "BEN SALAH Leila", matricule_fiscal: "" },
    prescription: null,
    valable_jusqu_au: valable,
    statut,
    devise: "TND",
    total_ttc: "649.500",
    vente: null,
    lignes: [],
  };
}

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

afterEach(() => vi.unstubAllGlobals());

const TOUS: DroitsDevis = { remise: true, voirOrdonnances: true, changerStatut: true, encaisser: true };

function afficher(droits: DroitsDevis, existants: unknown[] = []) {
  const envois: { url: string; corps: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        envois.push({ url, corps: init.body ? JSON.parse(init.body as string) : null });
        if (url.endsWith("/encaisser/")) return json({ id: "v1", numero: "T01-T2026-000007" }, 201);
        return json(devis("en_cours"), 201);
      }
      if (url === "/api/v1/magasins/") return json({ results: [TUNIS] });
      if (url.startsWith("/api/v1/clients/")) return json({ results: [CLIENT] });
      if (url.startsWith("/api/v1/prescriptions/")) return json({ results: [ORDONNANCE] });
      if (url.startsWith("/api/v1/articles/")) return json({ results: ARTICLES });
      return json({ results: existants });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Devis droits={droits} />
    </QueryClientProvider>,
  );
  return envois;
}

async function choisirClient() {
  fireEvent.change(screen.getByLabelText(/Client du devis/), { target: { value: "ben" } });
  fireEvent.click(await screen.findByText("BEN SALAH Leila"));
}

test("établit un devis avec ordonnance, monture et verres œil par œil", async () => {
  const envois = afficher(TOUS);
  await choisirClient();
  fireEvent.mouseDown(await screen.findByLabelText("Ordonnance"));
  fireEvent.click(await screen.findByText(/Lunettes du 01\/09\/2026/));

  fireEvent.change(screen.getByLabelText(/Ajouter un article/), { target: { value: "mon" } });
  const boutons = await screen.findAllByRole("button", { name: "Ajouter" });
  fireEvent.click(boutons[0]);
  fireEvent.click(boutons[1]);
  fireEvent.click(boutons[1]);
  // Second verre : œil gauche.
  const oeils = screen.getAllByLabelText("Œil");
  fireEvent.mouseDown(oeils[1]);
  fireEvent.click(await screen.findByRole("option", { name: "Gauche" }));

  expect(screen.getByText(/Total du devis : 649,500\sTND/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Établir le devis" }));

  expect(await screen.findByText(/Devis T01-D2026-000001 établi/)).toBeInTheDocument();
  expect(envois[0].corps).toEqual({
    magasin: "m1",
    client: "c1",
    prescription: "p1",
    lignes: [
      { article: "a1", quantite: 1 },
      { article: "a2", quantite: 1, oeil: "od" },
      { article: "a2", quantite: 1, oeil: "og" },
    ],
  });
});

test("sans droit aux ordonnances ni aux remises, ces champs n'apparaissent pas", async () => {
  afficher({ remise: false, voirOrdonnances: false, changerStatut: true, encaisser: true });
  await choisirClient();
  fireEvent.change(screen.getByLabelText(/Ajouter un article/), { target: { value: "mon" } });
  fireEvent.click((await screen.findAllByRole("button", { name: "Ajouter" }))[0]);
  expect(screen.queryByLabelText("Ordonnance")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Remise %")).not.toBeInTheDocument();
});

test("encaisse un devis au prix du devis", async () => {
  const envois = afficher(TOUS, [devis("accepte")]);
  await choisirClient();
  const liste = await screen.findByRole("list", { name: "Devis du client" });
  fireEvent.click(within(liste).getByRole("button", { name: "Encaisser" }));

  expect(await screen.findByText(/encaissé : ticket T01-T2026-000007/)).toBeInTheDocument();
  expect(envois[0]).toEqual({
    url: "/api/v1/devis/d1/encaisser/",
    corps: { paiements: [{ mode: "carte", montant: "649.500" }], commande: false },
  });
});

test("passe un devis en commande avec acompte", async () => {
  const envois = afficher(TOUS, [devis("accepte")]);
  await choisirClient();
  const liste = await screen.findByRole("list", { name: "Devis du client" });
  fireEvent.click(screen.getByRole("checkbox", { name: /En commande/ }));
  fireEvent.change(screen.getByLabelText("Acompte"), { target: { value: "300" } });
  expect(within(liste).getByRole("button", { name: "Commander" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText(/Péniche/), { target: { value: "12" } });
  fireEvent.click(within(liste).getByRole("button", { name: "Commander" }));

  expect(await screen.findByText(/encaissé|passé en commande/)).toBeInTheDocument();
  expect(envois[0]).toEqual({
    url: "/api/v1/devis/d1/encaisser/",
    corps: { paiements: [{ mode: "carte", montant: "300" }], commande: true, peniche: 12 },
  });
});

test("un devis expiré ne propose plus d'action", async () => {
  afficher(TOUS, [devis("en_cours", "2020-01-31")]);
  await choisirClient();
  const liste = await screen.findByRole("list", { name: "Devis du client" });
  expect(within(liste).getByText("Expiré")).toBeInTheDocument();
  expect(within(liste).queryByRole("button")).not.toBeInTheDocument();
});
