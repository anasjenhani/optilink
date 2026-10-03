from decimal import Decimal

from django.conf import settings
from django.db import models

from core.managers import ParMagasinManager
from core.models import ModeleDeBase

MONTANT = {"max_digits": 14, "decimal_places": 3}


class DepenseCaisse(ModeleDeBase):
    """Petite dépense payée en espèces depuis la caisse du magasin, déduite à la clôture."""

    class Categorie(models.TextChoices):
        FOURNITURES = "fournitures", "Fournitures"
        ENTRETIEN = "entretien", "Entretien et nettoyage"
        TRANSPORT = "transport", "Transport et courses"
        RESTAURATION = "restauration", "Restauration"
        DIVERS = "divers", "Divers"

    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    categorie = models.CharField(max_length=20, choices=Categorie.choices)
    motif = models.CharField(max_length=200)
    beneficiaire = models.CharField("bénéficiaire", max_length=100, blank=True)
    montant = models.DecimalField(**MONTANT)
    payee_le = models.DateTimeField()
    saisie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    cloture = models.ForeignKey(
        "ClotureCaisse",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="depenses_caisse",
        help_text="Clôture qui l'a déduite ; vide tant que la caisse n'est pas clôturée.",
    )

    objects = ParMagasinManager()
    tous = models.Manager()

    class Meta:
        ordering = ["-payee_le"]
        verbose_name = "dépense de caisse"
        verbose_name_plural = "dépenses de caisse"

    def __str__(self):
        return f"{self.motif} {self.montant}"


class ClotureCaisse(ModeleDeBase):
    """Clôture de la caisse d'un magasin, envoyée à la finance pour vérification.

    Elle couvre tout ce qui a été encaissé depuis la clôture précédente. Le caissier compte la
    caisse ; OptiLink calcule ce qui était attendu et les écarts. La finance valide, ou rejette
    avec un commentaire : le caissier corrige alors son comptage et renvoie.
    """

    class Statut(models.TextChoices):
        ENVOYEE = "envoyee", "Envoyée à la finance"
        VALIDEE = "validee", "Validée"
        REJETEE = "rejetee", "Rejetée"

    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    numero = models.CharField(max_length=40, unique=True)
    debut = models.DateTimeField(null=True, blank=True, help_text="Vide pour la première.")
    fin = models.DateTimeField()
    devise = models.CharField(max_length=3)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.ENVOYEE)

    # Calculé par OptiLink sur la période.
    fond_initial = models.DecimalField(
        **MONTANT, help_text="Fond laissé en caisse à la clôture précédente."
    )
    encaisse_especes = models.DecimalField(**MONTANT)
    encaisse_cheques = models.DecimalField(**MONTANT)
    nombre_cheques = models.PositiveIntegerField()
    encaisse_cartes = models.DecimalField(**MONTANT)
    rembourse_especes = models.DecimalField(**MONTANT)
    rembourse_cheques = models.DecimalField(**MONTANT)
    rembourse_cartes = models.DecimalField(**MONTANT)
    depenses = models.DecimalField(**MONTANT)
    alimentations = models.DecimalField(
        **MONTANT, default=0, help_text="Espèces ajoutées au fond de caisse pendant la période."
    )

    # Compté par le caissier.
    especes_comptees = models.DecimalField(**MONTANT)
    cheques_comptes = models.DecimalField(**MONTANT)
    nombre_cheques_comptes = models.PositiveIntegerField()
    cartes_comptees = models.DecimalField(
        **MONTANT, help_text="Total des tickets du terminal de paiement."
    )
    fond_conserve = models.DecimalField(
        **MONTANT, help_text="Espèces laissées en caisse pour le lendemain."
    )
    commentaire_caissier = models.TextField(blank=True)
    cloturee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    verifiee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    verifiee_le = models.DateTimeField(null=True, blank=True)
    commentaire_finance = models.TextField(blank=True)

    # Où est parti l'argent une fois la clôture validée.
    depot_especes = models.ForeignKey(
        "OperationTresorerie",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="clotures_especes",
    )
    depot_cheques = models.ForeignKey(
        "OperationTresorerie",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="clotures_cheques",
    )
    encaissement_cartes = models.ForeignKey(
        "OperationTresorerie",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="clotures_cartes",
    )

    objects = ParMagasinManager()
    tous = models.Manager()

    class Meta:
        ordering = ["-fin"]
        verbose_name = "clôture de caisse"
        verbose_name_plural = "clôtures de caisse"
        permissions = [("valider_cloturecaisse", "Peut valider ou rejeter une clôture de caisse")]

    def __str__(self):
        return self.numero

    @property
    def especes_attendues(self) -> Decimal:
        return (
            self.fond_initial
            + self.alimentations
            + self.encaisse_especes
            - self.rembourse_especes
            - self.depenses
        )

    @property
    def cheques_attendus(self) -> Decimal:
        return self.encaisse_cheques - self.rembourse_cheques

    @property
    def cartes_attendues(self) -> Decimal:
        return self.encaisse_cartes - self.rembourse_cartes

    @property
    def ecart_especes(self) -> Decimal:
        return self.especes_comptees - self.especes_attendues

    @property
    def ecart_cheques(self) -> Decimal:
        return self.cheques_comptes - self.cheques_attendus

    @property
    def ecart_cartes(self) -> Decimal:
        return self.cartes_comptees - self.cartes_attendues

    @property
    def especes_a_remettre(self) -> Decimal:
        return self.especes_comptees - self.fond_conserve


class CompteTresorerie(ModeleDeBase):
    """Où se trouve l'argent d'une société : banque, coffre d'un magasin, caisse centrale."""

    class Type(models.TextChoices):
        BANQUE = "banque", "Compte bancaire"
        COFFRE = "coffre", "Coffre"
        CAISSE_CENTRALE = "caisse_centrale", "Caisse centrale"

    societe = models.ForeignKey(
        "reseau.Societe", on_delete=models.PROTECT, related_name="comptes", verbose_name="société"
    )
    type = models.CharField(max_length=20, choices=Type.choices)
    nom = models.CharField(max_length=100, help_text="Ex. « BIAT agence Aouina », « Coffre T01 ».")
    banque = models.CharField(max_length=100, blank=True)
    rib = models.CharField("RIB", max_length=34, blank=True)
    magasin = models.ForeignKey(
        "reseau.Magasin",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="Pour un coffre : le magasin où il se trouve.",
    )
    devise = models.CharField(max_length=3, default="TND")
    solde_initial = models.DecimalField(**MONTANT, default=0)
    est_actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["societe", "type", "nom"]
        verbose_name = "compte de trésorerie"
        verbose_name_plural = "comptes de trésorerie"

    def __str__(self):
        return self.nom


class OperationTresorerie(ModeleDeBase):
    """Mouvement d'argent : dépôt des clôtures, versement en banque, alimentation, frais…

    Une opération peut d'abord être prévue (prévision de versement), puis effectuée (bordereau
    remis à la banque), puis rapprochée quand la finance la retrouve sur le relevé bancaire.
    Seules les opérations effectuées ou rapprochées comptent dans les soldes.
    """

    class Type(models.TextChoices):
        DEPOT_ESPECES = "depot_especes", "Dépôt des espèces des clôtures"
        DEPOT_CHEQUES = "depot_cheques", "Remise des chèques à la banque"
        ENCAISSEMENT_CARTES = "encaissement_cartes", "Encaissement des cartes bancaires"
        TRANSFERT = "transfert", "Transfert entre comptes"
        ALIMENTATION_FOND = "alimentation_fond", "Alimentation du fond de caisse"
        OPERATION_BANCAIRE = "operation_bancaire", "Opération bancaire (frais, agios, autre)"

    class Statut(models.TextChoices):
        PREVUE = "prevue", "Prévue"
        EFFECTUEE = "effectuee", "Effectuée"
        RAPPROCHEE = "rapprochee", "Rapprochée avec la banque"

    societe = models.ForeignKey(
        "reseau.Societe", on_delete=models.PROTECT, related_name="+", verbose_name="société"
    )
    numero = models.CharField(max_length=40, unique=True)
    type = models.CharField(max_length=20, choices=Type.choices)
    statut = models.CharField(max_length=12, choices=Statut.choices)
    source = models.ForeignKey(
        CompteTresorerie, on_delete=models.PROTECT, null=True, blank=True, related_name="sorties"
    )
    destination = models.ForeignKey(
        CompteTresorerie, on_delete=models.PROTECT, null=True, blank=True, related_name="entrees"
    )
    magasin = models.ForeignKey(
        "reseau.Magasin",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="Caisse alimentée, pour une alimentation du fond.",
    )
    montant = models.DecimalField(**MONTANT)
    montant_credite = models.DecimalField(
        **MONTANT,
        null=True,
        blank=True,
        help_text="Cartes : montant réellement crédité par la banque (commission déduite).",
    )
    date_prevue = models.DateField(null=True, blank=True)
    date_operation = models.DateField(null=True, blank=True)
    date_valeur = models.DateField(null=True, blank=True, help_text="Date sur le relevé.")
    effectuee_le = models.DateTimeField(null=True, blank=True)
    reference = models.CharField(
        max_length=60, blank=True, help_text="N° de bordereau ou de pièce bancaire."
    )
    libelle = models.CharField(max_length=200, blank=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    rapprochee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "opération de trésorerie"
        verbose_name_plural = "opérations de trésorerie"
        permissions = [
            ("rapprocher_operationtresorerie", "Peut rapprocher une opération avec la banque")
        ]

    def __str__(self):
        return self.numero

    @property
    def commission(self) -> Decimal | None:
        if self.montant_credite is None:
            return None
        return self.montant - self.montant_credite
