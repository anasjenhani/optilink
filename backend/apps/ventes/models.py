from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.managers import ParMagasinManager
from core.models import ModeleDeBase


class TypeDocument(models.TextChoices):
    TICKET = "ticket", "Ticket de caisse"
    FACTURE = "facture", "Facture"
    DEVIS = "devis", "Devis"
    AVOIR = "avoir", "Avoir"
    ACHAT = "achat", "Commande fournisseur"
    RECEPTION = "reception", "Bon de réception"


# Préfixe du numéro : M01-T2026-000001 pour un ticket, M01-F2026-000001 pour une facture,
# M01-D2026-000001 pour un devis, M01-A2026-000001 pour un avoir, M01-C2026-000001 pour une
# commande fournisseur, M01-R2026-000001 pour un bon de réception. Chaque type de document a
# sa propre suite de numéros.
PREFIXES = {
    TypeDocument.TICKET: "T",
    TypeDocument.FACTURE: "F",
    TypeDocument.DEVIS: "D",
    TypeDocument.AVOIR: "A",
    TypeDocument.ACHAT: "C",
    TypeDocument.RECEPTION: "R",
}


class CompteurFacture(models.Model):
    """Dernier numéro attribué par magasin, année et type de document (numérotation sans trou).

    Tickets et factures ont chacun leur suite.
    """

    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    annee = models.PositiveSmallIntegerField()
    type_document = models.CharField(max_length=10, choices=TypeDocument.choices)
    dernier = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "compteur de factures"
        constraints = [
            models.UniqueConstraint(
                fields=["magasin", "annee", "type_document"], name="compteur_unique_par_annee"
            )
        ]

    def __str__(self):
        return f"{self.magasin_id}/{self.annee}/{self.type_document} : {self.dernier}"


class Etape(models.TextChoices):
    """Étapes du suivi qualité d'une commande, de la visite à la remise au client."""

    A_COMMANDER = "a_commander", "Visite créée à commander"
    COMMANDEE = "commandee", "Commandée, en attente de réception BL"
    MONTAGE = "montage", "Montage en cours"
    CONTROLE = "controle", "Contrôle qualité"
    CONTACT_CLIENT = "contact_client", "Client prévenu"
    INSTANCE = "instance", "En instance"


class Vente(ModeleDeBase):
    """Vente enregistrée en caisse, avec son ticket. Jamais modifiée : une correction passera
    par un avoir.

    Une vente est soit remise tout de suite (payée en totalité), soit une **commande** : le
    client verse un acompte, l'équipement est préparé (verres commandés au fournisseur), puis
    il est livré contre le solde. La facture est une étape à part (``Facture``), possible
    seulement quand la vente est entièrement payée.
    """

    class Statut(models.TextChoices):
        EN_COMMANDE = "en_commande", "En commande"
        LIVREE = "livree", "Livrée"
        ANNULEE = "annulee", "Annulée"

    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    numero = models.CharField(max_length=40, unique=True, help_text="N° de ticket.")
    annee = models.PositiveSmallIntegerField()
    sequence = models.PositiveIntegerField()
    client = models.ForeignKey(
        "crm.Client", on_delete=models.PROTECT, null=True, blank=True, related_name="ventes"
    )
    vendeur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    devise = models.CharField(max_length=3, help_text="Monnaie du pays du magasin à la vente.")
    total_ht = models.DecimalField(max_digits=14, decimal_places=3)
    total_tva = models.DecimalField(max_digits=14, decimal_places=3)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=3)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.LIVREE)
    livraison_prevue_le = models.DateField(null=True, blank=True)
    peniche = models.PositiveSmallIntegerField(
        "péniche",
        null=True,
        blank=True,
        help_text="Bac où l'équipement de la commande attend sa livraison ; libre après.",
    )
    livree_le = models.DateTimeField(null=True, blank=True)
    livree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    etape = models.CharField(
        "étape de l'atelier",
        max_length=16,
        choices=Etape.choices,
        blank=True,
        help_text="Dernière étape saisie au suivi ; vide, l'étape vient des verres commandés.",
    )

    objects = ParMagasinManager()
    tous = models.Manager()

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "vente"
        permissions = [
            ("appliquer_remise", "Peut appliquer une remise"),
            ("consulter_reporting", "Peut consulter le reporting des ventes"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["magasin", "annee", "sequence"], name="facture_sans_doublon"
            ),
            # Une péniche ne contient qu'une commande en cours ; livrée ou annulée, elle se libère.
            models.UniqueConstraint(
                fields=["magasin", "peniche"],
                condition=models.Q(statut="en_commande", peniche__isnull=False),
                name="une_commande_par_peniche",
            ),
        ]

    def __str__(self):
        return self.numero

    @property
    def regle_par_le_client(self):
        return sum((p.montant for p in self.paiements.all()), Decimal("0"))

    @property
    def pris_en_charge(self):
        """Part des organismes (CNAM, assurance, mutuelle), sauf prise en charge refusée."""
        return sum(
            (
                pec.montant
                for pec in self.prises_en_charge.all()
                if pec.statut != PriseEnCharge.Statut.REFUSEE
            ),
            Decimal("0"),
        )

    @property
    def reste_a_payer(self):
        """Ce que doit encore le client : total moins ses règlements et la part des organismes."""
        return self.total_ttc - self.regle_par_le_client - self.pris_en_charge


class Facture(ModeleDeBase):
    """Facture émise à part, au nom d'un client, pour une vente entièrement payée.

    Numérotée sans trou par magasin et par année (suite distincte des tickets), jamais modifiée.
    Elle porte le droit de timbre du pays.
    """

    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    vente = models.OneToOneField(Vente, on_delete=models.PROTECT, related_name="facture")
    client = models.ForeignKey("crm.Client", on_delete=models.PROTECT, related_name="factures")
    # Copiés de la fiche client à l'émission : modifier la fiche ne change pas la facture.
    client_nom = models.CharField(max_length=200, blank=True)
    client_adresse = models.CharField(max_length=320, blank=True)
    client_matricule_fiscal = models.CharField(max_length=30, blank=True)
    numero = models.CharField(max_length=40, unique=True)
    annee = models.PositiveSmallIntegerField()
    sequence = models.PositiveIntegerField()
    devise = models.CharField(max_length=3)
    total_ht = models.DecimalField(max_digits=14, decimal_places=3)
    total_tva = models.DecimalField(max_digits=14, decimal_places=3)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=3)
    timbre_fiscal = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    net_a_payer = models.DecimalField(
        max_digits=14, decimal_places=3, help_text="Total TTC + droit de timbre."
    )
    mode_paiement_timbre = models.CharField(
        max_length=20, blank=True, help_text="Comment le client a réglé le timbre."
    )
    emise_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    objects = ParMagasinManager()
    tous = models.Manager()

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "facture"
        constraints = [
            models.UniqueConstraint(
                fields=["magasin", "annee", "sequence"], name="facture_numerotee_sans_doublon"
            )
        ]

    def __str__(self):
        return self.numero


class Devis(ModeleDeBase):
    """Devis d'équipement remis à un client, avec ses prix figés jusqu'à la date de validité.

    Il peut s'appuyer sur une ordonnance du client. Accepté, il s'encaisse en caisse au prix
    du devis, même si le tarif a changé entre-temps. Ses lignes ne se modifient pas : une
    autre proposition est un nouveau devis.
    """

    class Statut(models.TextChoices):
        EN_COURS = "en_cours", "En cours"
        ACCEPTE = "accepte", "Accepté"
        REFUSE = "refuse", "Refusé"
        ENCAISSE = "encaisse", "Encaissé"

    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    numero = models.CharField(max_length=40, unique=True)
    annee = models.PositiveSmallIntegerField()
    sequence = models.PositiveIntegerField()
    client = models.ForeignKey("crm.Client", on_delete=models.PROTECT, related_name="devis")
    prescription = models.ForeignKey(
        "optique.Prescription",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="devis",
        help_text="Ordonnance du client sur laquelle s'appuie le devis.",
    )
    etabli_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    devise = models.CharField(max_length=3)
    total_ht = models.DecimalField(max_digits=14, decimal_places=3)
    total_tva = models.DecimalField(max_digits=14, decimal_places=3)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=3)
    valable_jusqu_au = models.DateField()
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.EN_COURS)
    vente = models.OneToOneField(
        Vente, on_delete=models.PROTECT, null=True, blank=True, related_name="devis"
    )
    remarques = models.TextField(blank=True)

    objects = ParMagasinManager()
    tous = models.Manager()

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "devis"
        verbose_name_plural = "devis"
        constraints = [
            models.UniqueConstraint(
                fields=["magasin", "annee", "sequence"], name="devis_numerote_sans_doublon"
            )
        ]

    def __str__(self):
        return self.numero


class LigneDevis(models.Model):
    class Oeil(models.TextChoices):
        DROIT = "od", "Œil droit"
        GAUCHE = "og", "Œil gauche"

    devis = models.ForeignKey(Devis, on_delete=models.PROTECT, related_name="lignes")
    article = models.ForeignKey("stock.Article", on_delete=models.PROTECT, related_name="+")
    libelle = models.CharField(max_length=200)
    oeil = models.CharField(
        max_length=2, choices=Oeil.choices, blank=True, help_text="Pour un verre ou une lentille."
    )
    quantite = models.PositiveIntegerField()
    prix_unitaire_ttc = models.DecimalField(max_digits=14, decimal_places=3)
    remise_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=3)

    class Meta:
        verbose_name = "ligne de devis"

    def __str__(self):
        return f"{self.quantite} × {self.libelle}"


class Avoir(ModeleDeBase):
    """Avoir : crédit rendu au client sur une vente (retour d'articles, ou annulation).

    La vente et sa facture ne sont jamais modifiées : l'avoir les corrige, avec sa propre suite
    de numéros. Il dit ce qui est remboursé au client et ce qui revient en stock.
    """

    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    numero = models.CharField(max_length=40, unique=True)
    annee = models.PositiveSmallIntegerField()
    sequence = models.PositiveIntegerField()
    vente = models.ForeignKey(Vente, on_delete=models.PROTECT, related_name="avoirs")
    facture = models.ForeignKey(
        Facture,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="avoirs",
        help_text="Facture corrigée, si la vente avait été facturée.",
    )
    client = models.ForeignKey(
        "crm.Client", on_delete=models.PROTECT, null=True, blank=True, related_name="avoirs"
    )
    annulation = models.BooleanField(default=False, help_text="Annule toute la vente.")
    motif = models.CharField(max_length=300)
    devise = models.CharField(max_length=3)
    total_ht = models.DecimalField(max_digits=14, decimal_places=3)
    total_tva = models.DecimalField(max_digits=14, decimal_places=3)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=3)
    montant_rembourse = models.DecimalField(max_digits=14, decimal_places=3)
    mode_remboursement = models.CharField(max_length=20, blank=True)
    emis_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    objects = ParMagasinManager()
    tous = models.Manager()

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "avoir"
        constraints = [
            models.UniqueConstraint(
                fields=["magasin", "annee", "sequence"], name="avoir_numerote_sans_doublon"
            )
        ]

    def __str__(self):
        return self.numero


def _mesure(aide):
    return models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True, help_text=aide
    )


class Lunette(models.Model):
    """Une paire de lunettes d'une visite : sa monture, ses deux verres et leurs suppléments.

    La correction vient d'une ordonnance (``optique.Prescription``, chiffrée) ; la lunette garde
    les mesures de montage prises par l'opticien (écarts et hauteurs) et l'œil directeur.
    """

    class Vision(models.TextChoices):
        LOIN = "loin", "Loin"
        PRES = "pres", "Près"
        DOUBLE_FOYER = "double_foyer", "Double foyer"
        DEGRESSIF = "degressif", "Dégressif"
        PROGRESSIF = "progressif", "Progressif"

    class Oeil(models.TextChoices):
        DROIT = "droit", "Droit"
        GAUCHE = "gauche", "Gauche"

    vente = models.ForeignKey(Vente, on_delete=models.PROTECT, related_name="lunettes")
    numero = models.PositiveSmallIntegerField(help_text="N° de la lunette dans la visite (1, 2…).")
    vision = models.CharField(max_length=20, choices=Vision.choices, blank=True)
    solaire = models.BooleanField(default=False, help_text="Lunette solaire (sinon optique).")
    inadaptation = models.BooleanField(
        default=False, help_text="Refaite parce que le client ne s'est pas adapté."
    )
    prescription = models.ForeignKey(
        "optique.Prescription",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lunettes",
        help_text="Ordonnance d'où vient la correction ; vide pour une solaire sans correction.",
    )
    oeil_directeur = models.CharField(max_length=10, choices=Oeil.choices, blank=True)
    ecart_d = _mesure("Demi-écart pupillaire de loin, œil droit (mm).")
    ecart_g = _mesure("Demi-écart pupillaire de loin, œil gauche (mm).")
    ecart_pres_d = _mesure("Demi-écart de près, œil droit (mm).")
    ecart_pres_g = _mesure("Demi-écart de près, œil gauche (mm).")
    hauteur_d = _mesure("Hauteur de montage, œil droit (mm).")
    hauteur_g = _mesure("Hauteur de montage, œil gauche (mm).")
    observation = models.TextField(blank=True)
    client_absent = models.BooleanField(
        default=False, help_text="Mesures prises sans le client (reprise d'une ancienne lunette)."
    )

    class Meta:
        ordering = ["vente", "numero"]
        verbose_name = "lunette"
        constraints = [
            models.UniqueConstraint(fields=["vente", "numero"], name="lunette_numero_unique")
        ]

    def __str__(self):
        return f"{self.vente.numero}/{self.numero}"


class Lentilles(models.Model):
    """Lentilles de contact d'une visite : celle de l'œil droit et celle de l'œil gauche.

    La correction (avec rayon et diamètre) vient d'une ordonnance de lentilles du client.
    """

    vente = models.ForeignKey(Vente, on_delete=models.PROTECT, related_name="lentilles")
    numero = models.PositiveSmallIntegerField(help_text="N° dans la visite (1, 2…).")
    prescription = models.ForeignKey(
        "optique.Prescription",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lentilles",
        help_text="Ordonnance de lentilles d'où vient la correction.",
    )
    observation = models.TextField(blank=True)

    class Meta:
        ordering = ["vente", "numero"]
        verbose_name = "lentilles"
        verbose_name_plural = "lentilles"
        constraints = [
            models.UniqueConstraint(fields=["vente", "numero"], name="lentilles_numero_unique")
        ]

    def __str__(self):
        return f"{self.vente.numero}/L{self.numero}"


class LigneVente(models.Model):
    class Role(models.TextChoices):
        MONTURE = "monture", "Monture"
        VERRE_D = "verre_d", "Verre droit"
        VERRE_G = "verre_g", "Verre gauche"
        SUPPLEMENT_D = "supplement_d", "Supplément verre droit"
        SUPPLEMENT_G = "supplement_g", "Supplément verre gauche"
        LENTILLE_D = "lentille_d", "Lentille droite"
        LENTILLE_G = "lentille_g", "Lentille gauche"

    vente = models.ForeignKey(Vente, on_delete=models.PROTECT, related_name="lignes")
    article = models.ForeignKey("stock.Article", on_delete=models.PROTECT, related_name="+")
    lunette = models.ForeignKey(
        Lunette, on_delete=models.PROTECT, null=True, blank=True, related_name="lignes"
    )
    lentilles = models.ForeignKey(
        Lentilles, on_delete=models.PROTECT, null=True, blank=True, related_name="lignes"
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        blank=True,
        help_text="Place dans la lunette ou les lentilles.",
    )
    numero_lot = models.CharField(
        "n° de lot", max_length=40, blank=True, help_text="Lentilles, produits : traçabilité."
    )
    date_peremption = models.DateField("date de péremption", null=True, blank=True)
    libelle = models.CharField(max_length=200)
    quantite = models.PositiveIntegerField()
    prix_unitaire_ttc = models.DecimalField(max_digits=14, decimal_places=3)
    remise_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=3)

    class Meta:
        verbose_name = "ligne de vente"

    def __str__(self):
        return f"{self.quantite} × {self.libelle}"


class LigneAvoir(models.Model):
    avoir = models.ForeignKey(Avoir, on_delete=models.PROTECT, related_name="lignes")
    ligne_vente = models.ForeignKey(LigneVente, on_delete=models.PROTECT, related_name="retours")
    libelle = models.CharField(max_length=200)
    quantite = models.PositiveIntegerField()
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=3)
    remis_en_stock = models.BooleanField(
        default=True, help_text="Faux pour un article défectueux ou fait sur mesure."
    )

    class Meta:
        verbose_name = "ligne d'avoir"

    def __str__(self):
        return f"{self.quantite} × {self.libelle}"


class Paiement(models.Model):
    """Règlement reçu : tout le prix en caisse, ou acompte puis solde pour une commande."""

    class Mode(models.TextChoices):
        CARTE = "carte", "Carte bancaire"
        ESPECES = "especes", "Espèces"
        CHEQUE = "cheque", "Chèque"

    vente = models.ForeignKey(Vente, on_delete=models.PROTECT, related_name="paiements")
    mode = models.CharField(max_length=20, choices=Mode.choices)
    montant = models.DecimalField(max_digits=14, decimal_places=3)
    recu_le = models.DateTimeField(default=timezone.now)
    recu_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )

    class Meta:
        verbose_name = "paiement"

    def __str__(self):
        return f"{self.get_mode_display()} {self.montant}"


class EtapeCommande(models.Model):
    """Passage d'une commande à une étape du suivi qualité, avec qui et quand (traçabilité)."""

    Etape = Etape

    vente = models.ForeignKey(Vente, on_delete=models.PROTECT, related_name="etapes")
    etape = models.CharField(max_length=16, choices=Etape.choices)
    observation = models.CharField(max_length=300, blank=True)
    le = models.DateTimeField(default=timezone.now)
    par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["le", "pk"]
        verbose_name = "étape de commande"
        verbose_name_plural = "étapes de commande"

    def __str__(self):
        return f"{self.vente} : {self.get_etape_display()}"


class PriseEnCharge(ModeleDeBase):
    """Part d'une vente payée par un organisme (CNAM, assurance, mutuelle) et non par le client.

    Elle vient en déduction de ce que doit le client ; refusée, elle redevient à sa charge.
    """

    class Statut(models.TextChoices):
        DEMANDEE = "demandee", "Demandée"
        ACCORDEE = "accordee", "Accordée"
        REGLEE = "reglee", "Réglée par l'organisme"
        REFUSEE = "refusee", "Refusée"

    vente = models.ForeignKey(Vente, on_delete=models.PROTECT, related_name="prises_en_charge")
    organisme = models.ForeignKey("crm.Organisme", on_delete=models.PROTECT, related_name="+")
    montant = models.DecimalField(max_digits=14, decimal_places=3)
    numero_dossier = models.CharField("n° de dossier", max_length=60, blank=True)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.DEMANDEE)
    saisie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["cree_le"]
        verbose_name = "prise en charge"
        verbose_name_plural = "prises en charge"

    def __str__(self):
        return f"{self.organisme} : {self.montant}"

    @property
    def magasin_id(self):
        """Pour les droits par magasin : celui de la vente."""
        return self.vente.magasin_id
