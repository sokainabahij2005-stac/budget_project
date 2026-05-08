import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'budget_project.settings')
django.setup()

from django.contrib.auth.hashers import make_password
from budget.models import Utilisateur

# Supprimer ancien admin
Utilisateur.objects.filter(username='admin').delete()

# Creer admin avec budget fixe
admin = Utilisateur.objects.create(
    username='admin',
    email='admin@budgetapp.com',
    password=make_password('admin123'),
    budgetMensuel=5000.00
)
print("=" * 40)
print("ADMIN CREE")
print("-" * 40)
print("Email    : admin@budgetapp.com")
print("Password : admin123")
print("Budget   : 5000.00 MAD")
print("=" * 40)