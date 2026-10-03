import AccountBalance from "@mui/icons-material/AccountBalance";
import AddBox from "@mui/icons-material/AddBox";
import AdminPanelSettings from "@mui/icons-material/AdminPanelSettings";
import ArrowDownward from "@mui/icons-material/ArrowDownward";
import ArrowUpward from "@mui/icons-material/ArrowUpward";
import Badge from "@mui/icons-material/Badge";
import BeachAccess from "@mui/icons-material/BeachAccess";
import Build from "@mui/icons-material/Build";
import CalendarMonth from "@mui/icons-material/CalendarMonth";
import CheckCircle from "@mui/icons-material/CheckCircle";
import CompareArrows from "@mui/icons-material/CompareArrows";
import CreditCard from "@mui/icons-material/CreditCard";
import Description from "@mui/icons-material/Description";
import EditNote from "@mui/icons-material/EditNote";
import EventRepeat from "@mui/icons-material/EventRepeat";
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
import { Caisse } from "../pages/Caisse";
import { Catalogue } from "../pages/Catalogue";
import { Clients } from "../pages/Clients";
import { Commandes } from "../pages/Commandes";
import { Devis } from "../pages/Devis";
import { Factures } from "../pages/Factures";
import { Imports } from "../pages/Imports";
import { Magasins } from "../pages/Magasins";
import { RessourcesHumaines } from "../pages/RessourcesHumaines";
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
};

export type Module = { id: string; libelle: string; tuiles: Tuile[] };

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
  const voirClients = a("crm.view_client");
  const voirCatalogue = a("stock.view_article");
  const droitsTresorerie = {
    cloturer: a("tresorerie.add_cloturecaisse"),
    depenses: a("tresorerie.add_depensecaisse"),
    verifier: a("tresorerie.valider_cloturecaisse"),
    voirClotures: a("tresorerie.view_cloturecaisse"),
    versements: a("tresorerie.add_operationtresorerie"),
    banque: a("tresorerie.view_operationtresorerie"),
    rapprocher: a("tresorerie.rapprocher_operationtresorerie"),
    gererComptes: a("tresorerie.add_comptetresorerie"),
  };
  const tresorerie = (onglet: keyof typeof droitsTresorerie) =>
    si(droitsTresorerie[onglet], () => <Tresorerie droits={droitsTresorerie} ongletInitial={ONGLETS_TRESORERIE[onglet]} />);
  const droitsRh = {
    voirEmployes: a("rh.view_employe"),
    creerEmploye: a("rh.add_employe"),
    voirPresence: a("rh.view_pointage"),
    pointer: a("rh.add_pointage"),
    voirConges: a("rh.view_demandeconge"),
    saisirConge: a("rh.add_demandeconge") && a("rh.view_employe"),
    deciderConge: a("rh.decider_demandeconge"),
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
    si(voirCatalogue, () => <Catalogue familleInitiale={famille} />);
  const imports = {
    catalogue: a("stock.add_article") && a("stock.change_prixarticle"),
    stock: a("stock.add_mouvementstock"),
  };

  const modules: Module[] = [
    {
      id: "vente",
      libelle: "Vente",
      tuiles: [
        { id: "recherche-verre", libelle: "Recherche Verre", icone: Visibility, couleur: COULEURS.violet, ecran: stock("verre") },
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
          ecran: si(vendre, () =>
            voirClients ? <VenteComptoir creerClient={a("crm.add_client")} /> : <Caisse />,
          ),
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
              }}
            />
          )),
        },
        { id: "clients", libelle: "Clients et ordonnances", icone: People, couleur: COULEURS.turquoise, ecran: clients },
        {
          id: "commandes",
          libelle: "Commandes en cours",
          icone: LocalShipping,
          couleur: COULEURS.bleu,
          ecran: si(vendre, () => <Commandes />),
        },
        aVenir("nouvelle-visite", "Nouvelle Visite", PersonAddAlt, COULEURS.turquoise),
        aVenir("liste-visites", "Liste Visites", ListAlt, COULEURS.jaune),
        aVenir("visites-filtre-facture", "Visites Filtre Facture", FilterAlt, COULEURS.jaune),
        aVenir("suivi-visite", "Suivi Visite", TrackChanges, COULEURS.orange),
        aVenir("consulter-visite", "Consulter Visite", FindInPage, COULEURS.rouge),
        aVenir("lunettes-vendues", "Lunettes Vendues", Sell, COULEURS.turquoise),
        aVenir("liste-recus", "Liste Reçus", ReceiptLong, COULEURS.jaune),
        aVenir("creation-produit", "Demande Création Produit", AddBox, COULEURS.bleu),
        aVenir("prospect", "Prospect Client", PersonSearch, COULEURS.rouge),
        aVenir("code-barre", "Code à barres", QrCode2, COULEURS.bleu),
        aVenir("historique-visites", "Historique Visites", History, COULEURS.rouge),
        aVenir("casse-verre", "Casse Verre", Build, COULEURS.vert),
        aVenir("code-barre-marque", "Code à barres Marque", QrCodeScanner, COULEURS.bleu),
        aVenir("visites-stock", "Visites de Stock", Inventory, COULEURS.brun),
        aVenir("reste-vendeur", "Reste par Vendeur", Payments, COULEURS.vert),
      ],
    },
    {
      id: "stock",
      libelle: "Stock",
      tuiles: [
        { id: "stock-monture", libelle: "Stock Monture", icone: Inventory2, couleur: COULEURS.jaune, ecran: stock("monture") },
        { id: "stock-lentille", libelle: "Stock Lentille", icone: Inventory2, couleur: COULEURS.jaune, ecran: stock("lentille") },
        { id: "stock-article", libelle: "Stock Article", icone: Inventory2, couleur: COULEURS.jaune, ecran: stock("divers") },
        { id: "stock-verre", libelle: "Stock Verre", icone: Inventory2, couleur: COULEURS.jaune, ecran: stock("verre") },
        {
          id: "bon-entree",
          libelle: "Bon Entrée",
          icone: ArrowDownward,
          couleur: COULEURS.rouge,
          ecran: si(imports.stock, () => <Imports droits={{ catalogue: false, stock: true }} />),
        },
        {
          id: "import-catalogue",
          libelle: "Import Catalogue",
          icone: UploadFile,
          couleur: COULEURS.bleu,
          ecran: si(imports.catalogue, () => <Imports droits={{ catalogue: true, stock: false }} />),
        },
        {
          id: "commande-verres",
          libelle: "Commande Verres Fournisseur",
          icone: LocalShipping,
          couleur: COULEURS.violet,
          ecran: si(a("achats.add_commandefournisseur"), () => <Verres />),
        },
        aVenir("inventaire", "Inventaire", Sync, COULEURS.bleu),
        aVenir("stock-date", "Stock à la Date", CalendarMonth, COULEURS.vert),
        aVenir("config-stock", "Config Stock", Widgets, COULEURS.brun),
        aVenir("stock-depense", "Stock Article Dépense", Inventory2, COULEURS.jaune),
        aVenir("mouvements", "Mouvements de Stock", TableChart, COULEURS.brun),
        aVenir("stock-total", "Stock Total", Widgets, COULEURS.orange),
        aVenir("bon-transfert", "Bon Transfert", SwapHoriz, COULEURS.bleu),
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
          ecran: si(vendre, () => <Commandes />),
        },
        {
          id: "remboursement",
          libelle: "Remboursement Client",
          icone: Undo,
          couleur: COULEURS.vert,
          ecran: si(a("ventes.add_avoir"), () => <Avoirs />),
        },
        {
          id: "avance-personnel",
          libelle: "Avance Personnel",
          icone: Groups,
          couleur: COULEURS.bleu,
          ecran: si(droitsRh.voirAcomptes, () => <RessourcesHumaines droits={droitsRh} ongletInitial="acomptes" />),
        },
        aVenir("vente-credit", "Liste Vente à Crédit", ListAlt, COULEURS.brun),
        aVenir("liste-reglements", "Liste Règlements", ReceiptLong, COULEURS.gris),
        aVenir("changement-cheques", "Changement Chèques", SwapHoriz, COULEURS.brun),
        aVenir("bon-cnam", "Bon CNAM", Description, COULEURS.orange),
        aVenir("reglement-credit", "Règlement Crédit", CreditCard, COULEURS.brun),
        aVenir("transfert-solde", "Transfert Solde", CompareArrows, COULEURS.gris),
        aVenir("impaye", "Impayé Client", ReportProblem, COULEURS.rouge),
        aVenir("reglement-impaye", "Règlement Impayé", ReportProblem, COULEURS.rouge),
      ],
    },
    {
      id: "caisse",
      libelle: "Caisse",
      tuiles: [
        { id: "session-en-cours", libelle: "Session en Cours", icone: LockOpen, couleur: COULEURS.jaune, ecran: tresorerie("cloturer") },
        { id: "sessions-cloturees", libelle: "Sessions Clôturées", icone: Lock, couleur: COULEURS.jaune, ecran: tresorerie("voirClotures") },
        { id: "validation", libelle: "Validation Clôtures", icone: CheckCircle, couleur: COULEURS.vert, ecran: tresorerie("verifier") },
        { id: "operations-diverses", libelle: "Opérations Diverses", icone: Payments, couleur: COULEURS.orange, ecran: tresorerie("depenses") },
        { id: "versement", libelle: "Versement Espèces", icone: Savings, couleur: COULEURS.vert, ecran: tresorerie("versements") },
        { id: "bordereau", libelle: "Bordereau de Versement", icone: EditNote, couleur: COULEURS.gris, ecran: tresorerie("versements") },
        { id: "coffre", libelle: "Coffre et Banque", icone: AccountBalance, couleur: COULEURS.brun, ecran: tresorerie("banque") },
        aVenir("echeancier", "Échéancier Client", CalendarMonth, COULEURS.vert),
        aVenir("export-reglements", "Exportation Règlements", UploadFile, COULEURS.gris),
        aVenir("transfert-reglements", "Transfert Règlements Clients", SwapHoriz, COULEURS.vert),
        aVenir("report-magasin", "Mise à jour Report Magasin", Store, COULEURS.brun),
      ],
    },
    {
      id: "sav",
      libelle: "SAV",
      tuiles: [
        aVenir("creation-sav", "Création SAV", Build, COULEURS.gris),
        aVenir("cloture-sav", "Clôture SAV", Lock, COULEURS.gris),
        aVenir("visites-sav", "Visites SAV", ListAlt, COULEURS.gris),
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
          ecran: si(a("ventes.add_facture"), () => <Factures />),
        },
        { id: "avoir", libelle: "Avoir", icone: Undo, couleur: COULEURS.rouge, ecran: si(a("ventes.add_avoir"), () => <Avoirs />) },
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
          libelle: "Demande de Congé",
          icone: BeachAccess,
          couleur: COULEURS.turquoise,
          ecran: () => <RessourcesHumaines droits={droitsRh} ongletInitial="moi" />,
        },
        {
          id: "demande-acompte",
          libelle: "Demande d'Acompte",
          icone: Savings,
          couleur: COULEURS.vert,
          ecran: () => <RessourcesHumaines droits={droitsRh} ongletInitial="mes-acomptes" />,
        },
        aVenir("demande-attestation", "Demande d'Attestation", Description, COULEURS.violet),
        aVenir("demande-pret", "Demande de Prêt", AccountBalance, COULEURS.brun),
        aVenir("fiche-paie", "Fiche de Paie", ReceiptLong, COULEURS.bleu),
        {
          id: "rh",
          libelle: "Ressources Humaines",
          icone: Badge,
          couleur: COULEURS.bleu,
          ecran: () => <RessourcesHumaines droits={droitsRh} />,
        },
        { id: "magasins", libelle: "Magasins", icone: Store, couleur: COULEURS.brun, ecran: si(a("reseau.view_magasin"), () => <Magasins />) },
        {
          id: "acces",
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
        { id: "plateforme", libelle: "État de la Plateforme", icone: MonitorHeart, couleur: COULEURS.vert, ecran: () => <Accueil /> },
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
