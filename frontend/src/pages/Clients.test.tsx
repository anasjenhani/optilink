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
  email: "",
  ville: "Lille",
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
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      appels.push(url);
      if (url.startsWith("/api/v1/clients/")) return json({ results: [DUPONT] });
      if (url.startsWith("/api/v1/prescriptions/")) return json({ results: [ORDONNANCE] });
      return json({ results: [] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Clients droits={{ creerClient: true, voirOrdonnances, saisirOrdonnance: false }} />
    </QueryClientProvider>,
  );
  return appels;
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
