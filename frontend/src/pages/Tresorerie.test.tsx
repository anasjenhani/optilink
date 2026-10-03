import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { Tresorerie, type DroitsTresorerie } from "./Tresorerie";

const TUNIS = {
  id: "m1",
  code: "T01",
  nom: "Tunis",
  societe: "Optique de Tunis",
  ville: "Tunis",
  pays: { code: "TN", nom: "Tunisie", devise: "TND", decimales: 3, indicatif_telephonique: "+216", timbre_fiscal: "1.000", libelle_identifiant_prescripteur: "" },
};
const SITUATION = {
  debut: null,
  fin: "2026-10-03T18:00:00Z",
  devise: "TND",
  fond_initial: "0.000",
  encaisse_especes: "240.000",
  encaisse_cheques: "180.000",
  nombre_cheques: 1,
  encaisse_cartes: "320.500",
  rembourse_especes: "15.000",
  rembourse_cheques: "0.000",
  rembourse_cartes: "0.000",
  depenses: "12.500",
  alimentations: "0.000",
  especes_attendues: "212.500",
  cheques_attendus: "180.000",
  cartes_attendues: "320.500",
  cloture_rejetee: null,
};
const CLOTURE = {
  ...SITUATION,
  id: "c1",
  numero: "T01-CL2026-000001",
  magasin: "Tunis",
  statut: "envoyee",
  especes_comptees: "250.000",
  cheques_comptes: "180.000",
  nombre_cheques_comptes: 1,
  cartes_comptees: "320.500",
  fond_conserve: "50.000",
  especes_a_remettre: "200.000",
  ecart_especes: "37.500",
  ecart_cheques: "0.000",
  ecart_cartes: "0.000",
  commentaire_caissier: "",
  cloturee_par: "Leila",
  verifiee_par: null,
  verifiee_le: null,
  commentaire_finance: "",
};
const TOUT: DroitsTresorerie = { cloturer: true, depenses: true, verifier: true, voirClotures: true };

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

afterEach(() => vi.unstubAllGlobals());

function afficher(droits = TOUT) {
  const envois: { url: string; corps: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        envois.push({ url, corps: JSON.parse(init.body as string) });
        return json(url.endsWith("/valider/") ? { ...CLOTURE, statut: "validee" } : CLOTURE, 201);
      }
      if (url === "/api/v1/magasins/") return json({ results: [TUNIS] });
      if (url.includes("/situation/")) return json(SITUATION);
      if (url.includes("/depenses/")) return json({ results: [] });
      return json({ results: [CLOTURE] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Tresorerie droits={droits} />
    </QueryClientProvider>,
  );
  return envois;
}

const sansEspaces = (texte: string | null) => (texte ?? "").replace(/\s/g, "");

test("le caissier compte sa caisse et voit les écarts avant d'envoyer", async () => {
  const envois = afficher();
  const especes = await screen.findByLabelText("Espèces comptées");
  fireEvent.change(especes, { target: { value: "250" } });
  const ligne = especes.closest("tr")!;
  expect(sansEspaces(within(ligne as HTMLElement).getAllByRole("cell")[3].textContent)).toBe("37,500TND");
  fireEvent.change(screen.getByLabelText("Chèques comptés"), { target: { value: "180" } });
  fireEvent.change(screen.getByLabelText("Nombre de chèques"), { target: { value: "1" } });
  fireEvent.change(screen.getByLabelText("Total des tickets carte"), { target: { value: "320.5" } });
  fireEvent.change(screen.getByLabelText(/Fond laissé en caisse/), { target: { value: "50" } });
  expect(sansEspaces(screen.getByText(/Espèces à remettre/).textContent)).toBe("Espècesàremettre:200,000TND");
  fireEvent.click(screen.getByRole("button", { name: "Clôturer et envoyer à la finance" }));
  expect(await screen.findByText(/T01-CL2026-000001 envoyée à la finance/)).toBeInTheDocument();
  expect(envois[0]).toEqual({
    url: "/api/v1/tresorerie/clotures/",
    corps: {
      magasin: "m1",
      especes_comptees: "250",
      cheques_comptes: "180",
      nombre_cheques_comptes: 1,
      cartes_comptees: "320.5",
      fond_conserve: "50",
      commentaire_caissier: "",
    },
  });
});

test("la finance valide une clôture", async () => {
  const envois = afficher({ cloturer: false, depenses: false, verifier: true, voirClotures: true });
  expect(await screen.findByText("T01-CL2026-000001 · Tunis")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Rejeter" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Valider" }));
  await vi.waitFor(() => expect(envois).toHaveLength(1));
  expect(envois[0]).toEqual({ url: "/api/v1/tresorerie/clotures/c1/valider/", corps: { commentaire: "" } });
});

test("une dépense de caisse s'enregistre", async () => {
  const envois = afficher();
  fireEvent.click(await screen.findByRole("tab", { name: "Dépenses de caisse" }));
  fireEvent.change(await screen.findByLabelText("Motif"), { target: { value: "Produit vitres" } });
  fireEvent.change(screen.getByLabelText("Montant"), { target: { value: "12.5" } });
  fireEvent.click(screen.getByRole("button", { name: "Enregistrer la dépense" }));
  await vi.waitFor(() => expect(envois).toHaveLength(1));
  expect(envois[0].corps).toEqual({
    magasin_id: "m1",
    categorie: "fournitures",
    motif: "Produit vitres",
    beneficiaire: "",
    montant: "12.5",
  });
});
