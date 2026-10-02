import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";

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

function afficher(voirOrdonnances: boolean) {
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
      if (url.startsWith("/api/v1/clients/")) return json({ results: [DUPONT] });
      if (url.startsWith("/api/v1/prescriptions/")) return json({ results: [ORDONNANCE] });
      return json({ results: [] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Clients droits={{ creerClient: true, modifierClient: true, voirOrdonnances, saisirOrdonnance: false }} />
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
  expect(corps[0]).toMatchObject({ methode: "PATCH", url: "/api/v1/clients/c1/", saisie: { telephone_2: "0700000000" } });
  expect((corps[0] as { saisie: object }).saisie).not.toHaveProperty("magasin_origine");
});
