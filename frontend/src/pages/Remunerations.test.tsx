import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";

import { Acomptes, MesAcomptes, Primes, RecapPaie } from "./Remunerations";

const ACOMPTE = {
  id: "a1",
  employe: "e1",
  employe_nom: "Salma Ben Ali",
  magasin: "Tunis",
  montant: "400.000",
  mois: "2026-10-01",
  motif: "Rentrée scolaire",
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

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

afterEach(() => vi.unstubAllGlobals());

function afficher(ecran: React.ReactNode, acompte = ACOMPTE) {
  const envois: { url: string; corps: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        envois.push({ url, corps: JSON.parse(init.body as string) });
        if (url.includes("mon-espace")) return json({ employe: {}, conges: [], acomptes: [ACOMPTE], primes: [] }, 201);
        return json(acompte);
      }
      if (url.includes("/acomptes/")) return json({ results: [acompte] });
      if (url.includes("/primes/")) return json({ results: [PRIME] });
      if (url.includes("/recap/"))
        return json([{ employe: "e1", matricule: "T01-E001", nom: "Salma Ben Ali", magasin: "Tunis", salaire_base: "1200.000", acomptes: "250.000", primes: "100.000" }]);
      return json([{ id: "e1", nom: "Ben Ali", prenom: "Salma", magasin_nom: "Tunis" }]);
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ecran}</QueryClientProvider>,
  );
  return envois;
}

const sansEspaces = (texte: string | null) => (texte ?? "").replace(/\s/g, "");

test("l'employée demande un acompte", async () => {
  const envois = afficher(<MesAcomptes acomptes={[]} primes={[]} salaire="1200.000" />);
  expect(sansEspaces(screen.getByText(/Salaire de base/).textContent)).toContain("1200,000TND");
  fireEvent.change(screen.getByLabelText("Montant de l'acompte"), { target: { value: "400" } });
  fireEvent.click(screen.getByRole("button", { name: "Demander l'acompte" }));
  await vi.waitFor(() => expect(envois).toHaveLength(1));
  expect(envois[0]).toEqual({ url: "/api/v1/rh/mon-espace/demander-acompte/", corps: { montant: "400", motif: "" } });
});

test("les RH versent un acompte accordé par virement", async () => {
  const envois = afficher(<Acomptes demander={false} decider />, { ...ACOMPTE, statut: "accorde" });
  fireEvent.mouseDown(await screen.findByLabelText("Versement Salma Ben Ali"));
  fireEvent.click(await screen.findByRole("option", { name: "Virement" }));
  const bouton = screen.getByRole("button", { name: "Marquer versé" });
  expect(bouton).toBeDisabled();
  fireEvent.change(screen.getByLabelText("N° de virement ou de chèque"), { target: { value: "VIR-88" } });
  fireEvent.click(bouton);
  await vi.waitFor(() => expect(envois).toHaveLength(1));
  expect(envois[0]).toEqual({ url: "/api/v1/rh/acomptes/a1/verser/", corps: { mode: "virement", reference: "VIR-88" } });
});

test("les RH valident une prime proposée", async () => {
  const envois = afficher(<Primes proposer={false} valider />);
  fireEvent.click(await screen.findByRole("button", { name: "Valider" }));
  await vi.waitFor(() => expect(envois).toHaveLength(1));
  expect(envois[0]).toEqual({ url: "/api/v1/rh/primes/p1/valider/", corps: { commentaire: "" } });
});

test("le récapitulatif montre primes et acomptes du mois", async () => {
  afficher(<RecapPaie />);
  const ligne = (await screen.findByText("Salma Ben Ali")).closest("tr")!;
  expect(sansEspaces(ligne.textContent)).toBe("SalmaBenAliT01-E001·Tunis1200,000TND100,000TND250,000TND");
});
