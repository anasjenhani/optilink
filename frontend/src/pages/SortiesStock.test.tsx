import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

import { DemandesTransfert, PeremptionLentilles, Reassort } from "./SortiesStock";

const PAYS = { code: "TN", devise: "TND", decimales: 3, timbre_fiscal: "1.000" };
const MAGASIN = { id: "m1", code: "T01", nom: "Tunis Centre", societe_id: "s1", type: "magasin", pays: PAYS };
const DEPOT = { id: "d1", code: "DEP", nom: "Dépôt central", societe_id: "s1", type: "depot", pays: PAYS };

const ecran = (contenu: ReactNode) =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      {contenu}
    </QueryClientProvider>,
  );

function simuler(reponses: (url: string) => unknown, envois: unknown[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") envois.push({ url, corps: init.body ? JSON.parse(init.body as string) : null });
      return Promise.resolve(new Response(JSON.stringify(reponses(url))));
    }),
  );
}

afterEach(() => vi.unstubAllGlobals());

test("le dépôt sert une demande d'alimentation avec moins que demandé", async () => {
  const envois: unknown[] = [];
  const demande = {
    id: "dm1",
    numero: "T01-DT2026-000001",
    magasin: "Tunis Centre",
    magasin_id: "m1",
    aupres_de: "Dépôt central",
    aupres_de_id: "d1",
    statut: "en_attente",
    statut_libelle: "En attente",
    observation: "",
    cree_le: "2026-10-09T10:00:00+01:00",
    demandee_par: "Amel",
    traitee_par: "",
    traitee_le: null,
    motif_refus: "",
    transfert: null,
    lignes: [
      { article: "a1", reference: "MON-1", libelle: "Monture", famille: "monture", quantite: 4, quantite_servie: 0 },
    ],
  };
  simuler((url) => (url.includes("sens=recues") ? { results: [demande] } : { results: [] }), envois);
  ecran(<DemandesTransfert alimentation demander={false} servir />);

  fireEvent.click(screen.getByRole("tab", { name: "Demandes à servir" }));
  fireEvent.click(await screen.findByText("T01-DT2026-000001"));
  fireEvent.change(screen.getByLabelText("Envoyer Monture"), { target: { value: "3" } });
  fireEvent.click(screen.getByRole("button", { name: "Servir (envoyer le transfert)" }));
  await vi.waitFor(() =>
    expect(envois).toEqual([
      { url: "/api/v1/demandes-transfert/dm1/servir/", corps: { lignes: [{ article: "a1", quantite: 3 }] } },
    ]),
  );
});

test("le réassort part en demande d'alimentation au dépôt", async () => {
  const envois: unknown[] = [];
  simuler((url) => {
    if (url.startsWith("/api/v1/magasins/")) return { results: [MAGASIN, DEPOT] };
    if (url.includes("reassort")) {
      return [
        {
          article: "a1",
          reference: "MON-1",
          libelle: "Monture",
          famille: "monture",
          vendu: 2,
          stock: 1,
          stock_depot: 10,
          propose: 2,
        },
      ];
    }
    return { numero: "T01-DT2026-000002", aupres_de: "Dépôt central" };
  }, envois);
  ecran(<Reassort />);

  fireEvent.change(await screen.findByLabelText("Demander Monture"), { target: { value: "1" } });
  fireEvent.click(screen.getByRole("button", { name: "Demander au dépôt (1 articles)" }));
  expect(await screen.findByText(/T01-DT2026-000002 envoyée/)).toBeInTheDocument();
  expect(envois).toEqual([
    {
      url: "/api/v1/demandes-transfert/",
      corps: {
        magasin: "m1",
        aupres_de: "d1",
        observation: expect.stringContaining("Réassort"),
        lignes: [{ article: "a1", quantite: 1 }],
      },
    },
  ]);
});

test("la péremption des lentilles met les périmées en tête et cache celles sans souci", async () => {
  const lentille = (reference: string, etat: string, lots: { date: string | null; quantite: number }[]) => ({
    article: reference,
    reference,
    libelle: `biofinity ${reference}`,
    stock: lots.reduce((s, l) => s + l.quantite, 0),
    prochaine: lots[0].date,
    etat,
    lots,
  });
  simuler(
    (url) =>
      url.includes("peremptions-lentilles")
        ? [
            lentille("LEN-1", "perimee", [{ date: "2026-09-30", quantite: 2 }]),
            lentille("LEN-2", "inconnue", [{ date: null, quantite: 3 }]),
            lentille("LEN-3", "ok", [{ date: "2027-06-30", quantite: 6 }]),
          ]
        : { results: [MAGASIN] },
    [],
  );
  ecran(<PeremptionLentilles />);

  expect(
    await screen.findByText("1 périmées · 0 bientôt périmées · 1 à dater (au prochain inventaire des lentilles)"),
  ).toBeInTheDocument();
  expect(screen.getByText("Périmée")).toBeInTheDocument();
  expect(screen.getByText("3 × date inconnue")).toBeInTheDocument();
  expect(screen.queryByText("LEN-3")).not.toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("Voir aussi les lentilles sans souci"));
  expect(screen.getByText("LEN-3")).toBeInTheDocument();
});
