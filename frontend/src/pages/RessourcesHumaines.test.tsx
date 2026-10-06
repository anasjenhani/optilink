import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

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
  salaire_base: "1200.000",
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
const KARIM = {
  ...SALMA,
  id: "e2",
  matricule: "T01-E002",
  utilisateur: null,
  nom: "Trabelsi",
  prenom: "Karim",
  poste: "Opticien",
  date_sortie: "2026-09-30",
};
const ACOMPTE = {
  id: "a1",
  employe: "e1",
  employe_nom: "Salma Ben Ali",
  magasin: "Tunis",
  montant: "400.000",
  mois: "2026-10-01",
  motif: "",
  statut: "demande",
  demande_par: "salma",
  decide_par: null,
  decide_le: null,
  commentaire_decision: "",
  mode_versement: "",
  verse_le: null,
  reference_versement: "",
};
const PRIME = {
  id: "p1",
  employe: "e1",
  employe_nom: "Salma Ben Ali",
  magasin: "Tunis",
  type: "objectif",
  type_libelle: "Prime d'objectif (ventes)",
  montant: "150.000",
  mois: "2026-10-01",
  motif: "",
  statut: "proposee",
  proposee_par: "karim",
  validee_par: null,
  validee_le: null,
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

function afficher(
  droits: DroitsRh,
  employe = true,
  { onglet, conge = CONGE, espace = {} }: { onglet?: string; conge?: typeof CONGE; espace?: object } = {},
) {
  const envois: { url: string; corps: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        const corps = JSON.parse(init.body as string);
        envois.push({ url, corps });
        return json({ ...SALMA, ...corps });
      }
      if (init?.method === "POST" && url.includes("annuler")) {
        envois.push({ url, corps: null });
        if (url.includes("mon-espace"))
          return json({ employe: SALMA, conges: [], acomptes: [{ ...ACOMPTE, statut: "annule" }], primes: [] });
        return json({ ...conge, statut: "annulee" });
      }
      if (init?.method === "POST") {
        envois.push({ url, corps: init.body ? JSON.parse(init.body as string) : null });
        if (url.includes("mon-espace")) return json({ employe: SALMA, conges: [CONGE], acomptes: [], primes: [] }, 201);
        if (url.includes("presence")) return json([]);
        return json({ ...CONGE, statut: "acceptee" });
      }
      if (url.includes("mon-espace"))
        return employe
          ? json({ employe: SALMA, conges: [], acomptes: [], primes: [], ...espace })
          : json({ detail: "Aucune fiche" }, 404);
      if (url === "/api/v1/magasins/") return json({ results: [{ id: "m1", nom: "Tunis" }] });
      if (url.includes("/presence/"))
        return json([
          {
            employe: "e1",
            matricule: "T01-E001",
            nom: "Salma Ben Ali",
            poste: "Vendeuse",
            pointage: null,
            conge: null,
          },
        ]);
      if (url.includes("/conges/")) return json({ results: [conge] });
      if (url.includes("/acomptes/")) return json({ results: [{ ...ACOMPTE, statut: "accorde" }] });
      if (url.includes("/primes/")) return json({ results: [PRIME] });
      // Sans ?actifs=true, la liste comprend aussi les employés sortis.
      if (url.includes("/employes/") && !url.includes("actifs")) return json([SALMA, KARIM]);
      return json([SALMA]);
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RessourcesHumaines droits={droits} ongletInitial={onglet} />
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

const CONGE_A_VENIR = { ...CONGE, statut: "acceptee", debut: "2099-01-10", fin: "2099-01-12" };

test("le responsable annule un congé accepté qui n'a pas commencé, après confirmation", async () => {
  const envois = afficher({ ...AUCUN, voirConges: true, annulerConge: true }, false, { conge: CONGE_A_VENIR });
  fireEvent.click(await screen.findByRole("button", { name: "Annuler le congé de Salma Ben Ali" }));
  expect(await screen.findByText(/les jours seront rendus à son solde/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retour" }));
  expect(envois).toHaveLength(0);
  fireEvent.click(screen.getByRole("button", { name: "Annuler le congé de Salma Ben Ali" }));
  fireEvent.click(await screen.findByRole("button", { name: "Confirmer l'annulation" }));
  await vi.waitFor(() => expect(envois).toHaveLength(1));
  expect(envois[0]).toEqual({ url: "/api/v1/rh/conges/c1/annuler/", corps: null });
});

test("pas d'annulation d'un congé déjà commencé, ni sans le droit", async () => {
  afficher({ ...AUCUN, voirConges: true, annulerConge: true }, false, {
    conge: { ...CONGE_A_VENIR, debut: "2020-01-10", fin: "2020-01-12" },
  });
  expect(await screen.findByText("Acceptée")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Annuler/ })).not.toBeInTheDocument();
  vi.unstubAllGlobals();
  cleanup();
  afficher({ ...AUCUN, voirConges: true }, false, { conge: CONGE_A_VENIR });
  expect(await screen.findByText("Acceptée")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Annuler/ })).not.toBeInTheDocument();
});

test("les RH corrigent une fiche employé puis enregistrent sa sortie", async () => {
  const envois = afficher({ ...AUCUN, voirEmployes: true, modifierEmploye: true }, false);
  fireEvent.click(await screen.findByRole("button", { name: "Modifier Salma Ben Ali" }));
  fireEvent.change(screen.getByLabelText("Poste"), { target: { value: "Opticienne" } });
  fireEvent.change(screen.getByLabelText("Téléphone"), { target: { value: "+216 98 000 000" } });
  fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  await vi.waitFor(() => expect(envois).toHaveLength(1));
  expect(envois[0]).toEqual({
    url: "/api/v1/rh/employes/e1/",
    corps: {
      magasin: "m1",
      nom: "Ben Ali",
      prenom: "Salma",
      poste: "Opticienne",
      cin: "",
      telephone: "+216 98 000 000",
      date_embauche: "2026-04-01",
      date_sortie: null,
      conges_par_mois: "1.0",
      solde_conges_initial: "0.0",
      salaire_base: "1200.000",
      utilisateur: "salma",
    },
  });

  fireEvent.click(await screen.findByRole("button", { name: "Sortie de Salma Ben Ali" }));
  fireEvent.change(await screen.findByLabelText("Dernier jour dans l'effectif"), { target: { value: "2026-10-31" } });
  fireEvent.click(screen.getByRole("button", { name: "Enregistrer la sortie" }));
  await vi.waitFor(() => expect(envois).toHaveLength(2));
  expect(envois[1]).toEqual({ url: "/api/v1/rh/employes/e1/", corps: { date_sortie: "2026-10-31" } });
});

test("les employés sortis s'affichent à la demande, sans bouton de sortie", async () => {
  afficher({ ...AUCUN, voirEmployes: true, modifierEmploye: true }, false);
  expect(await screen.findByText("T01-E001 · Vendeuse · Tunis")).toBeInTheDocument();
  expect(screen.queryByText(/Karim/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("Afficher aussi les employés sortis"));
  expect(await screen.findByText("Sorti le 30/09/2026")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Modifier Karim Trabelsi" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Sortie de Karim Trabelsi" })).not.toBeInTheDocument();
  expect(vi.mocked(fetch).mock.calls.some(([url]) => url === "/api/v1/rh/employes/")).toBe(true);
});

test("sans le droit de modifier, la liste des employés est en lecture seule", async () => {
  afficher({ ...AUCUN, voirEmployes: true }, false);
  expect(await screen.findByText("T01-E001 · Vendeuse · Tunis")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Modifier Salma Ben Ali" })).not.toBeInTheDocument();
});

test("les RH annulent un acompte accordé, après confirmation", async () => {
  const envois = afficher({ ...AUCUN, voirAcomptes: true, demanderAcompte: true }, false);
  fireEvent.click(await screen.findByRole("button", { name: "Annuler l'acompte de Salma Ben Ali" }));
  fireEvent.click(await screen.findByRole("button", { name: "Confirmer l'annulation" }));
  await vi.waitFor(() => expect(envois).toHaveLength(1));
  expect(envois[0]).toEqual({ url: "/api/v1/rh/acomptes/a1/annuler/", corps: null });
});

test("une prime proposée s'annule avec le droit de proposer, pas avec celui de valider seul", async () => {
  const envois = afficher({ ...AUCUN, voirPrimes: true, proposerPrime: true }, false);
  fireEvent.click(await screen.findByRole("button", { name: "Annuler la prime de Salma Ben Ali" }));
  fireEvent.click(await screen.findByRole("button", { name: "Confirmer l'annulation" }));
  await vi.waitFor(() => expect(envois).toHaveLength(1));
  expect(envois[0]).toEqual({ url: "/api/v1/rh/primes/p1/annuler/", corps: null });
  vi.unstubAllGlobals();
  cleanup();
  afficher({ ...AUCUN, voirPrimes: true, validerPrime: true }, false);
  expect(await screen.findByRole("button", { name: "Valider" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Annuler/ })).not.toBeInTheDocument();
});

test("l'employée retire sa demande d'acompte encore en attente", async () => {
  const envois = afficher(AUCUN, true, {
    onglet: "mes-acomptes",
    espace: { acomptes: [ACOMPTE, { ...ACOMPTE, id: "a2", statut: "accorde" }] },
  });
  const boutons = await screen.findAllByRole("button", { name: /^Annuler l'acompte/ });
  expect(boutons).toHaveLength(1);
  fireEvent.click(boutons[0]);
  expect(await screen.findByText(/les RH ne la verront plus à décider/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Confirmer l'annulation" }));
  await vi.waitFor(() => expect(envois).toHaveLength(1));
  expect(envois[0]).toEqual({ url: "/api/v1/rh/mon-espace/a1/annuler-acompte/", corps: null });
  expect(await screen.findByText("Annulé")).toBeInTheDocument();
});
