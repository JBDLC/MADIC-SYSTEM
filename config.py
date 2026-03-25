# -*- coding: utf-8 -*-
"""Configuration de l'application MADIC."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Base de données : PostgreSQL en prod (DATABASE_URL), SQLite en local
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    # Vérifier que c'est une vraie URL (pas un nom comme "madic_system")
    if '://' not in DATABASE_URL:
        DATABASE_URL = None

DATABASE_PATH = os.path.join(BASE_DIR, 'madic_data.db')
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or os.path.join(BASE_DIR, 'uploads')
REPORTS_FOLDER = os.environ.get('REPORTS_FOLDER') or os.path.join(BASE_DIR, 'reports')

# Seuil paramétrable pour la détection du saut de compteur (en km)
MAX_COUNTER_JUMP = 1000

# Cuves (colonne Excel) : numéro → libellé et site
CUVE_LABELS = {
    1: 'Cuve GNR 35m3 LA PRAZ',
    2: 'Cuve ADB 5m3 LA PRAZ',
    3: 'Cuve GAZOIL 8m3 LA PRAZ',
    4: 'STOCK ROULANT 1 LA PRAZ',
    5: 'STOCK ROULANT 2 LA PRAZ',
    6: 'Cuve GNR 25m3 SMP',
    7: 'Cuve G0 10m3 SMP',
    8: 'Cuve ADB 6m3 SMP',
    9: 'STOCK ROULANT 1 SMP',
    10: 'STOCK ROULANT 2 SMP',
}
# Identifiants des stocks roulants (prélèvement = consommation pour la machine)
STOCK_ROULANT_CUVE_IDS = frozenset({4, 5, 9, 10})
# Sites dérivés du numéro de cuve (1–5 LA PRAZ, 6–10 SMP)
CUVE_SITE_LA_PRAZ_MAX = 5


def cuve_num_to_site(cuve_num):
    """Retourne 'LA PRAZ' ou 'SMP' ou None."""
    if cuve_num is None:
        return None
    try:
        n = int(cuve_num)
    except (TypeError, ValueError):
        return None
    if 1 <= n <= CUVE_SITE_LA_PRAZ_MAX:
        return 'LA PRAZ'
    if 6 <= n <= 10:
        return 'SMP'
    return None


def format_cuve_label(cuve_num):
    """Libellé affichage pour un numéro de cuve."""
    if cuve_num is None:
        return '(non renseigné)'
    try:
        n = int(cuve_num)
    except (TypeError, ValueError):
        return str(cuve_num)
    return CUVE_LABELS.get(n, f'Cuve {n}')

# Mots-clés pour identifier les colonnes (matching flexible - contains)
# Ordre de priorité : le premier match gagne
COLUMN_KEYWORDS = {
    'date': ['date', 'dat', 'jour'],
    'heure': ['heure', 'horaire', 'time', 'heure debut', 'heure fin', 'hr'],
    'parc': ['parc', 'véhicule', 'vehicule', 'immatriculation', 'n° parc', 'no parc', 'machine', 'engin', 'véhicule', 'matricule'],
    'service_vehicule': ['service véhicule', 'service vehicule', 'département', 'departement', 'service'],
    'personne': ['personne', 'conducteur', 'chauffeur', 'driver', 'employé', 'employe'],
    'service_personne': ['service personne', 'service personnes'],
    'produit': ['produit', 'product', 'carburant', 'fuel', 'gasoil', 'diesel', 'essence'],
    'quantite': ['quantité', 'quantite', 'qte', 'volume', 'litre', 'litres', 'consommation'],
    'compteur': ['compteur', 'odomètre', 'odometre', 'kilométrage', 'kilometrage', 'km', 'compte'],
    'unite': ['unité', 'unite', 'unit'],
    'cuve': ['cuve', 'cuve n', 'n° cuve', 'no cuve', 'numero cuve', 'numéro cuve', 'tank'],
}
