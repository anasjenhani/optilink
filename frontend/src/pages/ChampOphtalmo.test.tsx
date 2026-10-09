import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";

import { ChampOphtalmo } from "./ChampOphtalmo";

afterEach(() => vi.unstubAllGlobals());

function afficher(changer: (nom: string) => void) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ChampOphtalmo valeur="" changer={changer} />
    </QueryClientProvider>,
  );
  return screen.getByLabelText("Ophtalmologiste");
}

test("on cherche le médecin dans la liste ou on l'ajoute", async () => {
  const appel = vi.fn((_url: string, init?: RequestInit) =>
    Promise.resolve(
      init?.method === "POST"
        ? new Response(JSON.stringify({ id: 2, nom: "Dr Gharbi" }), { status: 201 })
        : new Response(JSON.stringify([{ id: 1, nom: "Dr Ben Salah" }])),
    ),
  );
  vi.stubGlobal("fetch", appel);
  const changer = vi.fn();
  const champ = afficher(changer);

  fireEvent.change(champ, { target: { value: "ben" } });
  fireEvent.click(await screen.findByText("Dr Ben Salah"));
  expect(changer).toHaveBeenLastCalledWith("Dr Ben Salah");

  fireEvent.change(champ, { target: { value: "Dr Gharbi" } });
  fireEvent.click(await screen.findByText("Ajouter « Dr Gharbi » à la liste"));
  await vi.waitFor(() => expect(changer).toHaveBeenLastCalledWith("Dr Gharbi"));
  const ajout = appel.mock.calls.find(([, init]) => init?.method === "POST");
  expect(JSON.parse(String(ajout?.[1]?.body))).toEqual({ nom: "Dr Gharbi" });
});

test("l'ajout d'un médecin déjà dans la liste est refusé", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((_url: string, init?: RequestInit) =>
      Promise.resolve(
        init?.method === "POST"
          ? new Response(JSON.stringify({ nom: ["Dr Ben Salah est déjà dans la liste des ophtalmologistes."] }), {
              status: 400,
            })
          : new Response(JSON.stringify([])),
      ),
    ),
  );
  const changer = vi.fn();
  fireEvent.change(afficher(changer), { target: { value: "ben-salah" } });
  fireEvent.click(await screen.findByText("Ajouter « ben-salah » à la liste"));
  expect(await screen.findByText(/déjà dans la liste/)).toBeInTheDocument();
  expect(changer).not.toHaveBeenCalledWith("ben-salah");
});
