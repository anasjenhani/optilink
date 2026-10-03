import Alert from "@mui/material/Alert";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemText from "@mui/material/ListItemText";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";

import { listerMagasins } from "../api/magasins";

export function Magasins() {
  const magasins = useQuery({ queryKey: ["magasins"], queryFn: listerMagasins });

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Mes magasins
        </Typography>
        {magasins.isError && <Alert severity="error">{magasins.error.message}</Alert>}
        <List dense>
          {magasins.data?.map((magasin) => (
            <ListItem key={magasin.id} disableGutters>
              <ListItemText primary={magasin.nom} secondary={`${magasin.code} · ${magasin.societe}`} />
            </ListItem>
          ))}
        </List>
      </CardContent>
    </Card>
  );
}
