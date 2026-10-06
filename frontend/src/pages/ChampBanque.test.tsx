import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";

import { ChampBanque } from "./ChampBanque";

afterEach(() => vi.unstubAllGlobals());

function Fiche() {
  const [banque, setBanque] = useState("");
  return <ChampBanque valeur={banque} changer={setBanque} />;
}

test("retrouve une banque par son sigle et garde son nom", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify([
            { id: 1, code: "08", nom: "BANQUE INTERNATIONALE ARABE DE TUNISIE", sigle: "BIAT", pays: "TN" },
            { id: 2, code: "25", nom: "BANQUE ZITOUNA", sigle: "BZ", pays: "TN" },
          ]),
        ),
      ),
    ),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Fiche />
    </QueryClientProvider>,
  );
  const champ = screen.getByLabelText("Banque");
  fireEvent.change(champ, { target: { value: "biat" } });
  const option = await screen.findByRole("option", { name: "BIAT · BANQUE INTERNATIONALE ARABE DE TUNISIE" });
  expect(screen.getAllByRole("option")).toHaveLength(1);
  fireEvent.click(option);
  expect(champ).toHaveValue("BANQUE INTERNATIONALE ARABE DE TUNISIE");
});
