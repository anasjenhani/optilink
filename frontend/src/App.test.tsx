import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";

import type { EtatSession } from "./api/auth";
import { App } from "./App";

const ANONYME: EtatSession = { authentifie: false, mfa: null, utilisateur: null };

function session(mfa: EtatSession["mfa"], permissions: string[] = []): EtatSession {
  return {
    authentifie: true,
    mfa,
    utilisateur: { identifiant: "claire", nom_complet: "Claire Martin", permissions },
  };
}

function json(donnees: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(donnees), { status }));
}

/** Simule l'API : chaque route renvoie la réponse fournie. */
function simulerApi(routes: Record<string, () => Promise<Response>>) {
  const appels: { url: string; init?: RequestInit }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      appels.push({ url, init });
      const route = routes[url];
      return route ? route() : json({ statut: "ok", base_de_donnees: "ok", cache: "ok" });
    }),
  );
  return appels;
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("un visiteur voit l'écran de connexion puis la demande de code", async () => {
  document.cookie = "csrftoken=jeton-csrf";
  const appels = simulerApi({
    "/api/v1/auth/session/": () => json(ANONYME),
    "/api/v1/auth/connexion/": () => json(session("a_verifier")),
  });
  afficher();

  fireEvent.change(await screen.findByLabelText(/Identifiant/), { target: { value: "claire" } });
  fireEvent.change(screen.getByLabelText(/Mot de passe/), { target: { value: "secret" } });
  fireEvent.click(screen.getByRole("button", { name: "Se connecter" }));

  expect(await screen.findByText("Double authentification")).toBeInTheDocument();
  const connexion = appels.find((a) => a.url === "/api/v1/auth/connexion/")!;
  expect(connexion.init?.headers).toMatchObject({ "X-CSRFToken": "jeton-csrf" });
  expect(JSON.parse(connexion.init?.body as string)).toEqual({
    identifiant: "claire",
    mot_de_passe: "secret",
  });
});

test("affiche l'erreur renvoyée par l'API", async () => {
  simulerApi({
    "/api/v1/auth/session/": () => json(ANONYME),
    "/api/v1/auth/connexion/": () => json({ detail: "Identifiant ou mot de passe incorrect." }, 400),
  });
  afficher();

  fireEvent.click(await screen.findByRole("button", { name: "Se connecter" }));
  expect(await screen.findByText("Identifiant ou mot de passe incorrect.")).toBeInTheDocument();
});

test("l'activation affiche les codes de secours avant d'ouvrir l'application", async () => {
  let etat = session("a_activer");
  simulerApi({
    "/api/v1/auth/session/": () => json(etat),
    "/api/v1/auth/mfa/activation/": () => json({ uri: "otpauth://x", cle: "ABCD", qr_svg: "<svg/>" }),
    "/api/v1/auth/mfa/activation/confirmation/": () => {
      etat = session("verifiee");
      return json({ codes_secours: ["11111111", "22222222"], session: etat });
    },
  });
  afficher();

  expect(await screen.findByAltText("QR code d'activation")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText(/Code/), { target: { value: "123456" } });
  fireEvent.click(screen.getByRole("button", { name: "Activer" }));

  expect(await screen.findByText(/11111111/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "J'ai conservé mes codes" }));
  expect(await screen.findByText("État de la plateforme")).toBeInTheDocument();
});

test("les magasins ne s'affichent qu'avec la permission", async () => {
  simulerApi({
    "/api/v1/auth/session/": () => json(session("verifiee", ["reseau.view_magasin"])),
    "/api/v1/magasins/": () =>
      json({ results: [{ id: "1", code: "M01", nom: "Lille", societe: "Optique du Nord", ville: "Lille" }] }),
  });
  afficher();

  expect(await screen.findByText("Claire Martin")).toBeInTheDocument();
  expect(await screen.findByText("M01 · Nord")).toBeInTheDocument();
});

test("sans permission, pas de liste de magasins", async () => {
  simulerApi({ "/api/v1/auth/session/": () => json(session("verifiee")) });
  afficher();

  expect(await screen.findByText("État de la plateforme")).toBeInTheDocument();
  expect(screen.queryByText("Mes magasins")).not.toBeInTheDocument();
});
