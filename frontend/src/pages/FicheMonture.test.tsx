import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { calculerPrix } from "../api/fiches";
import { formatCode, pageEtiquettes } from "./EtiquetteCodeBarres";
import { FicheMonture } from "./FicheMonture";

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("calcule comme l'ancien logiciel : marge sur le prix d'achat HT, achat net TTC après remise", () => {
  const calcul = calculerPrix({ achatHT: 798.32, remise: 20, tva: 19, venteTTC: 2500, fodec: false });
  expect(calcul.venteHT.toFixed(2)).toBe("2100.84");
  expect(calcul.marge?.toFixed(2)).toBe("163.16");
  expect(calcul.achatNetTTC.toFixed(2)).toBe("760.00");
});

test("code-barres : EAN-13 si la clé est juste, sinon Code 128 ; une étiquette par page", () => {
  expect(formatCode("2000000000015")).toBe("EAN13");
  expect(formatCode("2000000000016")).toBe("CODE128");
  expect(formatCode("CL.S.40235")).toBe("CODE128");
  const page = pageEtiquettes({
    svg: "<svg></svg>",
    titre: "Celine <CL40235>",
    reference: "CL.S.40235-30N",
    prix: "2 500,000 TND",
    copies: 3,
    largeur: 50,
    hauteur: 25,
  });
  expect(page).toContain("@page { size: 50mm 25mm; margin: 0; }");
  expect(page.match(/class="e"/g)).toHaveLength(3);
  expect(page).toContain("Celine &lt;CL40235&gt;");
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

test("l'onglet Code A Barre dessine le code et imprime", async () => {
  // jsdom n'a pas de canvas : JsBarcode y mesure la largeur du texte sous les barres.
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
    measureText: () => ({ width: 60 }),
  } as unknown as CanvasRenderingContext2D);
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.includes("suggestions"))
        return json({ marque: [], modele: [], forme: [], couleur: [], couleur_verres: [] });
      return json({
        id: "a1",
        reference: "CL.S.40235-30N",
        libelle: "Celine",
        famille: "monture",
        code_barres: "2000000000015",
        fournisseur: "f1",
        fournisseur_nom: "Cartier Tunisie",
        fournisseur_code: 4,
        reference_fournisseur: "",
        est_actif: true,
        stockable: true,
        suivi_numero_serie: false,
        promotion: false,
        etui_special: false,
        fodec: false,
        observation: "",
        monture: { categorie: "solaire", marque: "Celine", modele: "CL40235" },
        prix: { prix_achat_ht: "798.320", taux_remise_achat: "20.00", taux_tva: "19.00", prix_vente_ttc: "2500.000" },
        dernier_achat: null,
        stocks: [],
        cree_par: "anas",
        cree_le: "2026-10-05T10:00:00Z",
      });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <FicheMonture
        article="a1"
        magasin="m1"
        monnaie={{ devise: "TND", decimales: 3 }}
        tauxTva={["19.00"]}
        onFerme={vi.fn()}
      />
    </QueryClientProvider>,
  );
  fireEvent.click(await screen.findByRole("tab", { name: "Code A Barre" }));
  const dessin = screen.getByRole("img", { name: "Code-barres 2000000000015" });
  await vi.waitFor(() => expect(dessin.querySelectorAll("rect").length).toBeGreaterThan(10));
  fireEvent.change(screen.getByLabelText("Nombre d'étiquettes"), { target: { value: "2" } });
  fireEvent.click(screen.getByRole("button", { name: "Imprimer" }));
  const cadre = document.querySelector("iframe");
  expect(cadre?.contentDocument?.body.innerHTML).toContain("CL.S.40235-30N");
  expect(cadre?.contentDocument?.querySelectorAll(".e")).toHaveLength(2);
});
