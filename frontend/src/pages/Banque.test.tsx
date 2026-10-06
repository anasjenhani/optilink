import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { Banque, Versements } from "./Banque";

const A_REMETTRE = [
  {
    id: "c1",
    numero: "T01-CL2026-000001",
    magasin: "Tunis",
    societe: "s1",
    fin: "2026-10-03T18:00:00Z",
    devise: "TND",
    especes: "200.000",
    cheques: "180.000",
    nombre_cheques: 1,
    cartes: "320.500",
  },
];
const COMPTE = {
  id: "b1",
  societe: "s1",
  societe_nom: "Optique de Tunis",
  type: "banque",
  nom: "BIAT Aouina",
  banque: "BIAT",
  rib: "",
  magasin: null,
  magasin_nom: null,
  devise: "TND",
  solde_initial: "0.000",
  est_actif: true,
  solde_comptable: "695.000",
  solde_banque: "0.000",
};
const OPERATION = {
  id: "o1",
  numero: "SCTE001-OP2026-000003",
  societe: "Optique de Tunis",
  type: "encaissement_cartes",
  type_libelle: "Encaissement des cartes bancaires",
  statut: "effectuee",
  source: null,
  destination: "BIAT Aouina",
  magasin: null,
  montant: "320.500",
  montant_credite: null,
  commission: null,
  date_prevue: null,
  date_operation: "2026-10-04",
  date_valeur: null,
  reference: "TPE-4",
  libelle: "T01-CL2026-000001",
  cree_par: "Sami",
  rapprochee_par: null,
};

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

afterEach(() => vi.unstubAllGlobals());

function afficher(ecran: React.ReactNode, compte: typeof COMPTE = COMPTE) {
  const envois: { url: string; corps: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        const corps = JSON.parse(init.body as string);
        envois.push({ url, corps });
        return json({ ...compte, ...corps });
      }
      if (init?.method === "POST") {
        envois.push({ url, corps: JSON.parse(init.body as string) });
        return json({ ...OPERATION, numero: "SCTE001-OP2026-000001" }, 201);
      }
      if (url.includes("a-remettre")) return json(A_REMETTRE);
      if (url.includes("/comptes/")) return json([compte]);
      if (url.includes("/operations/")) return json({ results: url.includes("prevue") ? [] : [OPERATION] });
      return json({ results: [] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      {ecran}
    </QueryClientProvider>,
  );
  return envois;
}

test("le responsable verse les espèces d'une clôture validée à la banque", async () => {
  const envois = afficher(<Versements />);
  fireEvent.click(await screen.findByLabelText("T01-CL2026-000001"));
  expect(screen.getByText(/1 clôture\(s\) · total/).textContent?.replace(/\s/g, "")).toContain("200,000TND");
  fireEvent.mouseDown(screen.getByLabelText("Déposer sur"));
  fireEvent.click(await screen.findByRole("option", { name: "BIAT Aouina" }));
  const bouton = screen.getByRole("button", { name: "Enregistrer le dépôt" });
  expect(bouton).toBeDisabled();
  fireEvent.change(screen.getByLabelText("N° de bordereau"), { target: { value: "B-77" } });
  fireEvent.click(bouton);
  expect(await screen.findByText("Dépôt SCTE001-OP2026-000001 enregistré.")).toBeInTheDocument();
  expect(envois[0]).toEqual({
    url: "/api/v1/tresorerie/operations/deposer/",
    corps: {
      type: "depot_especes",
      clotures: ["c1"],
      destination: "b1",
      reference: "B-77",
      prevue: false,
      date: null,
    },
  });
});

test("la finance rapproche les cartes avec le montant crédité", async () => {
  const envois = afficher(<Banque droits={{ gererComptes: true, rapprocher: true, operations: true }} />);
  const comptes = await screen.findByRole("table", { name: "Comptes de trésorerie" });
  expect(within(comptes).getByText("BIAT Aouina")).toBeInTheDocument();
  const credite = await screen.findByLabelText("Montant crédité SCTE001-OP2026-000003");
  fireEvent.change(screen.getByLabelText("Date de valeur SCTE001-OP2026-000003"), { target: { value: "2026-10-05" } });
  fireEvent.change(credite, { target: { value: "315" } });
  fireEvent.click(screen.getByRole("button", { name: "Rapprocher" }));
  await vi.waitFor(() => expect(envois).toHaveLength(1));
  expect(envois[0]).toEqual({
    url: "/api/v1/tresorerie/operations/o1/rapprocher/",
    corps: { date_valeur: "2026-10-05", montant_credite: "315" },
  });
});

test("la finance corrige le RIB d'un compte puis le désactive après confirmation", async () => {
  const envois = afficher(
    <Banque droits={{ gererComptes: true, rapprocher: false, operations: false, modifierComptes: true }} />,
  );
  fireEvent.click(await screen.findByRole("button", { name: "Modifier BIAT Aouina" }));
  expect(screen.queryByLabelText("Solde de départ")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Nom du compte"), { target: { value: "BIAT Aouina principal" } });
  fireEvent.change(screen.getByLabelText("RIB"), { target: { value: "08006012345678901234" } });
  fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  await vi.waitFor(() => expect(envois).toHaveLength(1));
  expect(envois[0]).toEqual({
    url: "/api/v1/tresorerie/comptes/b1/",
    corps: { nom: "BIAT Aouina principal", banque: "BIAT", rib: "08006012345678901234" },
  });

  fireEvent.click(await screen.findByRole("button", { name: "Désactiver BIAT Aouina" }));
  expect(await screen.findByText(/ne sera plus proposé pour les dépôts/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retour" }));
  expect(envois).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "Désactiver BIAT Aouina" }));
  fireEvent.click(await screen.findByRole("button", { name: "Désactiver le compte" }));
  await vi.waitFor(() => expect(envois).toHaveLength(2));
  expect(envois[1]).toEqual({ url: "/api/v1/tresorerie/comptes/b1/", corps: { est_actif: false } });
});

test("un compte inactif est signalé et se réactive", async () => {
  const envois = afficher(
    <Banque droits={{ gererComptes: true, rapprocher: false, operations: false, modifierComptes: true }} />,
    { ...COMPTE, est_actif: false },
  );
  const comptes = await screen.findByRole("table", { name: "Comptes de trésorerie" });
  expect(within(comptes).getByText("Inactif")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Réactiver BIAT Aouina" }));
  await vi.waitFor(() => expect(envois).toHaveLength(1));
  expect(envois[0].corps).toEqual({ est_actif: true });
});

test("sans le droit de modifier, les comptes restent en lecture seule", async () => {
  afficher(<Banque droits={{ gererComptes: true, rapprocher: false, operations: false }} />);
  expect(await screen.findByRole("table", { name: "Comptes de trésorerie" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Modifier BIAT Aouina" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Désactiver BIAT Aouina" })).not.toBeInTheDocument();
});
