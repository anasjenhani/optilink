import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { FicheLunette } from "./FicheLunette";

const CLIENT = { id: "c1", numero: 42, nom: "Ben Ali", prenom: "Sami" };
const ORDONNANCE = {
  id: "p1",
  type: "lunettes",
  date_prescription: "2026-09-01",
  prescripteur: "Dr Gharbi",
  mesures: {
    od: { sphere: "-1.25", cylindre: "-0.50", axe: 90, addition: "2.00" },
    og: { sphere: "-1.00", cylindre: "0.00", axe: null, addition: "2.00" },
    ecart_pupillaire: "63.0",
  },
};
const article = (id: string, famille: string, libelle: string, prix: string, code: string) => ({
  id,
  reference: id.toUpperCase(),
  libelle,
  famille,
  code_barres: code,
  description: "",
  sur_commande: famille !== "monture",
  prix_vente_ttc: prix,
  stock: famille === "monture" ? 2 : null,
});
const ARTICLES: Record<string, ReturnType<typeof article>[]> = {
  monture: [article("m1", "monture", "Ray-Ban RB5154", "289.500", "3601234")],
  verre: [article("v1", "verre", "Varilux Comfort 1.6", "180.000", "VAR16")],
  supplement: [article("s1", "supplement", "Antireflet", "40.000", "AR")],
};

function simuler() {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      const reponse = (donnees: unknown) => Promise.resolve(new Response(JSON.stringify(donnees)));
      if (url.startsWith("/api/v1/prescriptions/")) return reponse({ results: [ORDONNANCE] });
      if (url.startsWith("/api/v1/lunettes/")) return reponse({ results: [] });
      const famille = new URL(url, "http://x").searchParams.get("famille") ?? "";
      return reponse({ results: ARTICLES[famille] ?? [] });
    }),
  );
}

afterEach(() => vi.unstubAllGlobals());

test("ordonnance reprise, monture et verres scannés, lunette validée avec ses places", async () => {
  simuler();
  const onValider = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <FicheLunette
        magasin="m"
        client={CLIENT as never}
        monnaie={{ devise: "TND", decimales: 3 }}
        numero={1}
        droits={{ remise: true, voirOrdonnances: true, saisirOrdonnance: true }}
        onValider={onValider}
      />
    </QueryClientProvider>,
  );

  // Sans ordonnance, des verres correcteurs sont refusés.
  fireEvent.mouseDown(await screen.findByLabelText("Ordonnance (ophtalmo)"));
  fireEvent.click(await screen.findByRole("option", { name: /Dr Gharbi/ }));
  const droit = screen.getByText("Œil droit").closest("div")!;
  expect(within(droit).getAllByLabelText("Sph")[0]).toHaveValue("-1.25");
  // Près = loin + addition ; demi-écarts pris dans l'ordonnance.
  expect(within(droit).getAllByLabelText("Sph")[1]).toHaveValue("+0.75");
  expect(within(droit).getByLabelText("E.I.P")).toHaveValue("31.5");

  const code = screen.getByLabelText("Code");
  fireEvent.change(code, { target: { value: "3601234" } });
  fireEvent.keyDown(code, { key: "Enter" });
  await waitFor(() => expect(screen.getByRole("combobox", { name: "Monture" })).toHaveValue("Ray-Ban RB5154"));

  const choisir = async (champ: HTMLElement, texte: string, option: RegExp) => {
    fireEvent.change(champ, { target: { value: texte } });
    fireEvent.click(await screen.findByRole("option", { name: option }));
  };
  await choisir(screen.getAllByRole("combobox", { name: "Verre" })[0], "vari", /Varilux/);
  await choisir(screen.getAllByRole("combobox", { name: "Ajouter un supplément" })[0], "anti", /Antireflet/);
  await screen.findByRole("button", { name: "Antireflet ✕" });
  fireEvent.click(screen.getByRole("button", { name: "Copier le verre droit" }));
  expect(screen.getByText(/Total lunette/)).toHaveTextContent("729,500");

  fireEvent.click(screen.getByRole("radio", { name: "Progressif" }));
  fireEvent.click(screen.getByRole("button", { name: "Valider la lunette" }));
  await waitFor(() => expect(onValider).toHaveBeenCalled());
  const [lunette, articles] = onValider.mock.calls[0];
  expect(lunette).toMatchObject({ vision: "progressif", prescription: "p1", ecart_d: "31.5", solaire: false });
  expect(articles.map((a: { role: string; article: { id: string } }) => `${a.role}:${a.article.id}`)).toEqual([
    "monture:m1",
    "verre_d:v1",
    "verre_g:v1",
    "supplement_d:s1",
    "supplement_g:s1",
  ]);
});
