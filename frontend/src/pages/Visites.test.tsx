import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { Visites } from "./Visites";

const MAGASIN = { id: "m1", code: "T01", nom: "Tunis Centre", pays: { devise: "TND", decimales: 3 } };
const VISITE = {
  id: "v1",
  numero: "T01-T2026-000001",
  magasin: "T01",
  devise: "TND",
  cree_le: "2026-10-04T10:15:00+01:00",
  vendeur: "claire",
  total_ttc: "649.500",
  pris_en_charge: "0.000",
  reste_a_payer: "449.500",
  statut: "en_commande",
  peniche: 12,
  livraison_prevue_le: null,
  facture: null,
  client: { id: "c1", nom: "BEN SALAH Amel", matricule_fiscal: "" },
  lignes: [{ id: 1, libelle: "Monture MON-T", quantite: 1, quantite_reprise: 0, total_ttc: "289.500", prix_unitaire_ttc: "289.500", remise_pct: "0.00" }],
};
const FICHE = {
  ...VISITE,
  magasin_nom: "Tunis Centre",
  vendeur_nom: "Claire Martin",
  client_fiche: { id: "c1", numero: 7, nom: "BEN SALAH Amel", telephone: "98 123 456", organisme: "CNAM", numero_affilie: "123" },
  etat: "montage",
  etat_libelle: "Montage en cours",
  reglements: [{ mode: "especes", mode_libelle: "Espèces", montant: "200.000", recu_le: "2026-10-04T10:15:00+01:00", recu_par: "Claire Martin" }],
  prises_en_charge: [],
  etapes: [],
  verres_commandes: [
    { id: 5, ligne: 2, libelle: "Verre unifocal", commande_fournisseur: "T01-A2026-000001", fournisseur: "Labo Verres", statut: "recue", recu_le: "2026-10-04T12:00:00+01:00", casse: null },
  ],
  avoirs: [],
};

afterEach(() => vi.unstubAllGlobals());

test("filtre les visites et ouvre la fiche, d'où l'on déclare une casse", async () => {
  const urls: string[] = [];
  const envois: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      urls.push(url);
      const json = (d: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(d), { status }));
      if (url === "/api/v1/magasins/") return json({ results: [MAGASIN] });
      if (url.endsWith("/fiche/")) return json(FICHE);
      if (init?.method === "POST") {
        envois.push(JSON.parse(init.body as string));
        return json({ id: "k1" }, 201);
      }
      return json({ count: 1, results: [VISITE] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Visites casse />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("BEN SALAH Amel")).toBeInTheDocument();
  fireEvent.click(within(screen.getByRole("group", { name: "Facture" })).getByRole("button", { name: "Non facturée" }));
  fireEvent.change(screen.getByLabelText(/N° visite, nom/), { target: { value: "salah" } });
  fireEvent.click(screen.getByRole("button", { name: "Rechercher" }));
  await vi.waitFor(() => expect(urls.some((u) => u.includes("recherche=salah") && u.includes("facturee=false"))).toBe(true));

  fireEvent.click((await screen.findAllByRole("button", { name: "T01-T2026-000001" }))[0]);
  const fiche = await screen.findByRole("dialog", { name: /Visite T01-T2026-000001/ });
  expect(await within(fiche).findByText(/Suivi : Montage en cours/)).toBeInTheDocument();
  expect(within(fiche).getByText(/prise en charge CNAM/)).toBeInTheDocument();

  fireEvent.click(within(fiche).getByRole("button", { name: "Casse" }));
  fireEvent.change(within(fiche).getByLabelText("Observation"), { target: { value: "Éclat" } });
  fireEvent.click(within(fiche).getByRole("button", { name: "Déclarer la casse" }));
  await vi.waitFor(() => expect(envois).toEqual([{ ligne_commande: 5, cause: "atelier", observation: "Éclat" }]));
});
