import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

export function CodesSecours({ codes, onTermine }: { codes: string[]; onTermine: () => void }) {
  return (
    <Card sx={{ maxWidth: 440, mx: "auto" }}>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6" component="h2">
            Codes de secours
          </Typography>
          <Alert severity="warning">
            Conservez ces codes en lieu sûr. Chacun remplace une seule fois le code de
            l'application si vous perdez votre téléphone. Ils ne seront plus affichés.
          </Alert>
          <Typography component="pre" sx={{ fontFamily: "monospace", columns: 2, m: 0 }}>
            {codes.join("\n")}
          </Typography>
          <Button variant="contained" onClick={onTermine}>
            J'ai conservé mes codes
          </Button>
        </Stack>
      </CardContent>
    </Card>
  );
}
