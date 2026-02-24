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
}
