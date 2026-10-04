import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { FicheLentilles } from "./FicheLentilles";

const ORDONNANCE = {
  id: "p2",
  type: "lentilles",
  date_prescription: "2026-09-01",
  prescripteur: "Dr Gharbi",
  mesures: {
    od: { sphere: "-2.00", cylindre: "0.00", axe: null, rayon: "8.60", diametre: "14.20" },
    og: { sphere: "-1.75", cylindre: "0.00", axe: null, rayon: "8.60", diametre: "14.20" },
  },
};
const LENTILLE = {
  id: "l1",
  reference: "LEN-1",
  libelle: "Acuvue Oasys (6)",
  famille: "lentille",
  code_barres: "",
  description: "",
  sur_commande: false,
  prix_vente_ttc: "95.000",
  stock: 10,
};

test("lentilles reprises de l'ordonnance, quantité et lot par œil", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      const reponse = (donnees: unknown) => Promise.resolve(new Response(JSON.stringify(donnees)));
      if (url.startsWith("/api/v1/prescriptions/")) return reponse({ results: [ORDONNANCE] });
      if (url.startsWith("/api/v1/lentilles/")) return reponse({ results: [] });
      return reponse({ results: [LENTILLE] });
    }),
  );
  const onValider = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <FicheLentilles
        magasin="m"
        client={{ id: "c1", numero: 42, nom: "Ben Ali", prenom: "Sami" } as never}
        monnaie={{ devise: "TND", decimales: 3 }}
        numero={1}
        droits={{ remise: true, voirOrdonnances: true, saisirOrdonnance: true }}
        onValider={onValider}
      />
    </QueryClientProvider>,
  );

  fireEvent.mouseDown(await screen.findByLabelText("Ordonnance de lentilles"));
  fireEvent.click(await screen.findByRole("option", { name: /Dr Gharbi/ }));
  const droit = screen.getByText("Œil droit").closest("div")!;
  expect(within(droit).getByLabelText("Sph")).toHaveValue("-2.00");
  expect(within(droit).getByLabelText("Rayon")).toHaveValue("8.60");

  const [designationD] = screen.getAllByRole("combobox", { name: "Désignation" });
  fireEvent.change(designationD, { target: { value: "acu" } });
  fireEvent.click(await screen.findByRole("option", { name: /Acuvue/ }));
  fireEvent.change(screen.getAllByLabelText("Qté")[0], { target: { value: "2" } });
  fireEvent.change(screen.getAllByLabelText("N° lot")[0], { target: { value: "B123" } });
  fireEvent.click(screen.getByRole("button", { name: "Copier la lentille droite" }));
  expect(screen.getByText(/Total lentilles/)).toHaveTextContent("380,000");

  fireEvent.click(screen.getByRole("button", { name: "Valider les lentilles" }));
  await waitFor(() => expect(onValider).toHaveBeenCalled());
  const [jeu, choisies] = onValider.mock.calls[0];
  expect(jeu).toEqual({ prescription: "p2", observation: "" });
  expect(
    choisies.map((c: { role: string; quantite: number; numero_lot: string }) => [c.role, c.quantite, c.numero_lot]),
  ).toEqual([
    ["lentille_d", 2, "B123"],
    ["lentille_g", 2, "B123"],
  ]);
  vi.unstubAllGlobals();
});
