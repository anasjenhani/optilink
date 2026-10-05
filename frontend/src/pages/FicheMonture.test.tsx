import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { calculerPrix } from "../api/fiches";
import { barresEan13, FicheMonture } from "./FicheMonture";

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

afterEach(() => vi.unstubAllGlobals());

test("calcule comme l'ancien logiciel : marge sur le prix d'achat HT, achat net TTC après remise", () => {
  const calcul = calculerPrix({ achatHT: 798.32, remise: 20, tva: 19, venteTTC: 2500, fodec: false });
  expect(calcul.venteHT.toFixed(2)).toBe("2100.84");
  expect(calcul.marge?.toFixed(2)).toBe("163.16");
  expect(calcul.achatNetTTC.toFixed(2)).toBe("760.00");
});

test("dessine un EAN-13", () => {
  expect(barresEan13("2000000000015")).toHaveLength(95);
  expect(barresEan13("CL.S.40235")).toBeNull();
});

test("crée une monture avec son prix ; la marge saisie donne le prix de vente", async () => {
  const appels: { url: string; methode?: string; corps?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      appels.push({ url, methode: init?.method, corps: init?.body ? JSON.parse(init.body as string) : undefined });
      if (url.includes("suggestions"))
        return json({ marque: ["Celine"], modele: [], forme: [], couleur: [], couleur_verres: [] });
      if (url.includes("fournisseurs"))
        return json({ count: 1, results: [{ id: "f1", code: 4, nom: "Cartier Tunisie" }] });
      return json({ id: "a1" }, 201);
    }),
  );
  const onFerme = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <FicheMonture
        article={null}
        magasin="m1"
        monnaie={{ devise: "TND", decimales: 3 }}
        tauxTva={["19.00", "7.00"]}
        onFerme={onFerme}
      />
    </QueryClientProvider>,
  );
  fireEvent.change(screen.getByLabelText("Fournisseur"), { target: { value: "Cartier" } });
  fireEvent.click(await screen.findByText("4 · Cartier Tunisie"));
  fireEvent.mouseDown(screen.getByLabelText("Famille"));
  fireEvent.click(within(screen.getByRole("listbox")).getByText("Lunette Solaire"));
  fireEvent.mouseDown(screen.getByLabelText("Matière"));
  fireEvent.click(within(screen.getByRole("listbox")).getByText("Acétate"));
  fireEvent.change(screen.getByLabelText("Marque"), { target: { value: "Celine" } });
  fireEvent.change(screen.getByLabelText("Référence"), { target: { value: "CL.S.40235-30N" } });
  fireEvent.change(screen.getByLabelText("Taille"), { target: { value: "55" } });
  fireEvent.change(screen.getByLabelText("Prix Achat HT"), { target: { value: "798,32" } });
  fireEvent.change(screen.getByLabelText("Dernier Tx.Remise"), { target: { value: "20" } });
  fireEvent.change(screen.getByLabelText("Marge"), { target: { value: "100" } });
  fireEvent.blur(screen.getByLabelText("Marge"));
  expect(screen.getByLabelText("Prix Vente TTC")).toHaveValue("1900.002");
  expect(screen.getByLabelText("Prix Achat Net TTC")).toHaveValue("760.001");
  fireEvent.click(screen.getByRole("checkbox", { name: "Promotion" }));
  fireEvent.keyDown(window, { key: "F4" });

  await vi.waitFor(() => expect(onFerme).toHaveBeenCalled());
  expect(appels.find((a) => a.methode === "POST")).toMatchObject({
    url: "/api/v1/fiches-articles/?magasin=m1",
    corps: {
      famille: "monture",
      fournisseur: "f1",
      reference: "CL.S.40235-30N",
      promotion: true,
      stockable: true,
      monture: { categorie: "solaire", matiere: "acetate", marque: "Celine", calibre: 55 },
      nouveau_prix: { prix_achat_ht: "798.32", taux_remise_achat: "20", taux_tva: "19", prix_vente_ttc: "1900.002" },
    },
  });
});
