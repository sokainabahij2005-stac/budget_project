from django.contrib import admin

# Register your models here.

from .models import Utilisateur, Categorie, Transaction, Alerte, Statistique

admin.site.register(Utilisateur)
admin.site.register(Categorie)
admin.site.register(Transaction)
admin.site.register(Alerte)
admin.site.register(Statistique)