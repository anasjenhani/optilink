import AccountBalance from "@mui/icons-material/AccountBalance";
import AddBox from "@mui/icons-material/AddBox";
import AdminPanelSettings from "@mui/icons-material/AdminPanelSettings";
import ArrowDownward from "@mui/icons-material/ArrowDownward";
import ArrowUpward from "@mui/icons-material/ArrowUpward";
import AssignmentReturn from "@mui/icons-material/AssignmentReturn";
import Badge from "@mui/icons-material/Badge";
import BeachAccess from "@mui/icons-material/BeachAccess";
import Block from "@mui/icons-material/Block";
import Build from "@mui/icons-material/Build";
import CalendarMonth from "@mui/icons-material/CalendarMonth";
import CheckCircle from "@mui/icons-material/CheckCircle";
import CompareArrows from "@mui/icons-material/CompareArrows";
import CreditCard from "@mui/icons-material/CreditCard";
import DeleteSweep from "@mui/icons-material/DeleteSweep";
import Description from "@mui/icons-material/Description";
import EditNote from "@mui/icons-material/EditNote";
import EventRepeat from "@mui/icons-material/EventRepeat";
import Factory from "@mui/icons-material/Factory";
import FactCheck from "@mui/icons-material/FactCheck";
import FilterAlt from "@mui/icons-material/FilterAlt";
import FindInPage from "@mui/icons-material/FindInPage";
import Groups from "@mui/icons-material/Groups";
import History from "@mui/icons-material/History";
import Inventory from "@mui/icons-material/Inventory";
import Inventory2 from "@mui/icons-material/Inventory2";
import ListAlt from "@mui/icons-material/ListAlt";
import LocalShipping from "@mui/icons-material/LocalShipping";
import Lock from "@mui/icons-material/Lock";
import LockOpen from "@mui/icons-material/LockOpen";
import MonitorHeart from "@mui/icons-material/MonitorHeart";
import MoveDown from "@mui/icons-material/MoveDown";
import MoveToInbox from "@mui/icons-material/MoveToInbox";
import Payments from "@mui/icons-material/Payments";
import People from "@mui/icons-material/People";
import PersonAddAlt from "@mui/icons-material/PersonAddAlt";
import PersonSearch from "@mui/icons-material/PersonSearch";
import PointOfSale from "@mui/icons-material/PointOfSale";
import QrCode2 from "@mui/icons-material/QrCode2";
import QrCodeScanner from "@mui/icons-material/QrCodeScanner";
import ReceiptLong from "@mui/icons-material/ReceiptLong";
import RemoveRedEye from "@mui/icons-material/RemoveRedEye";
import ReportProblem from "@mui/icons-material/ReportProblem";
import RequestQuote from "@mui/icons-material/RequestQuote";
import Savings from "@mui/icons-material/Savings";
import Sell from "@mui/icons-material/Sell";
import Store from "@mui/icons-material/Store";
import SwapHoriz from "@mui/icons-material/SwapHoriz";
import Sync from "@mui/icons-material/Sync";
import TableChart from "@mui/icons-material/TableChart";
import Today from "@mui/icons-material/Today";
import TrackChanges from "@mui/icons-material/TrackChanges";
import Undo from "@mui/icons-material/Undo";
import UploadFile from "@mui/icons-material/UploadFile";
import Visibility from "@mui/icons-material/Visibility";
import Widgets from "@mui/icons-material/Widgets";
import type { SvgIconComponent } from "@mui/icons-material";
import type { ReactNode } from "react";

import { peut, type EtatSession } from "../api/auth";
import { AccesSecurite } from "../pages/AccesSecurite";
import { Accueil } from "../pages/Accueil";
import { Avoirs } from "../pages/Avoirs";
import { BonReception } from "../pages/BonReception";
import { BonRetour, ListeBonsRetour } from "../pages/BonRetour";
import { Caisse } from "../pages/Caisse";
import { Catalogue } from "../pages/Catalogue";
import { Clients } from "../pages/Clients";
import { CassesVerres } from "../pages/CassesVerres";
import { Commandes } from "../pages/Commandes";
import { Corbeille } from "../pages/Corbeille";
import { CreditClients } from "../pages/CreditClients";
import { BordereauxPec } from "../pages/BordereauxPec";
import { PrisesEnCharge } from "../pages/PrisesEnCharge";
import { Sav } from "../pages/Sav";
import { Recus } from "../pages/Recus";
import { ReglementsFournisseurs } from "../pages/ReglementsFournisseurs";
import { ResteVendeur } from "../pages/ResteVendeur";
import { Devis } from "../pages/Devis";
import { Factures } from "../pages/Factures";
import { Fournisseurs } from "../pages/Fournisseurs";
import { Imports } from "../pages/Imports";
import { Journee } from "../pages/Journee";
import { FactureAchat } from "../pages/FactureAchat";
import { ListeFacturesAchat } from "../pages/ListeFacturesAchat";
import { ListeReceptions } from "../pages/ListeReceptions";
import { Magasins } from "../pages/Magasins";
import { MouvementsStock } from "../pages/MouvementsStock";
import { RessourcesHumaines } from "../pages/RessourcesHumaines";
import { Suivi } from "../pages/Suivi";
import { ListeTransferts, TransfertStock } from "../pages/Transferts";
import { Inventaire } from "../pages/Inventaire";
import { ConsulterVisite, HistoriqueVisites, Visites } from "../pages/Visites";
import { Tresorerie } from "../pages/Tresorerie";
import { VenteComptoir } from "../pages/VenteComptoir";
import { Verres } from "../pages/Verres";

/** Un bouton de la grille d'un module : il ouvre son écran, ou il est grisé « à venir ». */
export type Tuile = {
  id: string;
  libelle: string;
  icone: SvgIconComponent;
  couleur: string;
  ecran?: () => ReactNode;
  aVenir?: boolean;
  /** Sous-onglet du module (Administration : RH, Réseau, Sécurité… comme dans /admin/). */
  categorie?: string;
};

export type Module = { id: string; libelle: string; tuiles: Tuile[] };

/** Boutons fixes sous les onglets : les écrans du quotidien, accessibles depuis partout. */
export const RACCOURCIS: { module: string; tuile: string; libelle: string }[] = [
  { module: "vente", tuile: "journee", libelle: "Journée" },
  { module: "vente", tuile: "nouvelle-visite", libelle: "Nouvelle visite" },
  { module: "vente", tuile: "suivi-visite", libelle: "Suivi" },
  { module: "vente", tuile: "recherche-verre", libelle: "Recherche verre" },
  { module: "vente", tuile: "recherche-monture", libelle: "Recherche monture" },
  { module: "vente", tuile: "recherche-lentille", libelle: "Recherche lentille" },
  { module: "vente", tuile: "clients", libelle: "Clients" },
];

const COULEURS = {
  violet: "#6a3fb5",
  bleu: "#2f7fc1",
  turquoise: "#1aa88f",
  gris: "#6b7280",
  jaune: "#d4a017",
  orange: "#d9822b",
  rouge: "#d64545",
  vert: "#3f9b3f",
  brun: "#9a6b3a",
};

const aVenir = (id: string, libelle: string, icone: SvgIconComponent, couleur: string): Tuile => ({
  id,
  libelle,
  icone,
  couleur,
  aVenir: true,
});

/**
 * Les modules de la barre d'onglets, sur le modèle de l'ancien logiciel des magasins.
 * Chaque bouton ouvre l'écran correspondant si l'utilisateur en a le droit ; les fonctions
 * pas encore construites restent visibles et grisées pour montrer la suite.
 */
export function modulesPour(session: EtatSession): Module[] {
  const a = (privilege: string) => peut(session, privilege);
  const si = (condition: boolean, ecran: () => ReactNode) => (condition ? ecran : undefined);

  const vendre = a("ventes.add_vente");
  const voirVentes = a("ventes.view_vente");
  const voirClients = a("crm.view_client");
  const voirCatalogue = a("stock.view_article");
  const declarerCasse = a("achats.add_casseverre");
  const droitsTresorerie = {
    cloturer: a("tresorerie.add_cloturecaisse"),
    depenses: a("tresorerie.add_depensecaisse"),
    verifier: a("tresorerie.valider_cloturecaisse"),
    voirClotures: a("tresorerie.view_cloturecaisse"),
    versements: a("tresorerie.add_operationtresorerie"),
    banque: a("tresorerie.view_operationtresorerie"),
    rapprocher: a("tresorerie.rapprocher_operationtresorerie"),
    gererComptes: a("tresorerie.add_comptetresorerie"),
    modifierComptes: a("tresorerie.change_comptetresorerie"),
  };
  const tresorerie = (onglet: keyof typeof ONGLETS_TRESORERIE) =>
    si(droitsTresorerie[onglet], () => (
      <Tresorerie droits={droitsTresorerie} ongletInitial={ONGLETS_TRESORERIE[onglet]} />
    ));
  const droitsCredit = { regler: a("ventes.add_vente"), gerer: a("ventes.gerer_impayes") };
  const droitsReglementsFournisseurs = {
    regler: a("achats.add_reglementfournisseur"),
    debiter: a("achats.change_reglementfournisseur"),
    annuler: a("achats.delete_reglementfournisseur"),
  };
  const droitsRh = {
    voirEmployes: a("rh.view_employe"),
    creerEmploye: a("rh.add_employe"),
    modifierEmploye: a("rh.change_employe"),
    voirPresence: a("rh.view_pointage"),
    pointer: a("rh.add_pointage"),
    voirConges: a("rh.view_demandeconge"),
    saisirConge: a("rh.add_demandeconge") && a("rh.view_employe"),
    deciderConge: a("rh.decider_demandeconge"),
    annulerConge: a("rh.add_demandeconge"),
    voirAcomptes: a("rh.view_acompte"),
    demanderAcompte: a("rh.add_acompte"),
    deciderAcompte: a("rh.decider_acompte"),
    voirPrimes: a("rh.view_prime"),
    proposerPrime: a("rh.add_prime"),
    validerPrime: a("rh.valider_prime"),
  };
  const clients = si(voirClients, () => (
    <Clients
      droits={{
        creerClient: a("crm.add_client"),
        modifierClient: a("crm.change_client"),
        voirOrdonnances: a("optique.view_prescription"),
        saisirOrdonnance: a("optique.add_prescription"),
      }}
    />
  ));
  const stock = (famille: "monture" | "verre" | "lentille" | "divers") =>
    si(voirCatalogue, () => <Catalogue familleInitiale={famille} importer={imports.catalogue} fiche={droitsFiche} />);
  const droitsFiche = {
    creer: a("stock.add_article") && a("stock.add_prixarticle"),
    modifier: a("stock.change_article") && a("stock.add_prixarticle") && a("stock.change_prixarticle"),
  };
  const imports = {
    catalogue: a("stock.add_article") && a("stock.change_prixarticle"),
    stock: a("stock.add_mouvementstock"),
    clients: a("crm.add_client") && a("crm.change_client"),
  };

  const comptoir = si(vendre, () =>
    voirClients ? (
      <VenteComptoir
        creerClient={a("crm.add_client")}
        droits={{
          remise: a("ventes.appliquer_remise"),
          voirOrdonnances: a("optique.view_prescription"),
          saisirOrdonnance: a("optique.add_prescription"),
        }}
      />
    ) : (
      <Caisse />
    ),
  );

  const modules: Module[] = [
    {
      id: "vente",
      libelle: "Vente",
      tuiles: [
        {
          id: "recherche-verre",
          libelle: "Recherche Verre",
          icone: Visibility,
          couleur: COULEURS.violet,
          ecran: stock("verre"),
        },
        {
          id: "recherche-monture",
          libelle: "Recherche Monture",
          icone: Visibility,
          couleur: COULEURS.brun,
          ecran: stock("monture"),
        },
        {
          id: "recherche-lentille",
          libelle: "Recherche Lentille",
          icone: RemoveRedEye,
          couleur: COULEURS.bleu,
          ecran: stock("lentille"),
        },
        {
          id: "comptoir",
          libelle: "Vente au Comptoir",
          icone: PointOfSale,
          couleur: COULEURS.turquoise,
          ecran: comptoir,
        },
        {
          id: "devis",
          libelle: "Devis Vente",
          icone: RequestQuote,
          couleur: COULEURS.gris,
          ecran: si(a("ventes.add_devis") && voirClients, () => (
            <Devis
              droits={{
                remise: a("ventes.appliquer_remise"),
                voirOrdonnances: a("optique.view_prescription"),
                changerStatut: a("ventes.change_devis"),
                encaisser: vendre,
                consulter: a("ventes.view_devis"),
              }}
            />
          )),
        },
        {
          id: "clients",
          libelle: "Clients et ordonnances",
          icone: People,
          couleur: COULEURS.turquoise,
          ecran: clients,
        },
        {
          id: "import-clients",
          libelle: "Import Clients",
          icone: UploadFile,
          couleur: COULEURS.bleu,
          ecran: si(imports.clients, () => <Imports types={["clients"]} />),
        },
        {
          id: "commandes",
          libelle: "Commandes en cours",
          icone: LocalShipping,
          couleur: COULEURS.bleu,
          ecran: si(vendre, () => <Commandes saisirPec={a("ventes.add_priseencharge")} />),
        },
        {
          id: "nouvelle-visite",
          libelle: "Nouvelle Visite",
          icone: PersonAddAlt,
          couleur: COULEURS.turquoise,
          ecran: comptoir,
        },
        {
          id: "journee",
          libelle: "Journée de Vente",
          icone: Today,
          couleur: COULEURS.vert,
          ecran: si(voirVentes, () => <Journee />),
        },
        {
          id: "liste-visites",
          libelle: "Liste Visites",
          icone: ListAlt,
          couleur: COULEURS.jaune,
          ecran: si(voirVentes, () => <Visites casse={declarerCasse} />),
        },
        {
          id: "visites-filtre-facture",
          libelle: "Visites Filtre Facture",
          icone: FilterAlt,
          couleur: COULEURS.jaune,
          ecran: si(voirVentes, () => <Visites casse={declarerCasse} factureeInitiale="false" />),
        },
        {
          id: "suivi-visite",
          libelle: "Suivi Visite",
          icone: TrackChanges,
          couleur: COULEURS.orange,
          ecran: si(voirVentes, () => <Suivi modifier={vendre} />),
        },
        {
          id: "consulter-visite",
          libelle: "Consulter Visite",
          icone: FindInPage,
          couleur: COULEURS.rouge,
          ecran: si(voirVentes, () => <ConsulterVisite casse={declarerCasse} />),
        },
        aVenir("lunettes-vendues", "Lunettes Vendues", Sell, COULEURS.turquoise),
        {
          id: "liste-recus",
          libelle: "Liste Reçus",
          icone: ReceiptLong,
          couleur: COULEURS.jaune,
          ecran: si(voirVentes, () => <Recus />),
        },
        aVenir("creation-produit", "Demande Création Produit", AddBox, COULEURS.bleu),
        aVenir("prospect", "Prospect Client", PersonSearch, COULEURS.rouge),
        aVenir("code-barre", "Code à barres", QrCode2, COULEURS.bleu),
        {
          id: "historique-visites",
          libelle: "Historique Visites",
          icone: History,
          couleur: COULEURS.rouge,
          ecran: si(voirVentes && voirClients, () => <HistoriqueVisites casse={declarerCasse} />),
        },
        {
          id: "casse-verre",
          libelle: "Casse Verre",
          icone: Build,
          couleur: COULEURS.vert,
          ecran: si(a("achats.view_casseverre"), () => <CassesVerres declarer={declarerCasse} />),
        },
        aVenir("code-barre-marque", "Code à barres Marque", QrCodeScanner, COULEURS.bleu),
        aVenir("visites-stock", "Visites de Stock", Inventory, COULEURS.brun),
        {
          id: "reste-vendeur",
          libelle: "Reste par Vendeur",
          icone: Payments,
          couleur: COULEURS.vert,
          ecran: si(voirVentes, () => <ResteVendeur />),
        },
      ],
    },
    {
      id: "stock",
      libelle: "Stock",
      tuiles: [
        {
          id: "stock-monture",
          libelle: "Stock Monture",
          icone: Inventory2,
          couleur: COULEURS.jaune,
          ecran: stock("monture"),
        },
        {
          id: "stock-lentille",
          libelle: "Stock Lentille",
          icone: Inventory2,
          couleur: COULEURS.jaune,
          ecran: stock("lentille"),
        },
        {
          id: "stock-article",
          libelle: "Stock Article",
          icone: Inventory2,
          couleur: COULEURS.jaune,
          ecran: stock("divers"),
        },
        {
          id: "stock-verre",
          libelle: "Stock Verre",
          icone: Inventory2,
          couleur: COULEURS.jaune,
          ecran: stock("verre"),
        },
        {
          id: "bon-entree",
          libelle: "Bon Entrée",
          icone: ArrowDownward,
          couleur: COULEURS.rouge,
          ecran: si(imports.stock, () => <Imports types={["stock"]} />),
        },
        {
          id: "import-catalogue",
          libelle: "Import Catalogue",
          icone: UploadFile,
          couleur: COULEURS.bleu,
          ecran: si(imports.catalogue, () => <Imports types={["catalogue"]} />),
        },
        {
          id: "commande-verres",
          libelle: "Commande Verres Fournisseur",
          icone: LocalShipping,
          couleur: COULEURS.violet,
          ecran: si(a("achats.add_commandefournisseur"), () => <Verres />),
        },
        {
          id: "bon-reception",
          libelle: "Bon de Réception",
          icone: MoveToInbox,
          couleur: COULEURS.vert,
          ecran: si(a("achats.add_bonreception") && a("achats.view_fournisseur"), () => (
            <BonReception droitsFournisseurs={{ creer: a("achats.add_fournisseur"), modifier: false }} />
          )),
        },
        {
          id: "liste-receptions",
          libelle: "Liste des Bons de Réception",
          icone: ListAlt,
          couleur: COULEURS.brun,
          ecran: si(a("achats.view_bonreception"), () => <ListeReceptions importer={a("achats.add_bonreception")} />),
        },
        {
          id: "facture-achat",
          libelle: "Facture Achat",
          icone: RequestQuote,
          couleur: COULEURS.violet,
          ecran: si(a("achats.add_factureachat") && a("achats.view_fournisseur"), () => <FactureAchat />),
        },
        {
          id: "liste-factures-achat",
          libelle: "Liste des Factures Achat",
          icone: ReceiptLong,
          couleur: COULEURS.brun,
          ecran: si(a("achats.view_factureachat"), () => <ListeFacturesAchat />),
        },
        {
          id: "bon-retour",
          libelle: "Bon Retour Fournisseur",
          icone: AssignmentReturn,
          couleur: COULEURS.rouge,
          ecran: si(a("achats.add_bonretour") && a("achats.view_fournisseur"), () => <BonRetour />),
        },
        {
          id: "liste-bons-retour",
          libelle: "Liste des Bons Retour",
          icone: ListAlt,
          couleur: COULEURS.brun,
          ecran: si(a("achats.view_bonretour"), () => <ListeBonsRetour />),
        },
        {
          id: "bon-transfert",
          libelle: "Bon Transfert",
          icone: SwapHoriz,
          couleur: COULEURS.bleu,
          ecran: si(a("stock.add_transfertstock"), () => <TransfertStock />),
        },
        {
          id: "liste-transferts",
          libelle: "Liste des Transferts",
          icone: CompareArrows,
          couleur: COULEURS.bleu,
          ecran: si(a("stock.view_transfertstock"), () => (
            <ListeTransferts recevoir={a("stock.change_transfertstock")} annuler={a("stock.add_transfertstock")} />
          )),
        },
        {
          id: "fournisseurs",
          libelle: "Fournisseurs",
          icone: Factory,
          couleur: COULEURS.bleu,
          ecran: si(a("achats.view_fournisseur"), () => (
            <Fournisseurs droits={{ creer: a("achats.add_fournisseur"), modifier: a("achats.change_fournisseur") }} />
          )),
        },
        {
          id: "inventaire",
          libelle: "Inventaire",
          icone: Sync,
          couleur: COULEURS.bleu,
          ecran: si(a("stock.view_inventaire"), () => (
            <Inventaire
              droits={{
                ouvrir: a("stock.add_inventaire"),
                compter: a("stock.change_inventaire"),
                valider: a("stock.valider_inventaire"),
              }}
            />
          )),
        },
        aVenir("stock-date", "Stock à la Date", CalendarMonth, COULEURS.vert),
        aVenir("config-stock", "Config Stock", Widgets, COULEURS.brun),
        aVenir("stock-depense", "Stock Article Dépense", Inventory2, COULEURS.jaune),
        {
          id: "mouvements",
          libelle: "Mouvements de Stock",
          icone: TableChart,
          couleur: COULEURS.brun,
          ecran: si(a("stock.view_mouvementstock"), () => <MouvementsStock />),
        },
        aVenir("stock-total", "Stock Total", Widgets, COULEURS.orange),
        aVenir("bon-sortie", "Bon Sortie", ArrowUpward, COULEURS.vert),
        aVenir("demande-transfert", "Demande Transfert", CompareArrows, COULEURS.bleu),
        aVenir("demande-alimentation", "Demande Alimentation", MoveDown, COULEURS.bleu),
        aVenir("bon-sortie-casse", "Bon Sortie Casse", ArrowUpward, COULEURS.vert),
        aVenir("reassort", "Réassort", EventRepeat, COULEURS.orange),
        aVenir("comparaison", "Comparaison", CompareArrows, COULEURS.gris),
      ],
    },
    {
      id: "reglement",
      libelle: "Règlement",
      tuiles: [
        {
          id: "reglement",
          libelle: "Règlement",
          icone: Payments,
          couleur: COULEURS.vert,
          ecran: si(vendre, () => <Commandes saisirPec={a("ventes.add_priseencharge")} />),
        },
        {
          id: "remboursement",
          libelle: "Remboursement Client",
          icone: Undo,
          couleur: COULEURS.vert,
          ecran: si(a("ventes.add_avoir") || a("ventes.view_avoir"), () => (
            <Avoirs emettre={a("ventes.add_avoir")} consulter={a("ventes.view_avoir")} />
          )),
        },
        {
          id: "avance-personnel",
          libelle: "Avance Personnel",
          icone: Groups,
          couleur: COULEURS.bleu,
          ecran: si(droitsRh.voirAcomptes, () => <RessourcesHumaines droits={droitsRh} ongletInitial="acomptes" />),
        },
        {
          id: "vente-credit",
          libelle: "Liste Vente à Crédit",
          icone: ListAlt,
          couleur: COULEURS.brun,
          ecran: si(a("ventes.view_vente"), () => <CreditClients droits={droitsCredit} ongletInitial="ventes" />),
        },
        {
          id: "liste-reglements",
          libelle: "Liste Règlements",
          icone: ReceiptLong,
          couleur: COULEURS.gris,
          ecran: si(voirVentes, () => <Recus />),
        },
        {
          id: "changement-cheques",
          libelle: "Changement Chèques",
          icone: SwapHoriz,
          couleur: COULEURS.brun,
          ecran: si(a("ventes.gerer_impayes"), () => <CreditClients droits={droitsCredit} ongletInitial="cheques" />),
        },
        {
          id: "prises-en-charge",
          libelle: "Prises en Charge (CNAM)",
          icone: Description,
          couleur: COULEURS.orange,
          ecran: si(a("ventes.view_priseencharge"), () => (
            <PrisesEnCharge modifier={a("ventes.change_priseencharge")} />
          )),
        },
        {
          id: "bordereaux-pec",
          libelle: "Bordereaux CNAM / Conventions",
          icone: FactCheck,
          couleur: COULEURS.orange,
          ecran: si(a("ventes.view_bordereaupec"), () => (
            <BordereauxPec preparer={a("ventes.add_bordereaupec")} regler={a("ventes.change_bordereaupec")} />
          )),
        },
        {
          id: "reglement-credit",
          libelle: "Règlement Crédit",
          icone: CreditCard,
          couleur: COULEURS.brun,
          ecran: si(a("ventes.add_vente"), () => <CreditClients droits={droitsCredit} ongletInitial="ventes" />),
        },
        aVenir("transfert-solde", "Transfert Solde", CompareArrows, COULEURS.gris),
        {
          id: "impaye",
          libelle: "Impayé Client",
          icone: ReportProblem,
          couleur: COULEURS.rouge,
          ecran: si(a("ventes.view_vente"), () => <CreditClients droits={droitsCredit} ongletInitial="impayes" />),
        },
        {
          id: "liste-noire",
          libelle: "Liste Noire",
          icone: Block,
          couleur: COULEURS.rouge,
          ecran: si(a("ventes.gerer_impayes"), () => (
            <CreditClients droits={droitsCredit} ongletInitial="liste-noire" />
          )),
        },
      ],
    },
    {
      id: "reglement-fournisseur",
      libelle: "Règlement Fournisseur",
      tuiles: [
        {
          id: "nouveau-reglement-fournisseur",
          libelle: "Règlement Fournisseur",
          icone: Payments,
          couleur: COULEURS.vert,
          ecran: si(a("achats.add_reglementfournisseur"), () => (
            <ReglementsFournisseurs droits={droitsReglementsFournisseurs} />
          )),
        },
        {
          id: "liste-reglements-fournisseurs",
          libelle: "Liste Règlements Fournisseurs",
          icone: ReceiptLong,
          couleur: COULEURS.gris,
          ecran: si(a("achats.view_reglementfournisseur"), () => (
            <ReglementsFournisseurs droits={droitsReglementsFournisseurs} ongletInitial="liste" />
          )),
        },
        {
          id: "echeancier-fournisseurs",
          libelle: "Échéancier Fournisseurs",
          icone: CalendarMonth,
          couleur: COULEURS.orange,
          ecran: si(a("achats.view_reglementfournisseur"), () => (
            <ReglementsFournisseurs droits={droitsReglementsFournisseurs} ongletInitial="echeancier" />
          )),
        },
      ],
    },
    {
      id: "caisse",
      libelle: "Caisse",
      tuiles: [
        {
          id: "session-en-cours",
          libelle: "Session en Cours",
          icone: LockOpen,
          couleur: COULEURS.jaune,
          ecran: tresorerie("cloturer"),
        },
        {
          id: "sessions-cloturees",
          libelle: "Sessions Clôturées",
          icone: Lock,
          couleur: COULEURS.jaune,
          ecran: tresorerie("voirClotures"),
        },
        {
          id: "validation",
          libelle: "Validation Clôtures",
          icone: CheckCircle,
          couleur: COULEURS.vert,
          ecran: tresorerie("verifier"),
        },
        {
          id: "operations-diverses",
          libelle: "Opérations Diverses",
          icone: Payments,
          couleur: COULEURS.orange,
          ecran: tresorerie("depenses"),
        },
        {
          id: "versement",
          libelle: "Versement Espèces",
          icone: Savings,
          couleur: COULEURS.vert,
          ecran: tresorerie("versements"),
        },
        {
          id: "bordereau",
          libelle: "Bordereau de Versement",
          icone: EditNote,
          couleur: COULEURS.gris,
          ecran: tresorerie("versements"),
        },
        {
          id: "coffre",
          libelle: "Coffre et Banque",
          icone: AccountBalance,
          couleur: COULEURS.brun,
          ecran: tresorerie("banque"),
        },
        {
          id: "echeancier",
          libelle: "Échéancier Client",
          icone: CalendarMonth,
          couleur: COULEURS.vert,
          ecran: si(a("ventes.view_vente"), () => <CreditClients droits={droitsCredit} ongletInitial="portefeuille" />),
        },
        aVenir("export-reglements", "Exportation Règlements", UploadFile, COULEURS.gris),
        aVenir("transfert-reglements", "Transfert Règlements Clients", SwapHoriz, COULEURS.vert),
        aVenir("report-magasin", "Mise à jour Report Magasin", Store, COULEURS.brun),
      ],
    },
    {
      id: "sav",
      libelle: "SAV",
      tuiles: [
        {
          id: "dossiers-sav",
          libelle: "Création / Suivi SAV",
          icone: Build,
          couleur: COULEURS.bleu,
          ecran: si(a("ventes.view_dossiersav"), () => (
            <Sav creer={a("ventes.add_dossiersav")} modifier={a("ventes.change_dossiersav")} />
          )),
        },
        {
          id: "sav-en-retard",
          libelle: "SAV en retard",
          icone: ReportProblem,
          couleur: COULEURS.rouge,
          ecran: si(a("ventes.view_dossiersav"), () => (
            <Sav creer={false} modifier={a("ventes.change_dossiersav")} filtreInitial="retard" />
          )),
        },
        {
          id: "cloture-sav",
          libelle: "Clôture SAV (prêts à rendre)",
          icone: Lock,
          couleur: COULEURS.vert,
          ecran: si(a("ventes.view_dossiersav"), () => (
            <Sav creer={false} modifier={a("ventes.change_dossiersav")} filtreInitial="pret" />
          )),
        },
        aVenir("article-vendu", "Article Vendu", Sell, COULEURS.gris),
      ],
    },
    {
      id: "facture",
      libelle: "Facture",
      tuiles: [
        {
          id: "facture",
          libelle: "Facture",
          icone: Description,
          couleur: COULEURS.violet,
          ecran: si(a("ventes.add_facture") || a("ventes.view_facture"), () => (
            <Factures generer={a("ventes.add_facture")} consulter={a("ventes.view_facture")} />
          )),
        },
        {
          id: "avoir",
          libelle: "Avoir",
          icone: Undo,
          couleur: COULEURS.rouge,
          ecran: si(a("ventes.add_avoir") || a("ventes.view_avoir"), () => (
            <Avoirs emettre={a("ventes.add_avoir")} consulter={a("ventes.view_avoir")} />
          )),
        },
        aVenir("ca-previsionnel", "CA Prévisionnel", TableChart, COULEURS.bleu),
        aVenir("cloture-mois", "Clôture Mois", Lock, COULEURS.brun),
        aVenir("facturation-vc", "Facturation Vente Comptoir", FactCheck, COULEURS.vert),
        aVenir("preparation-facturation", "Préparation Facturation", EditNote, COULEURS.violet),
        aVenir("facturation-visite", "Facturation Visite", FactCheck, COULEURS.violet),
        aVenir("avoir-financier", "Avoir Financier", Undo, COULEURS.rouge),
      ],
    },
    {
      id: "administration",
      libelle: "Administration",
      tuiles: [
        {
          id: "demande-conge",
          categorie: "Ressources humaines",
          libelle: "Demande de Congé",
          icone: BeachAccess,
          couleur: COULEURS.turquoise,
          ecran: () => <RessourcesHumaines droits={droitsRh} ongletInitial="moi" />,
        },
        {
          id: "demande-acompte",
          categorie: "Ressources humaines",
          libelle: "Demande d'Acompte",
          icone: Savings,
          couleur: COULEURS.vert,
          ecran: () => <RessourcesHumaines droits={droitsRh} ongletInitial="mes-acomptes" />,
        },
        {
          ...aVenir("demande-attestation", "Demande d'Attestation", Description, COULEURS.violet),
          categorie: "Ressources humaines",
        },
        {
          ...aVenir("demande-pret", "Demande de Prêt", AccountBalance, COULEURS.brun),
          categorie: "Ressources humaines",
        },
        { ...aVenir("fiche-paie", "Fiche de Paie", ReceiptLong, COULEURS.bleu), categorie: "Ressources humaines" },
        {
          id: "rh",
          categorie: "Ressources humaines",
          libelle: "Ressources Humaines",
          icone: Badge,
          couleur: COULEURS.bleu,
          ecran: () => <RessourcesHumaines droits={droitsRh} />,
        },
        {
          id: "magasins",
          categorie: "Réseau",
          libelle: "Magasins",
          icone: Store,
          couleur: COULEURS.brun,
          ecran: si(a("reseau.view_magasin"), () => <Magasins />),
        },
        {
          id: "acces",
          categorie: "Sécurité",
          libelle: "Accès et Sécurité",
          icone: AdminPanelSettings,
          couleur: COULEURS.rouge,
          ecran: si(a("securite.view_utilisateur") || a("auth.view_group"), () => (
            <AccesSecurite
              droits={{
                voirUtilisateurs: a("securite.view_utilisateur"),
                creerUtilisateur: a("securite.add_utilisateur") && a("securite.add_affectation"),
                modifierUtilisateur: a("securite.change_utilisateur") && a("securite.change_affectation"),
                voirProfils: a("auth.view_group"),
                creerProfil: a("auth.add_group"),
                modifierProfil: a("auth.change_group"),
                supprimerProfil: a("auth.delete_group"),
              }}
            />
          )),
        },
        {
          id: "corbeille",
          categorie: "Sécurité",
          libelle: "Corbeille",
          icone: DeleteSweep,
          couleur: COULEURS.gris,
          ecran: si(a("securite.view_elementcorbeille"), () => (
            <Corbeille
              droits={{
                restaurer: a("securite.restaurer_elementcorbeille"),
                vider: a("securite.delete_elementcorbeille"),
              }}
            />
          )),
        },
        {
          id: "plateforme",
          categorie: "Plateforme",
          libelle: "État de la Plateforme",
          icone: MonitorHeart,
          couleur: COULEURS.vert,
          ecran: () => <Accueil />,
        },
      ],
    },
  ];
  // Un bouton dont l'utilisateur n'a pas le droit disparaît ; seules les fonctions à venir restent grisées.
  return modules.map((m) => ({ ...m, tuiles: m.tuiles.filter((t) => t.aVenir || t.ecran) }));
}

const ONGLETS_TRESORERIE = {
  cloturer: "cloture",
  depenses: "depenses",
  verifier: "verifier",
  voirClotures: "historique",
  versements: "versements",
  banque: "banque",
  rapprocher: "banque",
  gererComptes: "banque",
};
