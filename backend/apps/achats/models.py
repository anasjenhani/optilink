from django.conf import settings
from django.db import models

from core.managers import ParMagasinManager
from core.models import ModeleDeBase


def _code_fournisseur_suivant():
    dernier = Fournisseur.objects.aggregate(dernier=models.Max("code"))["dernier"]
    return (dernier or 0) + 1


class Fournisseur(ModeleDeBase):
    """Fournisseur (laboratoire de verres, marque de montures…), commun à tout le réseau."""

    class FormeJuridique(models.TextChoices):
        SARL = "SARL", "SARL"
        SUARL = "SUARL", "SUARL"
        SA = "SA", "SA"
        SNC = "SNC", "SNC"
        PERSONNE_PHYSIQUE = "PP", "Personne physique"

    class RegimeTva(models.TextChoices):
        ASSUJETTI = "assujetti", "Payer la TVA"
        EXPORT = "export", "Export"
        EXONERATION = "exoneration", "Exonération"

    code = models.PositiveIntegerField(
        unique=True, null=True, editable=False, help_text="Numéro attribué à la création : 1, 2, 3…"
    )
    nom = models.CharField("raison sociale", max_length=200, unique=True)
    notre_code = models.CharField("notre code chez le fournisseur", max_length=40, blank=True)
    responsable = models.CharField(max_length=100, blank=True)
    fournisseur_verres = models.BooleanField(
        "fournisseur de verres", default=False, help_text="Laboratoire : verres commandés."
    )
    pays = models.ForeignKey("reseau.Pays", on_delete=models.PROTECT, related_name="+")
    # Information financière
    matricule_fiscal = models.CharField(max_length=30, blank=True)
    registre_commerce = models.CharField("registre de commerce", max_length=30, blank=True)
    code_douane = models.CharField(max_length=30, blank=True)
    forme_juridique = models.CharField(max_length=5, choices=FormeJuridique.choices, blank=True)
    capital_social = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    timbre_fiscal = models.BooleanField(default=True)
    assujetti = models.BooleanField("assujetti à la TVA", default=True)
    fodec = models.BooleanField(
        "FODEC", default=False, help_text="Ajoute 1 % du montant net HT, soumis à la TVA."
    )
    regime_tva = models.CharField(
        "régime de TVA", max_length=12, choices=RegimeTva.choices, default=RegimeTva.ASSUJETTI
    )
    numero_exoneration = models.CharField("n° d'exonération", max_length=40, blank=True)
    exoneration_du = models.DateField(null=True, blank=True)
    exoneration_au = models.DateField(null=True, blank=True)
    # Adresse et contacts
    adresse = models.TextField(blank=True)
    code_postal = models.CharField(max_length=10, blank=True)
    ville = models.CharField(max_length=100, blank=True)
    telephone = models.CharField("téléphone", max_length=30, blank=True)
    telephone_2 = models.CharField("téléphone 2", max_length=30, blank=True)
    fax = models.CharField(max_length=30, blank=True)
    email = models.EmailField("e-mail", blank=True)
    site_web = models.URLField("site web", blank=True)
    # Identité bancaire
    banque = models.CharField(max_length=100, blank=True)
    rib = models.CharField("RIB", max_length=34, blank=True)
    observation = models.TextField(blank=True)
    est_actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "fournisseur"

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if self.code is None:
            self.code = _code_fournisseur_suivant()
        super().save(*args, **kwargs)


class CommandeFournisseur(ModeleDeBase):
    """Commande passée par un magasin à un fournisseur pour les verres de ses clients.

    Chaque ligne correspond à une ligne d'une commande client : à la réception, la commande
    client peut être livrée.
    """

    class Statut(models.TextChoices):
        ENVOYEE = "envoyee", "Envoyée"
        RECUE = "recue", "Reçue"
        ANNULEE = "annulee", "Annulée"

    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    numero = models.CharField(max_length=40, unique=True)
    annee = models.PositiveSmallIntegerField()
    sequence = models.PositiveIntegerField()
    fournisseur = models.ForeignKey(Fournisseur, on_delete=models.PROTECT, related_name="commandes")
    reference_fournisseur = models.CharField(
        max_length=60, blank=True, help_text="N° donné par le fournisseur."
    )
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.ENVOYEE)
    passee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    recue_le = models.DateTimeField(null=True, blank=True)
    recue_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    objects = ParMagasinManager()
    tous = models.Manager()

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "commande fournisseur"
        verbose_name_plural = "commandes fournisseurs"
        constraints = [
            models.UniqueConstraint(
                fields=["magasin", "annee", "sequence"], name="commande_fournisseur_sans_doublon"
            )
        ]

    def __str__(self):
        return self.numero


class LigneCommandeFournisseur(models.Model):
    commande = models.ForeignKey(
        CommandeFournisseur, on_delete=models.PROTECT, related_name="lignes"
    )
    ligne_vente = models.ForeignKey(
        "ventes.LigneVente", on_delete=models.PROTECT, related_name="commandes_fournisseur"
    )
    article = models.ForeignKey("stock.Article", on_delete=models.PROTECT, related_name="+")
    quantite = models.PositiveIntegerField()
    details = models.CharField(
        max_length=300, blank=True, help_text="Œil, correction, traitement… pour le fournisseur."
    )

    class Meta:
        verbose_name = "ligne de commande fournisseur"

    def __str__(self):
        return f"{self.quantite} × {self.article}"


class CasseVerre(ModeleDeBase):
    """Verre cassé ou défectueux après réception : il repasse « à commander ».

    Une casse vise un verre reçu d'une commande fournisseur ; la commande client retrouve
    alors ce verre dans la liste des verres à commander, et son suivi revient à cette étape.
    """

    class Cause(models.TextChoices):
        ATELIER = "atelier", "Casse à l'atelier (montage)"
        FOURNISSEUR = "fournisseur", "Défaut du fournisseur"
        CLIENT = "client", "Casse par le client"

    ligne_commande = models.OneToOneField(
        LigneCommandeFournisseur,
        on_delete=models.PROTECT,
        related_name="casse",
        verbose_name="verre commandé",
    )
    vente = models.ForeignKey(
        "ventes.Vente", on_delete=models.PROTECT, related_name="casses_verres"
    )
    cause = models.CharField(max_length=12, choices=Cause.choices)
    observation = models.CharField(max_length=300, blank=True)
    declaree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "casse de verre"
        verbose_name_plural = "casses de verres"

    def __str__(self):
        return f"Casse {self.ligne_commande.article} ({self.vente})"

    @property
    def magasin_id(self):
        return self.vente.magasin_id


class BonReception(ModeleDeBase):
    """Bon de réception achat : la marchandise livrée par un fournisseur, avec son BL.

    À l'enregistrement, les articles de stock conformes entrent en stock du magasin et les
    verres commandés pour des clients sont marqués reçus. Un bon enregistré ne se modifie plus.
    """

    class Etat(models.TextChoices):
        NON_FACTURE = "non_facture", "Non facturé"
        FACTURE = "facture", "Facturé"

    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    numero = models.CharField(max_length=40, unique=True)
    annee = models.PositiveSmallIntegerField()
    sequence = models.PositiveIntegerField()
    fournisseur = models.ForeignKey(
        Fournisseur, on_delete=models.PROTECT, related_name="receptions"
    )
    date_saisie = models.DateField("date de saisie")
    numero_bl = models.CharField("n° BL fournisseur", max_length=60)
    date_bl = models.DateField("date BL fournisseur")
    observation = models.TextField(blank=True)
    taux_remise_ex = models.DecimalField(
        "remise exceptionnelle (%)", max_digits=5, decimal_places=2, default=0
    )
    etat = models.CharField(max_length=12, choices=Etat.choices, default=Etat.NON_FACTURE)
    numero_facture = models.CharField("n° facture fournisseur", max_length=60, blank=True)
    facture = models.ForeignKey(
        "FactureAchat",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bons",
        verbose_name="facture achat",
    )
    total_ht = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    total_remise = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    remise_ex = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    total_net_ht = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    total_fodec = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    total_tva = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    objects = ParMagasinManager()
    tous = models.Manager()

    class Meta:
        ordering = ["-annee", "-sequence"]
        verbose_name = "bon de réception"
        verbose_name_plural = "bons de réception"
        constraints = [
            models.UniqueConstraint(
                fields=["magasin", "annee", "sequence"], name="bon_reception_sans_doublon"
            ),
            models.UniqueConstraint(
                fields=["fournisseur", "numero_bl"], name="bl_fournisseur_une_fois"
            ),
        ]

    def __str__(self):
        return self.numero


class LigneReception(models.Model):
    """Article reçu. Une ligne non conforme (verre faux, monture abîmée…) n'entre pas."""

    class Oeil(models.TextChoices):
        DROIT = "D", "Œil droit"
        GAUCHE = "G", "Œil gauche"

    bon = models.ForeignKey(BonReception, on_delete=models.CASCADE, related_name="lignes")
    article = models.ForeignKey("stock.Article", on_delete=models.PROTECT, related_name="+")
    ligne_commande = models.ForeignKey(
        LigneCommandeFournisseur,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="receptions",
        help_text="Verre commandé pour un client.",
    )
    oeil = models.CharField("œil", max_length=1, choices=Oeil.choices, blank=True)
    designation = models.CharField("désignation", max_length=300)
    quantite = models.PositiveIntegerField("quantité")
    prix_achat_ht = models.DecimalField("prix d'achat HT", max_digits=12, decimal_places=3)
    taux_remise = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2)
    net_ht = models.DecimalField(max_digits=14, decimal_places=3)
    montant_ttc = models.DecimalField(max_digits=14, decimal_places=3)
    non_conforme = models.BooleanField(default=False)
    motif = models.CharField(max_length=200, blank=True)
    numero_serie = models.CharField("n° de série", max_length=60, blank=True)
    numero_lot = models.CharField("n° de lot", max_length=60, blank=True)
    date_peremption = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "ligne de réception"
        verbose_name_plural = "lignes de réception"

    def __str__(self):
        return f"{self.quantite} × {self.designation}"


class FactureAchat(ModeleDeBase):
    """Facture d'un fournisseur : elle regroupe ses bons de réception (BL) d'un magasin.

    Les totaux reprennent ceux des bons ; la facture peut ajouter une remise exceptionnelle,
    des frais, le timbre fiscal et un ajustement (écart d'arrondi avec la facture papier).
    Une facture enregistrée ne se modifie plus.
    """

    class Paiement(models.TextChoices):
        NON_PAYE = "non_paye", "Non payé"
        PARTIEL = "partiel", "Payé en partie"
        PAYE = "paye", "Payé"

    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    numero = models.CharField(max_length=40, unique=True)
    annee = models.PositiveSmallIntegerField()
    sequence = models.PositiveIntegerField()
    fournisseur = models.ForeignKey(
        Fournisseur, on_delete=models.PROTECT, related_name="factures_achat"
    )
    date_entree = models.DateField("date d'entrée")
    reference_fournisseur = models.CharField(
        "référence fournisseur", max_length=60, help_text="N° de la facture chez le fournisseur."
    )
    date_reference = models.DateField("date de la facture fournisseur")
    taux_remise_ex = models.DecimalField(
        "remise exceptionnelle (%)", max_digits=5, decimal_places=2, default=0
    )
    frais_supplementaires = models.DecimalField(
        max_digits=14, decimal_places=3, default=0, help_text="Transport, port… (TTC)."
    )
    timbre_fiscal = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    ajustement = models.DecimalField(
        "ajustement des totaux",
        max_digits=10,
        decimal_places=3,
        default=0,
        help_text="Écart d'arrondi pour retrouver le total TTC de la facture papier.",
    )
    observation = models.TextField(blank=True)
    paiement = models.CharField(max_length=10, choices=Paiement.choices, default=Paiement.NON_PAYE)
    total_ht = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    total_remise = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    remise_ex = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    total_net_ht = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    total_fodec = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    total_tva = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    objects = ParMagasinManager()
    tous = models.Manager()

    class Meta:
        ordering = ["-annee", "-sequence"]
        verbose_name = "facture achat"
        verbose_name_plural = "factures achat"
        constraints = [
            models.UniqueConstraint(
                fields=["magasin", "annee", "sequence"], name="facture_achat_sans_doublon"
            ),
            models.UniqueConstraint(
                fields=["fournisseur", "reference_fournisseur"],
                name="facture_fournisseur_une_fois",
            ),
        ]

    def __str__(self):
        return self.numero


class BonRetour(ModeleDeBase):
    """Bon retour fournisseur : marchandise renvoyée (non conforme à la réception, ou sortie
    du stock). Sa valeur se déduit de la facture achat du fournisseur qui l'importe.
    Un bon retour enregistré ne se modifie plus.
    """

    class Etat(models.TextChoices):
        NON_FACTURE = "non_facture", "Non déduit"
        FACTURE = "facture", "Déduit d'une facture"

    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    numero = models.CharField(max_length=40, unique=True)
    annee = models.PositiveSmallIntegerField()
    sequence = models.PositiveIntegerField()
    fournisseur = models.ForeignKey(Fournisseur, on_delete=models.PROTECT, related_name="retours")
    date_retour = models.DateField("date du retour")
    motif = models.CharField(max_length=200, blank=True)
    observation = models.TextField(blank=True)
    etat = models.CharField(max_length=12, choices=Etat.choices, default=Etat.NON_FACTURE)
    facture = models.ForeignKey(
        FactureAchat,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="retours",
        verbose_name="facture achat",
    )
    total_ht = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    total_remise = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    remise_ex = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    total_net_ht = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    total_fodec = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    total_tva = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    objects = ParMagasinManager()
    tous = models.Manager()

    class Meta:
        ordering = ["-annee", "-sequence"]
        verbose_name = "bon retour fournisseur"
        verbose_name_plural = "bons retour fournisseur"
        constraints = [
            models.UniqueConstraint(
                fields=["magasin", "annee", "sequence"], name="bon_retour_sans_doublon"
            ),
        ]

    def __str__(self):
        return self.numero


class LigneRetour(models.Model):
    """Article renvoyé : une ligne non conforme d'un bon de réception, ou un article du stock."""

    bon = models.ForeignKey(BonRetour, on_delete=models.CASCADE, related_name="lignes")
    article = models.ForeignKey("stock.Article", on_delete=models.PROTECT, related_name="+")
    ligne_reception = models.OneToOneField(
        LigneReception,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="retour",
        help_text="Ligne non conforme du bon de réception renvoyée.",
    )
    designation = models.CharField("désignation", max_length=300)
    quantite = models.PositiveIntegerField("quantité")
    prix_achat_ht = models.DecimalField("prix d'achat HT", max_digits=12, decimal_places=3)
    taux_remise = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2)
    net_ht = models.DecimalField(max_digits=14, decimal_places=3)
    montant_ttc = models.DecimalField(max_digits=14, decimal_places=3)
    motif = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "ligne de retour"
        verbose_name_plural = "lignes de retour"

    def __str__(self):
        return f"{self.quantite} × {self.designation}"
