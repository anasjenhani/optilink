import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { formaterOeil } from "../api/clients";
import { Clients } from "./Clients";

const DUPONT = {
  id: "c1",
  civilite: "mme",
  nom: "Dupont",
  prenom: "Marie",
  date_naissance: null,
  telephone: "0601020304",
  telephone_2: "",
  email: "",
  adresse: "",
  code_postal: "",
  ville: "Lille",
  societe: "",
  matricule_fiscal: "",
  magasin_origine: "m1",
  accepte_relances: false,
};
const ORDONNANCE = {
  id: "p1",
  type: "lunettes",
  date_prescription: "2026-09-20",
  prescripteur: "Dr Martin",
  mesures: { od: { sphere: "-2.25", cylindre: "-0.50", axe: 90 }, og: { sphere: "1.00", addition: "2.00" } },
  saisie_par: "Opticien",
};

function json(donnees: unknown) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status: 200 }));
}

afterEach(() => vi.unstubAllGlobals());

function afficher(voirOrdonnances: boolean, trouves: unknown[] = [DUPONT], modifierClient = true) {
  const appels: string[] = [];
  const corps: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, options?: RequestInit) => {
      appels.push(url);
      if (options?.method === "POST" || options?.method === "PATCH") {
        const saisie = JSON.parse(options.body as string);
        corps.push({ methode: options.method, url, saisie });
        return json({ ...DUPONT, ...saisie, id: "c2" });
      }
      if (url.startsWith("/api/v1/clients/")) return json({ results: trouves });
      if (url.startsWith("/api/v1/prescriptions/")) return json({ results: [ORDONNANCE] });
      return json({ results: [] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Clients droits={{ creerClient: true, modifierClient, voirOrdonnances, saisirOrdonnance: false }} />
    </QueryClientProvider>,
  );
  return Object.assign(appels, { corps });
}

test("affiche les ordonnances du client choisi", async () => {
  afficher(true);
  fireEvent.change(screen.getByLabelText("Rechercher un client"), { target: { value: "dupont" } });
  fireEvent.click(await screen.findByText("DUPONT Marie"));
  expect(await screen.findByText("OD -2.25 (-0.50 à 90°) · OG +1.00 add +2.00")).toBeInTheDocument();
});

test("ne demande pas les ordonnances sans le droit", async () => {
  const appels = afficher(false);
  fireEvent.change(screen.getByLabelText("Rechercher un client"), { target: { value: "dupont" } });
  fireEvent.click(await screen.findByText("DUPONT Marie"));
  expect(screen.queryByText("Ordonnances")).not.toBeInTheDocument();
  expect(appels.some((url) => url.startsWith("/api/v1/prescriptions/"))).toBe(false);
});

test("notation d'un œil sans cylindre", () => {
  expect(formaterOeil({ sphere: "-1.00", cylindre: "0.00", axe: null })).toBe("-1.00");
});

test("crée un client professionnel avec sa société", async () => {
  const { corps } = afficher(false);
  fireEvent.click(screen.getByRole("button", { name: "Nouveau client" }));
  const remplir = (label: string, valeur: string) =>
    fireEvent.change(screen.getByLabelText(label), { target: { value: valeur } });
  remplir("Nom", "Ben Salah");
  remplir("Prénom", "Karim");
  remplir("Téléphone 2", "98123456");
  remplir("Adresse", "12 rue de Marseille");
  expect(screen.queryByLabelText("Matricule fiscal")).not.toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("Client professionnel (société)"));
  remplir("Nom de la société", "Optique Services SARL");
  remplir("Matricule fiscal", "1234567/A/M/000");
  fireEvent.click(screen.getByRole("button", { name: "Créer le client" }));
  expect(await screen.findByText("Optique Services SARL · MF 1234567/A/M/000")).toBeInTheDocument();
  expect(corps[0]).toMatchObject({
    methode: "POST",
    saisie: { nom: "Ben Salah", telephone_2: "98123456", societe: "Optique Services SARL", date_naissance: null },
  });
});

test("modifie la fiche d'un client", async () => {
  const { corps } = afficher(false);
  fireEvent.change(screen.getByLabelText("Rechercher un client"), { target: { value: "dupont" } });
  fireEvent.click(await screen.findByText("DUPONT Marie"));
  fireEvent.click(screen.getByRole("button", { name: "Modifier la fiche" }));
  fireEvent.change(screen.getByLabelText("Téléphone 2"), { target: { value: "0700000000" } });
  fireEvent.click(screen.getByRole("button", { name: "Enregistrer la fiche" }));
  expect(await screen.findByText("0601020304 · 0700000000")).toBeInTheDocument();
  expect(corps[0]).toMatchObject({
    methode: "PATCH",
    url: "/api/v1/clients/c1/",
    saisie: { telephone_2: "0700000000" },
  });
  expect((corps[0] as { saisie: object }).saisie).not.toHaveProperty("magasin_origine");
});

test("la recherche écarte les clients désactivés, sauf si on demande à les voir", async () => {
  const appels = afficher(false, [{ ...DUPONT, est_actif: false }]);
  fireEvent.change(screen.getByLabelText("Rechercher un client"), { target: { value: "dupont" } });
  await screen.findByText("DUPONT Marie");
  expect(appels.at(-1)).toBe("/api/v1/clients/?recherche=dupont&est_actif=true");
  fireEvent.click(screen.getByLabelText("Voir les clients désactivés"));
  await waitFor(() => expect(appels.at(-1)).toBe("/api/v1/clients/?recherche=dupont"));
  expect(await screen.findByText("Désactivé")).toBeInTheDocument();
});

test("désactive puis réactive la fiche d'un client", async () => {
  const { corps } = afficher(false);
  fireEvent.change(screen.getByLabelText("Rechercher un client"), { target: { value: "dupont" } });
  fireEvent.click(await screen.findByText("DUPONT Marie"));
  fireEvent.click(screen.getByRole("button", { name: "Désactiver" }));
  expect(await screen.findByText(/Fiche désactivée/)).toBeInTheDocument();
  expect(corps[0]).toEqual({ methode: "PATCH", url: "/api/v1/clients/c1/", saisie: { est_actif: false } });
  fireEvent.click(screen.getByRole("button", { name: "Réactiver" }));
  await waitFor(() => expect(screen.queryByText(/Fiche désactivée/)).not.toBeInTheDocument());
  expect(corps[1]).toMatchObject({ methode: "PATCH", saisie: { est_actif: true } });
  expect(screen.getByRole("button", { name: "Désactiver" })).toBeInTheDocument();
});

test("pas de désactivation sans le droit de modifier les clients", async () => {
  afficher(false, [{ ...DUPONT, est_actif: false }], false);
  fireEvent.click(screen.getByLabelText("Voir les clients désactivés"));
  fireEvent.change(screen.getByLabelText("Rechercher un client"), { target: { value: "dupont" } });
  fireEvent.click(await screen.findByText("DUPONT Marie"));
  expect(screen.getByText(/Fiche désactivée/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Réactiver" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Désactiver" })).not.toBeInTheDocument();
});
