import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { RechercheVerres } from "./RechercheVerres";

afterEach(() => vi.unstubAllGlobals());

const ligne = {
  article: "a1",
  plage: 7,
  reference: "VER-RLX",
  designation: "RELAX 400 ASP 1.56 BLANC",
  fournisseur: "TN OPTIC",
  sphere_debut: "-4.00",
  sphere_fin: "0.00",
  cylindre_debut: "0.00",
  cylindre_fin: "3.00",
  diametre: "70",
  indice: "1.560",
  prix_vente_ttc: "98.573",
  quantite: null,
};

test("trois listes ; un clic choisit le verre avec la plage et son prix", async () => {
  const appel = vi.fn((_url: string) =>
    Promise.resolve(
      new Response(
        JSON.stringify({
          stock_fournisseur: [ligne],
          prescription: [],
          magasin: [{ ...ligne, article: "a2", plage: null, designation: "1.50 GRIS", quantite: 0 }],
        }),
      ),
    ),
  );
  vi.stubGlobal("fetch", appel);
  const choisir = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RechercheVerres
        ouvert
        titre="Verre droit"
        magasin="m1"
        monnaie={{ devise: "TND", decimales: 3 }}
        correction={{ sphere: "-3.50", cylindre: "-0.75" }}
        onChoisir={choisir}
        onFerme={() => {}}
      />
    </QueryClientProvider>,
  );
  const fournisseur = screen.getByRole("region", { name: "Verre Stock Fournisseur" });
  const cellule = await within(fournisseur).findByText("RELAX 400 ASP 1.56 BLANC");
  expect(String(appel.mock.calls[0][0])).toContain("sphere=-3.50");
  const prescription = screen.getByRole("region", { name: "Verre Prescription / RX / Importation" });
  expect(within(prescription).getByText("Aucun verre")).toBeInTheDocument();

  // Plus en stock dans le magasin : la ligne ne se choisit pas.
  fireEvent.click(screen.getByText("1.50 GRIS"));
  expect(choisir).not.toHaveBeenCalled();

  fireEvent.click(cellule);
  expect(choisir).toHaveBeenCalledWith(
    expect.objectContaining({ id: "a1", plage: 7, prix_vente_ttc: "98.573", sur_commande: true }),
  );
});
