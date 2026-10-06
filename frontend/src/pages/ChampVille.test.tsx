import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";

import { ChampVille } from "./ChampVille";

afterEach(() => vi.unstubAllGlobals());

function Fiche({ suivre }: { suivre: (ville: string) => void }) {
  const [ville, setVille] = useState("");
  return (
    <ChampVille
      valeur={ville}
      changer={(v) => {
        setVille(v);
        suivre(v);
      }}
    />
  );
}

test("propose les villes de la liste dans l'ordre alphabétique", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify([
            { id: 2, nom: "Ariana", pays: "TN" },
            { id: 1, nom: "Aïn Zaghouan", pays: "TN" },
            { id: 3, nom: "Sfax", pays: "TN" },
          ]),
        ),
      ),
    ),
  );
  const suivre = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Fiche suivre={suivre} />
    </QueryClientProvider>,
  );
  const champ = screen.getByLabelText("Ville");
  fireEvent.change(champ, { target: { value: "a" } });
  const options = await screen.findAllByRole("option");
  expect(options.map((o) => o.textContent)).toEqual(["Aïn Zaghouan", "Ariana", "Sfax"]);
  fireEvent.click(options[1]);
  expect(suivre).toHaveBeenLastCalledWith("Ariana");
  expect(champ).toHaveValue("Ariana");
});
