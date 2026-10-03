import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";

import { RessourcesHumaines, type DroitsRh } from "./RessourcesHumaines";

const SOLDE = { acquis: "6.0", pris: "0.0", en_attente: "0.0", disponible: "6.0" };
const SALMA = {
  id: "e1",
  matricule: "T01-E001",
  magasin: "m1",
  magasin_nom: "Tunis",
  utilisateur: "salma",
  nom: "Ben Ali",
  prenom: "Salma",
  cin: "",
  telephone: "",
  poste: "Vendeuse",
  date_embauche: "2026-04-01",
  date_sortie: null,
  conges_par_mois: "1.0",
  solde_conges_initial: "0.0",
  solde: SOLDE,
};
const CONGE = {
  id: "c1",
  employe: "e1",
  employe_nom: "Salma Ben Ali",
  magasin: "Tunis",
  type: "annuel",
  type_libelle: "Congé annuel payé",
  debut: "2026-10-12",
  fin: "2026-10-15",
  jours: "4.0",
  motif: "Voyage",
  statut: "demandee",
  demandee_par: "salma",
  decidee_par: null,
  decidee_le: null,
  commentaire_decision: "",
};
const AUCUN: DroitsRh = {
  voirEmployes: false,
  creerEmploye: false,
  voirPresence: false,
  pointer: false,
  voirConges: false,
  saisirConge: false,
  deciderConge: false,
};

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

afterEach(() => vi.unstubAllGlobals());

function afficher(droits: DroitsRh, employe = true) {
  const envois: { url: string; corps: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        envois.push({ url, corps: init.body ? JSON.parse(init.body as string) : null });
        if (url.includes("mon-espace")) return json({ employe: SALMA, conges: [CONGE] }, 201);
        if (url.includes("presence")) return json([]);
        return json({ ...CONGE, statut: "acceptee" });
      }
      if (url.includes("mon-espace")) return employe ? json({ employe: SALMA, conges: [] }) : json({ detail: "Aucune fiche" }, 404);
      if (url === "/api/v1/magasins/") return json({ results: [{ id: "m1", nom: "Tunis" }] });
      if (url.includes("/presence/"))
        return json([{ employe: "e1", matricule: "T01-E001", nom: "Salma Ben Ali", poste: "Vendeuse", pointage: null, conge: null }]);
      if (url.includes("/conges/")) return json({ results: [CONGE] });
      return json([SALMA]);
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RessourcesHumaines droits={droits} />
    </QueryClientProvider>,
  );
  return envois;
}

test("l'employée voit son solde et demande un congé", async () => {
  const envois = afficher(AUCUN);
  expect(await screen.findByText(/Disponible/)).toHaveTextContent("6 j");
  fireEvent.change(screen.getByLabelText("Du"), { target: { value: "2026-10-12" } });
  fireEvent.change(screen.getByLabelText("Au"), { target: { value: "2026-10-15" } });
  fireEvent.change(screen.getByLabelText("Motif"), { target: { value: "Voyage" } });
  fireEvent.click(screen.getByRole("button", { name: "Envoyer la demande" }));
  expect(await screen.findByText("En attente")).toBeInTheDocument();
  expect(envois[0]).toEqual({
    url: "/api/v1/rh/mon-espace/demander/",
    corps: { type: "annuel", debut: "2026-10-12", fin: "2026-10-15", motif: "Voyage" },
  });
});

test("le responsable accepte une demande en attente", async () => {
  const envois = afficher({ ...AUCUN, voirConges: true, deciderConge: true }, false);
  expect(await screen.findByRole("button", { name: "Accepter" })).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "Mes congés" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Refuser" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Accepter" }));
  await vi.waitFor(() => expect(envois).toHaveLength(1));
  expect(envois[0]).toEqual({ url: "/api/v1/rh/conges/c1/accepter/", corps: { commentaire: "" } });
});

test("le responsable pointe la présence du jour", async () => {
  const envois = afficher({ ...AUCUN, voirPresence: true, pointer: true }, false);
  fireEvent.click(await screen.findByRole("button", { name: "Tout le monde présent" }));
  fireEvent.change(screen.getByLabelText("Arrivée Salma Ben Ali"), { target: { value: "09:00" } });
  fireEvent.click(screen.getByRole("button", { name: "Enregistrer la présence" }));
  await vi.waitFor(() => expect(envois).toHaveLength(1));
  expect(envois[0].corps).toMatchObject({
    magasin: "m1",
    lignes: [{ employe: "e1", statut: "present", arrivee: "09:00", depart: null, commentaire: "" }],
  });
});

test("rien ne s'affiche sans fiche ni droit RH", async () => {
  afficher(AUCUN, false);
  await vi.waitFor(() => expect(fetch).toHaveBeenCalled());
  expect(screen.queryByText("Ressources humaines")).not.toBeInTheDocument();
});
