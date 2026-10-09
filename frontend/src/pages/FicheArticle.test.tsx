import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { FicheArticle, type FamilleArticle } from "./FicheArticle";

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

const LENTILLE = {
  id: "a7",
  reference: "LEN-000001",
  libelle: "Acuvue Oasys Bimensuelle",
  famille: "lentille",
  code_barres: "3600000000001",
  fournisseur: "f1",
  fournisseur_nom: "Essilor Tunisie",
  fournisseur_code: 4,
  reference_fournisseur: "",
  est_actif: true,
  stockable: true,
  suivi_numero_serie: false,
  promotion: false,
  etui_special: false,
  fodec: false,
  observation: "",
  monture: null,
  verre: null,
  lentille: {
    marque: "Acuvue",
    modele: "Oasys",
    renouvellement: "bimensuelle",
    type: "torique",
    rayon: "8.6",
    diametre: "14.0",
    puissance: "-3.25",
    cylindre: null,
    axe: 180,
    addition: null,
    lentilles_par_boite: 6,
  },
  prix: { prix_achat_ht: "40.000", taux_remise_achat: "0.00", taux_tva: "7.00", prix_vente_ttc: "85.000" },
  dernier_achat: null,
  stocks: [{ magasin: "Tunis Centre", stock: 12 }],
  cree_par: "anas",
  cree_le: "2026-10-05T10:00:00Z",
};

afterEach(() => vi.unstubAllGlobals());

function espionner(fiche: unknown = { id: "a1" }) {
  const appels: { url: string; methode?: string; corps?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      appels.push({ url, methode: init?.method, corps: init?.body ? JSON.parse(init.body as string) : undefined });
      if (url.includes("fournisseurs"))
        return json({ count: 1, results: [{ id: "f1", code: 4, nom: "Essilor Tunisie" }] });
      return json(fiche, init?.method === "POST" ? 201 : 200);
    }),
  );
  return appels;
}

function afficher(famille: FamilleArticle, article: string | null, onFerme = vi.fn(), lectureSeule = false) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <FicheArticle
        famille={famille}
        article={article}
        magasin="m1"
        monnaie={{ devise: "TND", decimales: 3 }}
        tauxTva={["19.00", "7.00"]}
        lectureSeule={lectureSeule}
        onFerme={onFerme}
      />
    </QueryClientProvider>,
  );
  return onFerme;
}

async function choisirFournisseur() {
  fireEvent.change(screen.getByLabelText("Fournisseur"), { target: { value: "Essilor" } });
  fireEvent.click(await screen.findByText("4 · Essilor Tunisie"));
}

test("crée un verre avec ses caractéristiques et son prix", async () => {
  const appels = espionner();
  const onFerme = afficher("verre", null);
  expect(screen.getByText("Fiche Verre")).toBeInTheDocument();
  await choisirFournisseur();
  const valider = screen.getByRole("button", { name: "Valider [F4]" });
  expect(valider).toBeDisabled(); // La géométrie est obligatoire.

  fireEvent.change(screen.getByLabelText("Marque"), { target: { value: "Essilor" } });
  fireEvent.change(screen.getByLabelText("Gamme"), { target: { value: "Varilux Comfort" } });
  fireEvent.mouseDown(screen.getByLabelText(/Géométrie/));
  fireEvent.click(within(screen.getByRole("listbox")).getByText("Progressif"));
  fireEvent.change(screen.getByLabelText("Indice"), { target: { value: "1,6" } });
  fireEvent.change(screen.getByLabelText("Diamètre"), { target: { value: "70 mm" } });
  fireEvent.click(screen.getByRole("checkbox", { name: "Photochromique" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Stockable" }));
  fireEvent.change(screen.getByLabelText("Prix Achat HT"), { target: { value: "150" } });
  fireEvent.change(screen.getByLabelText("Prix Vente TTC"), { target: { value: "320" } });
  fireEvent.click(valider);

  await vi.waitFor(() => expect(onFerme).toHaveBeenCalled());
  expect(appels.find((a) => a.methode === "POST")).toMatchObject({
    url: "/api/v1/fiches-articles/?magasin=m1",
    corps: {
      famille: "verre",
      fournisseur: "f1",
      est_actif: true,
      stockable: false,
      verre: {
        marque: "Essilor",
        gamme: "Varilux Comfort",
        geometrie: "progressif",
        indice: "1.6",
        matiere: "",
        diametre: 70,
        photochromique: true,
      },
      nouveau_prix: { prix_achat_ht: "150", taux_tva: "19", prix_vente_ttc: "320" },
    },
  });
  expect(appels.find((a) => a.methode === "POST")?.corps).not.toHaveProperty("lentille");
});

test("modifie une lentille et la désactive au lieu de la supprimer", async () => {
  const appels = espionner(LENTILLE);
  const onFerme = afficher("lentille", "a7");
  expect(await screen.findByLabelText("Puissance")).toHaveValue("-3.25");
  expect(screen.getByLabelText("Marque")).toHaveValue("Acuvue");
  expect(screen.getByLabelText("Fournisseur")).toHaveValue("4 · Essilor Tunisie");
  expect(screen.getByLabelText("Prix Vente TTC")).toHaveValue("85.000");
  expect(screen.queryByRole("button", { name: /Supprimer/ })).not.toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Puissance"), { target: { value: "-3,50" } });
  fireEvent.click(screen.getByRole("checkbox", { name: "Actif" }));
  fireEvent.keyDown(window, { key: "F4" });

  await vi.waitFor(() => expect(onFerme).toHaveBeenCalled());
  expect(appels.find((a) => a.methode === "PATCH")).toMatchObject({
    url: "/api/v1/fiches-articles/a7/?magasin=m1",
    corps: {
      famille: "lentille",
      est_actif: false,
      lentille: { renouvellement: "bimensuelle", type: "torique", puissance: "-3.50", cylindre: null, axe: 180 },
      nouveau_prix: { taux_tva: "7", prix_vente_ttc: "85.000" },
    },
  });

  fireEvent.click(screen.getByRole("tab", { name: "Stock" }));
  expect(screen.getByText("12")).toBeInTheDocument();
});

test("un article divers demande sa désignation, sans caractéristiques ni prix s'il n'est pas saisi", async () => {
  const appels = espionner();
  afficher("divers", null);
  expect(screen.getByText("Fiche Article")).toBeInTheDocument();
  await choisirFournisseur();
  expect(screen.getByRole("button", { name: "Valider [F4]" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText(/Désignation/), { target: { value: "Spray nettoyant 30 ml" } });
  fireEvent.click(screen.getByRole("button", { name: "Valider [F4]" }));
  await vi.waitFor(() => expect(appels.some((a) => a.methode === "POST")).toBe(true));
  const corps = appels.find((a) => a.methode === "POST")?.corps as Record<string, unknown>;
  expect(corps).toMatchObject({ famille: "divers", libelle: "Spray nettoyant 30 ml" });
  expect(corps).not.toHaveProperty("verre");
  expect(corps).not.toHaveProperty("nouveau_prix");
});

test("lecture seule : pas de bouton Valider", async () => {
  espionner(LENTILLE);
  afficher("lentille", "a7", vi.fn(), true);
  expect(await screen.findByLabelText("Puissance")).toHaveValue("-3.25");
  expect(screen.queryByRole("button", { name: "Valider [F4]" })).not.toBeInTheDocument();
  expect(screen.getByRole("checkbox", { name: "Actif" })).toBeDisabled();
});
