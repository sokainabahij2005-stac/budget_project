from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.db.models import Sum
from django.http import JsonResponse
from datetime import datetime
import json

from .models import Utilisateur, Transaction, Categorie, Statistique, Alerte


# ========== PAGE ACCUEIL ==========

def accueil(request):
    if request.session.get('utilisateur_id'):
        if request.session.get('is_admin'):
            return redirect('admin_dashboard')
        return redirect('dashboard')
    return render(request, 'accueil.html')


# ========== INSCRIPTION ==========

def inscription(request):
    if request.session.get('utilisateur_id'):
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email    = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password_confirm', '')
        budget   = request.POST.get('budgetMensuel', '').strip()

        erreurs = []

        if len(password) < 8:
            erreurs.append("Le mot de passe doit contenir au moins 8 caracteres.")

        if password != password2:
            erreurs.append("Les mots de passe ne correspondent pas.")

        if '@' not in email or '.' not in email:
            erreurs.append("Email invalide.")

        if Utilisateur.objects.filter(email=email).exists():
            erreurs.append("Cet email est deja utilise.")

        if Utilisateur.objects.filter(username=username).exists():
            erreurs.append("Ce nom d'utilisateur est deja pris.")

        # Verification mot de passe deja utilise par un autre compte
        mot_de_passe_existe = any(
            check_password(password, u.password)
            for u in Utilisateur.objects.all()
        )
        if mot_de_passe_existe:
            erreurs.append("Ce mot de passe est deja utilise par un autre compte. Veuillez en choisir un autre.")

        # Budget obligatoire et valide (minimum 1000 MAD)
        try:
            budget_val = float(budget)
            if budget_val < 1000:
                erreurs.append("Le budget mensuel doit etre d'au moins 1000 MAD.")
        except ValueError:
            erreurs.append("Veuillez entrer un budget mensuel valide.")

        if erreurs:
            return render(request, 'inscription.html', {
                'username': username,
                'email': email,
                'budgetMensuel': budget,
                'erreurs': erreurs,
            })

        user = Utilisateur.objects.create(
            username=username,
            email=email,
            password=make_password(password),
            budgetMensuel=budget_val
        )

        request.session['utilisateur_id'] = user.id
        request.session['is_admin'] = False
        return redirect('dashboard')

    return render(request, 'inscription.html')


# ========== CONNEXION ==========

def connexion(request):
    if request.session.get('utilisateur_id'):
        return redirect('dashboard')

    erreur = None

    if request.method == 'POST':
        email    = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        is_admin_login = request.POST.get('is_admin') == 'on'

        try:
            user = Utilisateur.objects.get(email=email)
        except Utilisateur.DoesNotExist:
            erreur = "Email ou mot de passe incorrect."
            return render(request, 'connexion.html', {'erreur': erreur})

        if not check_password(password, user.password):
            erreur = "Email ou mot de passe incorrect."
            return render(request, 'connexion.html', {'erreur': erreur})

        if is_admin_login:
            if user.username != 'admin':
                erreur = "Vous n'etes pas administrateur."
                return render(request, 'connexion.html', {'erreur': erreur})
            request.session['utilisateur_id'] = user.id
            request.session['is_admin'] = True
            return redirect('admin_dashboard')

        request.session['utilisateur_id'] = user.id
        request.session['is_admin'] = False
        return redirect('dashboard')

    return render(request, 'connexion.html')


# ========== DECONNEXION ==========

def deconnexion(request):
    request.session.flush()
    return redirect('accueil')


# ========== DASHBOARD UTILISATEUR ==========

def dashboard(request):
    user_id = request.session.get('utilisateur_id')
    if not user_id:
        return redirect('accueil')

    user = Utilisateur.objects.get(id=user_id)
    now  = datetime.now()

    # === SOMME UNIQUEMENT DU MOIS ACTUEL ===
    total_revenus_mois = Transaction.objects.filter(
        utilisateur=user,
        type='revenu',
        date__month=now.month,
        date__year=now.year
    ).aggregate(total=Sum('montant'))['total'] or 0

    total_depenses_mois = Transaction.objects.filter(
        utilisateur=user,
        type='depense',
        date__month=now.month,
        date__year=now.year
    ).aggregate(total=Sum('montant'))['total'] or 0

    solde_mois = total_revenus_mois - total_depenses_mois

    # Mettre à jour ou créer les stats du mois actuel
    stats, _ = Statistique.objects.get_or_create(
        utilisateur=user,
        mois=now.month,
        annee=now.year,
        defaults={
            'totalRevenus': total_revenus_mois,
            'totalDepenses': total_depenses_mois,
            'solde': solde_mois
        }
    )
    # Synchroniser au cas où
    stats.totalRevenus = total_revenus_mois
    stats.totalDepenses = total_depenses_mois
    stats.solde = solde_mois
    stats.save()

    # Courbe mensuelle (toute l'année pour le graphique)
    depenses_par_mois = []
    for m in range(1, 13):
        total = Transaction.objects.filter(
            utilisateur=user,
            type='depense',
            date__month=m,
            date__year=now.year
        ).aggregate(total=Sum('montant'))['total'] or 0
        depenses_par_mois.append(float(total))

    # Camembert depenses par categorie (toute l'année pour le graphique)
    depenses_categorie = Transaction.objects.filter(
        utilisateur=user,
        type='depense',
        date__year=now.year
    ).values('categorie__nom').annotate(total=Sum('montant')).order_by('-total')

    # Revenus par categorie (toute l'année pour le graphique)
    revenus_categorie = Transaction.objects.filter(
        utilisateur=user,
        type='revenu',
        date__year=now.year
    ).values('categorie__nom').annotate(total=Sum('montant')).order_by('-total')

    # === ALERTES UNIQUEMENT DU MOIS ACTUEL ===
    alertes = []
    if user.budgetMensuel > 0:
        depenses_total = total_depenses_mois
        budget = user.budgetMensuel

        if depenses_total > budget:
            alertes.append({
                'niveau': 'rouge',
                'message': f'ALERTE ROUGE ! Budget depasse ! Depenses: {depenses_total:.2f} MAD / Budget: {budget:.2f} MAD'
            })
            Alerte.objects.get_or_create(
                utilisateur=user,
                niveau='rouge',
                defaults={'message': 'Budget depasse !'}
            )
        elif depenses_total > budget * 0.8:
            alertes.append({
                'niveau': 'orange',
                'message': f'ATTENTION ! Vous avez atteint {depenses_total/budget*100:.0f}% de votre budget.'
            })
            Alerte.objects.get_or_create(
                utilisateur=user,
                niveau='orange',
                defaults={'message': '80% du budget atteint'}
            )
        else:
            alertes.append({
                'niveau': 'vert',
                'message': f'Budget respecte. Depenses: {depenses_total:.2f} MAD / {budget:.2f} MAD'
            })

    context = {
        'utilisateur': user,
        'stats': stats,
        'alertes': alertes,
        'depenses_par_mois': depenses_par_mois,
        'depenses_categorie': list(depenses_categorie),
        'revenus_categorie': list(revenus_categorie),
        'now': now,
        'total_revenus_mois': total_revenus_mois,
        'total_depenses_mois': total_depenses_mois,
        'solde_mois': solde_mois,
    }
    return render(request, 'dashboard.html', context)


# ========== AJOUTER TRANSACTION ==========

def ajouter_transaction(request):
    user_id = request.session.get('utilisateur_id')
    if not user_id:
        return redirect('accueil')

    user = Utilisateur.objects.get(id=user_id)

    if request.method == 'POST':
        montant    = float(request.POST.get('montant', 0))
        type_trans = request.POST.get('type')
        cat_id     = request.POST.get('categorie')
        desc       = request.POST.get('description', '')
        date_str   = request.POST.get('date')

        cat = Categorie.objects.get(id=cat_id) if cat_id else None

        Transaction.objects.create(
            montant=montant,
            type=type_trans,
            date=date_str,
            description=desc,
            categorie=cat,
            utilisateur=user
        )

        now = datetime.now()
        stats, _ = Statistique.objects.get_or_create(
            utilisateur=user,
            mois=now.month,
            annee=now.year,
            defaults={'totalRevenus': 0, 'totalDepenses': 0, 'solde': 0}
        )

        if type_trans == 'revenu':
            stats.totalRevenus += montant
        else:
            stats.totalDepenses += montant

        stats.solde = stats.totalRevenus - stats.totalDepenses
        stats.save()

        return redirect('dashboard')

    categories = Categorie.objects.all()
    return render(request, 'ajouter_transaction.html', {'categories': categories})


# ========== CHATBOT PAGE ==========

def chatbot(request):
    user_id = request.session.get('utilisateur_id')
    if not user_id:
        return redirect('accueil')
    return render(request, 'chatbot.html')


# ========== CHATBOT API ==========

def api_chatbot(request):
    user_id = request.session.get('utilisateur_id')
    if not user_id:
        return JsonResponse({'reponse': 'Connectez-vous d\'abord.'})

    data    = json.loads(request.body)
    message = data.get('message', '').lower().strip()
    user    = Utilisateur.objects.get(id=user_id)
    now     = datetime.now()

    stats = Statistique.objects.filter(
        utilisateur=user,
        mois=now.month,
        annee=now.year
    ).first()

    # --- SOLDE ---
    if 'solde' in message:
        if stats:
            return JsonResponse({'reponse': f"Ton solde du mois est de {stats.solde:.2f} MAD."})
        return JsonResponse({'reponse': "Aucune donnee disponible pour ce mois."})

    # --- REVENUS CE MOIS ---
    if message in ['revenus ce mois', 'mes revenus ce mois', 'revenu ce mois']:
        total = Transaction.objects.filter(
            utilisateur=user, type='revenu',
            date__month=now.month, date__year=now.year
        ).aggregate(total=Sum('montant'))['total'] or 0
        return JsonResponse({'reponse': f"Tes revenus ce mois : {total:.2f} MAD."})

    # --- REVENUS PAR CATEGORIE ---
    if message in ['revenus par categorie', 'revenu par categorie', 'mes revenus par categorie']:
        rev_cat = Transaction.objects.filter(
            utilisateur=user, type='revenu'
        ).values('categorie__nom').annotate(total=Sum('montant')).order_by('-total')
        if not rev_cat:
            return JsonResponse({'reponse': "Aucun revenu enregistre par categorie."})
        reponse = "Revenus par categorie :\n"
        for r in rev_cat:
            nom = r['categorie__nom'] or 'Sans categorie'
            reponse += f"- {nom} : {r['total']:.2f} MAD\n"
        return JsonResponse({'reponse': reponse})

    # --- DEPENSES CE MOIS ---
    if message in ['depenses ce mois', 'mes depenses ce mois', 'depense ce mois']:
        total = Transaction.objects.filter(
            utilisateur=user, type='depense',
            date__month=now.month, date__year=now.year
        ).aggregate(total=Sum('montant'))['total'] or 0
        return JsonResponse({'reponse': f"Tes depenses ce mois : {total:.2f} MAD."})

    # --- DEPENSES PAR CATEGORIE ---
    if message in ['depenses par categorie', 'depense par categorie', 'mes depenses par categorie']:
        dep_cat = Transaction.objects.filter(
            utilisateur=user, type='depense'
        ).values('categorie__nom').annotate(total=Sum('montant')).order_by('-total')
        if not dep_cat:
            return JsonResponse({'reponse': "Aucune depense enregistree par categorie."})
        reponse = "Depenses par categorie :\n"
        for d in dep_cat:
            nom = d['categorie__nom'] or 'Sans categorie'
            reponse += f"- {nom} : {d['total']:.2f} MAD\n"
        return JsonResponse({'reponse': reponse})

    # --- CONSEIL ---
    if 'conseil' in message:
        if stats and user.budgetMensuel > 0:
            ratio = stats.solde / user.budgetMensuel
            if ratio > 0.2:
                return JsonResponse({'reponse': "Tu epargnes bien ! Continue comme ca."})
            else:
                return JsonResponse({'reponse': "Attention ! Tu approches la limite de ton budget. Reduisez vos depenses."})
        return JsonResponse({'reponse': "Definissez un budget mensuel pour recevoir des conseils."})

    # --- NON RECONNU ---
    return JsonResponse({
        'reponse': "Je n'ai pas compris. Demandez parmi les options ci-dessous :\n\n"
                   "💰 Revenus ce mois\n"
                   "📊 Revenus par categorie\n"
                   "💸 Depenses ce mois\n"
                   "📈 Depenses par categorie\n"
                   "🏦 Solde\n"
                   "💡 Conseil"
    })


# ========== ADMIN DASHBOARD ==========

def admin_dashboard(request):
    if not request.session.get('is_admin'):
        return redirect('accueil')

    context = {
        'nb_users':        Utilisateur.objects.count(),
        'nb_categories':   Categorie.objects.count(),
        'nb_transactions': Transaction.objects.count(),
    }
    return render(request, 'admin_dashboard.html', context)


# ========== ADMIN UTILISATEURS ==========

def admin_utilisateurs(request):
    if not request.session.get('is_admin'):
        return redirect('accueil')

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        Utilisateur.objects.filter(id=user_id).exclude(username='admin').delete()
        return redirect('admin_utilisateurs')

    users = Utilisateur.objects.all()
    return render(request, 'admin_utilisateurs.html', {'users': users})


# ========== ADMIN CATEGORIES ==========

def admin_categories(request):
    if not request.session.get('is_admin'):
        return redirect('accueil')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'ajouter':
            nom = request.POST.get('nom')
            Categorie.objects.create(nom=nom)

        elif action == 'supprimer':
            cat_id = request.POST.get('cat_id')
            Categorie.objects.filter(id=cat_id).delete()

        return redirect('admin_categories')

    categories = Categorie.objects.all()
    return render(request, 'admin_categories.html', {'categories': categories})


def admin_modifier_categorie(request, cat_id):
    if not request.session.get('is_admin'):
        return redirect('accueil')

    cat = get_object_or_404(Categorie, id=cat_id)

    if request.method == 'POST':
        cat.nom = request.POST.get('nom')
        cat.save()
        return redirect('admin_categories')

    return render(request, 'admin_modifier_categorie.html', {'cat': cat})


# ========== ADMIN STATISTIQUES ==========

def admin_statistiques(request):
    if not request.session.get('is_admin'):
        return redirect('accueil')

    all_stats = []
    for user in Utilisateur.objects.all():
        for s in Statistique.objects.filter(utilisateur=user).order_by('-annee', '-mois'):
            all_stats.append({
                'user':     user.username,
                'mois':     s.mois,
                'annee':    s.annee,
                'revenus':  s.totalRevenus,
                'depenses': s.totalDepenses,
                'solde':    s.solde,
            })

    total_revenus  = Transaction.objects.filter(type='revenu').aggregate(total=Sum('montant'))['total'] or 0
    total_depenses = Transaction.objects.filter(type='depense').aggregate(total=Sum('montant'))['total'] or 0

    context = {
        'all_stats':      all_stats,
        'total_revenus':  total_revenus,
        'total_depenses': total_depenses,
        'solde_global':   total_revenus - total_depenses,                          
    }
    return render(request, 'admin_statistiques.html', context)
