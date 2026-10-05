import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { BonReception, calculerBon, type LigneSaisie } from "./BonReception";

const TUNIS = {
  id: "m1",
  code: "T01",
  nom: "Tunis",
  societe: "Optique de Tunis",
  ville: "Tunis",
  pays: {
    code: "TN",
    nom: "Tunisie",
    devise: "TND",
    decimales: 3,
    indicatif_telephonique: "+216",
    timbre_fiscal: "1.000",
    libelle_identifiant_prescripteur: "",
  },
};
const ESSILOR = {
  id: "f1",
  code: 3,
  nom: "Essilor Tunisie",
  adresse: "Rue du Lac",
  ville: "Tunis",
  telephone: "71000000",
  fodec: true,
  regime_tva: "assujetti",
};
const verre = (ligne: number, oeil: "D" | "G") => ({
  ligne_commande: ligne,
  commande: "T01-C2026-000001",
  commande_client: "T01-T2026-000003",
  client: "BEN SALAH Leila",
  oeil,
  article: { id: "v1", reference: "VER-1", libelle: "Verre progressif", famille: "verre", code_barres: "" },
  designation: `Verre progressif ${oeil === "D" ? "droit" : "gauche"}`,
  quantite: 1,
  dernier_prix_achat: "80.000",
  taux_tva: "19.00",
});

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

afterEach(() => vi.unstubAllGlobals());

function afficher() {
  const envois: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        envois.push(JSON.parse(init.body as string));
        return json({ id: "b1", numero: "T01-R2026-000001", numero_bl: "BL-77", total_ttc: "96.390" }, 201);
      }
      if (url === "/api/v1/magasins/") return json({ results: [TUNIS] });
      if (url.startsWith("/api/v1/fournisseurs/")) return json({ count: 1, results: [ESSILOR] });
      if (url.includes("/a-recevoir/")) return json([verre(11, "D"), verre(12, "G")]);
      return json({ results: [] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <BonReception droitsFournisseurs={{ creer: false, modifier: false }} />
    </QueryClientProvider>,
  );
  return envois;
}

test("reçoit les verres d'un bon de commande, avec un verre non conforme", async () => {
  const envois = afficher();
  fireEvent.click(await screen.findByRole("button", { name: "Rechercher un fournisseur" }));
  fireEvent.click(await screen.findByText("Essilor Tunisie"));
  expect(screen.getByText(/soumis au FODEC/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Importer Bon Commande" }));
  fireEvent.click(await screen.findByRole("checkbox", { name: "Tout choisir" }));
  fireEvent.click(screen.getByRole("button", { name: "Importer" }));

  const lignes = await screen.findByRole("table", { name: "Lignes Verre" });
  expect(within(lignes).getByText("Verre progressif droit")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("N° BL fournisseur"), { target: { value: "BL-77" } });
  fireEvent.click(screen.getByRole("checkbox", { name: "Non conforme Verre progressif gauche" }));
  expect(screen.getByRole("button", { name: "Valider" })).toBeDisabled();
  expect(screen.getByText("Le motif est obligatoire pour un article non conforme.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Motif Verre progressif gauche"), { target: { value: "Rayé" } });

  // 80 HT + FODEC 0,800 + TVA 19 % de 80,800 = 96,152 ; le verre refusé ne compte pas.
  const totaux = screen.getByRole("table", { name: "Totaux du bon" });
  expect(within(totaux).getByText(/96,152/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Valider" }));

  expect(await screen.findByText(/Bon de réception T01-R2026-000001 enregistré/)).toBeInTheDocument();
  expect(envois[0]).toMatchObject({
    magasin: "m1",
    fournisseur: "f1",
    numero_bl: "BL-77",
    lignes: [
      { article: "v1", ligne_commande: 11, oeil: "D", quantite: 1, prix_achat_ht: "80", non_conforme: false },
      { article: "v1", ligne_commande: 12, oeil: "G", non_conforme: true, motif: "Rayé" },
    ],
  });
});

test("calcule les totaux comme le serveur : remise, remise exceptionnelle, FODEC et TVA par taux", () => {
  const ligne = (prix: string, quantite: string, remise: string, tva: string): LigneSaisie => ({
    cle: 1,
    article: { id: "a", reference: "", libelle: "", famille: "monture", code_barres: "" },
    ligne_commande: null,
    commande: "",
    oeil: "",
    designation: "",
    quantite,
    prix_achat_ht: prix,
    taux_remise: remise,
    taux_tva: tva,
    non_conforme: false,
    motif: "",
    numero_lot: "",
    date_peremption: "",
    dernier_prix: null,
  });
  const totaux = calculerBon([ligne("100", "2", "10", "19"), ligne("50", "1", "0", "7")], 10, true, 3);
  expect(totaux.totalHt).toBe(250);
  expect(totaux.totalRemise).toBe(20);
  expect(totaux.remiseEx).toBe(23);
  expect(totaux.netHt).toBe(207);
  expect(totaux.totalFodec).toBe(2.07);
  // TVA sur (net × 0,9) × 1,01 : 162 × 1,01 × 19 % et 45 × 1,01 × 7 %.
  expect(totaux.tva.find((t) => t.taux === 19)?.montant).toBe(31.088);
  expect(totaux.tva.find((t) => t.taux === 7)?.montant).toBe(3.182);
});
