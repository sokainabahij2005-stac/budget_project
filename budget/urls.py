from django.urls import path
from . import views

urlpatterns = [
    path('', views.accueil, name='accueil'),
    path('inscription/', views.inscription, name='inscription'),
    path('connexion/', views.connexion, name='connexion'),
    path('deconnexion/', views.deconnexion, name='deconnexion'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('transaction/', views.ajouter_transaction, name='ajouter_transaction'),
    path('chatbot/', views.chatbot, name='chatbot'),
    path('api/chatbot/', views.api_chatbot, name='api_chatbot'),
    
    # Admin
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-utilisateurs/', views.admin_utilisateurs, name='admin_utilisateurs'),
    path('admin-categories/', views.admin_categories, name='admin_categories'),
    path('admin-statistiques/', views.admin_statistiques, name='admin_statistiques'),
    path('admin-modifier-categorie/<int:cat_id>/', views.admin_modifier_categorie, name='admin_modifier_categorie'),
]