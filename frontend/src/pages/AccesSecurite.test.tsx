import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { AccesSecurite, type DroitsAcces } from "./AccesSecurite";

const TOUS_LES_DROITS: DroitsAcces = {
  voirUtilisateurs: true,
  creerUtilisateur: true,
  modifierUtilisateur: true,
  voirProfils: true,
  creerProfil: true,
  modifierProfil: true,
  supprimerProfil: true,
};
const TUNIS = { id: "m1", code: "T01", nom: "Tunis", societe: "Optique de Tunis", ville: "Tunis", pays: { devise: "TND", decimales: 3 } };
const PROFILS = [
  { id: 1, nom: "Caissier", privileges: ["ventes.add_vente"], utilisateurs: 0 },
  { id: 2, nom: "Vendeur", privileges: ["ventes.add_vente", "ventes.view_vente"], utilisateurs: 1 },
];
const SAMI = {
  id: 7,
  identifiant: "sami",
  prenom: "Sami",
  nom: "Ben Ali",
  email: "",
  actif: true,
  derniere_connexion: null,
  mfa_active: true,
  administrateur_technique: false,
  affectations: [{ id: 3, profil: 2, profil_nom: "Vendeur", portee: "magasin", magasin: "m1", societe: null, perimetre: "T01 Tunis", debut: "2026-10-01", fin: null }],
};
const CATALOGUE = [
  {
    module: "Caisse et ventes",
    privileges: [
      { code: "ventes.view_vente", libelle: "Voir les ventes et les commandes" },
      { code: "ventes.add_vente", libelle: "Encaisser (caisse, acomptes, livraisons)" },
      { code: "ventes.appliquer_remise", libelle: "Accorder une remise" },
    ],
  },
];

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

afterEach(() => vi.unstubAllGlobals());

function afficher(droits = TOUS_LES_DROITS) {
  const envois: { url: string; methode: string; corps: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      const methode = init?.method ?? "GET";
      if (methode !== "GET") {
        envois.push({ url, methode, corps: init?.body ? JSON.parse(init.body as string) : null });
        return url.includes("/profils/") ? json(PROFILS[0]) : json(SAMI, 201);
      }
      if (url === "/api/v1/securite/utilisateurs/") return json([SAMI]);
      if (url === "/api/v1/securite/profils/") return json(PROFILS);
      if (url === "/api/v1/securite/privileges/") return json(CATALOGUE);
      if (url === "/api/v1/magasins/") return json({ results: [TUNIS] });
      return json({ results: [{ id: "s1", code: "SCTE001", raison_sociale: "Optique de Tunis" }] });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <AccesSecurite droits={droits} />
    </QueryClientProvider>,
  );
  return envois;
}

async function choisir(libelle: string, option: string, dans: HTMLElement = document.body) {
  fireEvent.mouseDown(within(dans).getByRole("combobox", { name: libelle }));
  fireEvent.click(await screen.findByRole("option", { name: option }));
}

test("liste les utilisateurs avec leurs profils", async () => {
  afficher();
  expect(await screen.findByText("Sami Ben Ali")).toBeInTheDocument();
  expect(screen.getByText("Vendeur · T01 Tunis")).toBeInTheDocument();
  expect(screen.getByText("Activée")).toBeInTheDocument();
});

test("crée un utilisateur avec un profil sur un magasin", async () => {
  const envois = afficher();
  fireEvent.click(await screen.findByRole("button", { name: "Nouvel utilisateur" }));
  const fiche = await screen.findByRole("dialog");
  fireEvent.change(within(fiche).getByLabelText(/Identifiant/), { target: { value: "leila" } });
  fireEvent.change(within(fiche).getByLabelText(/Mot de passe provisoire/), { target: { value: "Provisoire-2026!" } });
  fireEvent.click(within(fiche).getByRole("button", { name: "Ajouter un profil" }));
  await choisir("Profil", "Caissier", fiche);
  fireEvent.click(within(fiche).getByRole("button", { name: "Enregistrer" }));
  await vi.waitFor(() => expect(envois).toHaveLength(1));
  expect(envois[0]).toEqual({
    url: "/api/v1/securite/utilisateurs/",
    methode: "POST",
    corps: {
      identifiant: "leila",
      prenom: "",
      nom: "",
      email: "",
      mot_de_passe: "Provisoire-2026!",
      affectations: [{ profil: 1, portee: "magasin", magasin: "m1", societe: null, fin: null }],
    },
  });
});

test("donne un privilège à un profil", async () => {
  const envois = afficher();
  fireEvent.click(await screen.findByRole("tab", { name: "Profils et privilèges" }));
  fireEvent.click(await screen.findByRole("button", { name: /Vendeur/ }));
  fireEvent.click(await screen.findByRole("checkbox", { name: "Accorder une remise" }));
  fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  await vi.waitFor(() => expect(envois).toHaveLength(1));
  expect(envois[0].url).toBe("/api/v1/securite/profils/2/");
  expect(new Set((envois[0].corps as { privileges: string[] }).privileges)).toEqual(
    new Set(["ventes.add_vente", "ventes.view_vente", "ventes.appliquer_remise"]),
  );
});

test("sans droit de modification, les privilèges sont en lecture seule", async () => {
  afficher({ ...TOUS_LES_DROITS, voirUtilisateurs: false, modifierProfil: false });
  expect(await screen.findByRole("checkbox", { name: "Encaisser (caisse, acomptes, livraisons)" })).toBeDisabled();
  expect(screen.queryByRole("button", { name: "Enregistrer" })).not.toBeInTheDocument();
});
