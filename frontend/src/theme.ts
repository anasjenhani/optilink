import { createTheme } from "@mui/material/styles";

// Thème OptiLink unique : toutes les couleurs et tailles passent par ici.
export const theme = createTheme({
  palette: {
    primary: { main: "#1f5fa8" },
    secondary: { main: "#2e8b7a" },
  },
  shape: { borderRadius: 8 },
});
