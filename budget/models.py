from django.db import models


class Utilisateur(models.Model):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    budgetMensuel = models.FloatField(default=0.0)

    class Meta:
        db_table = 'utilisateur'

    def __str__(self):
        return self.username


class Categorie(models.Model):
    nom = models.CharField(max_length=100)

    class Meta:
        db_table = 'categorie'
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.nom


class Transaction(models.Model):
    TYPE_CHOICES = [
        ('revenu', 'Revenu'),
        ('depense', 'Depense'),
    ]
    montant = models.FloatField()
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    date = models.DateField()
    description = models.TextField(blank=True, null=True)
    categorie = models.ForeignKey(Categorie, on_delete=models.SET_NULL, null=True, blank=True)
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE)

    class Meta:
        db_table = 'transaction'
        ordering = ['-date']

    def __str__(self):
        return f"{self.type} - {self.montant} MAD ({self.date})"


class Alerte(models.Model):
    NIVEAU_CHOICES = [
        ('vert', 'OK - Budget respecte'),
        ('orange', 'Attention - 80% budget atteint'),
        ('rouge', 'Budget depasse'),
    ]
    message = models.TextField()
    niveau = models.CharField(max_length=10, choices=NIVEAU_CHOICES)
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE)

    class Meta:
        db_table = 'alerte'

    def __str__(self):
        return f"[{self.niveau.upper()}] {self.message[:40]}"


class Statistique(models.Model):
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE)
    totalRevenus = models.FloatField(default=0.0)
    totalDepenses = models.FloatField(default=0.0)
    solde = models.FloatField(default=0.0)
    mois = models.IntegerField()
    annee = models.IntegerField()

    class Meta:
        db_table = 'statistique'

    def calculer_solde(self):
        self.solde = self.totalRevenus - self.totalDepenses
        self.save()

    def __str__(self):
        return f"Stats {self.utilisateur} - {self.mois}/{self.annee}"