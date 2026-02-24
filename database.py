# -*- coding: utf-8 -*-
"""Configuration et modèles de base de données pour MADIC (PostgreSQL / SQLite)."""
import os
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from config import DATABASE_URL, DATABASE_PATH, UPLOAD_FOLDER, REPORTS_FOLDER

# Créer les dossiers si nécessaire
for folder in [UPLOAD_FOLDER, REPORTS_FOLDER]:
    os.makedirs(folder, exist_ok=True)

db = SQLAlchemy()


def init_db(app):
    """Initialise la base de données avec l'application Flask."""
    if DATABASE_URL:
        app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True, 'pool_recycle': 300}
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DATABASE_PATH}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['REPORTS_FOLDER'] = REPORTS_FOLDER
    db.init_app(app)
    
    with app.app_context():
        db.create_all()


class RawData(db.Model):
    """Données brutes importées du fichier Excel (sans duplication)."""
    __tablename__ = 'raw_data'
    
    id = db.Column(db.Integer, primary_key=True)
    date_heure = db.Column(db.DateTime, nullable=False)
    parc = db.Column(db.String(50), nullable=False)  # N° Parc (machine)
    service_vehicule = db.Column(db.String(100))
    personne = db.Column(db.String(100))
    service_personne = db.Column(db.String(100))
    produit = db.Column(db.String(100))
    quantite = db.Column(db.Float, nullable=False)
    compteur = db.Column(db.Float, nullable=False)
    unite = db.Column(db.String(20))
    imported_at = db.Column(db.DateTime, default=datetime.utcnow)


class ProcessedData(db.Model):
    """Données traitées avec calculs (compteur_before, diff, etc.)."""
    __tablename__ = 'processed_data'
    
    id = db.Column(db.Integer, primary_key=True)
    raw_data_id = db.Column(db.Integer, db.ForeignKey('raw_data.id'))
    parc = db.Column(db.String(50), nullable=False)
    date_heure = db.Column(db.DateTime, nullable=False)
    prev_date_heure = db.Column(db.DateTime)  # Ligne précédente
    personne = db.Column(db.String(100))
    produit = db.Column(db.String(100))
    quantite = db.Column(db.Float)
    quantite_before = db.Column(db.Float)
    quantite_after = db.Column(db.Float)
    compteur = db.Column(db.Float)
    compteur_before = db.Column(db.Float)
    compteur_after = db.Column(db.Float)
    diff_compteur = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Anomalie(db.Model):
    """Anomalies détectées."""
    __tablename__ = 'anomalies'
    
    id = db.Column(db.Integer, primary_key=True)
    machine = db.Column(db.String(50), nullable=False)
    type_anomalie = db.Column(db.String(100), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    prev_date = db.Column(db.DateTime)
    personne = db.Column(db.String(100))
    compteur_before = db.Column(db.Float)
    compteur_after = db.Column(db.Float)
    quantite_before = db.Column(db.Float)
    quantite_after = db.Column(db.Float)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class HistoryPeriod(db.Model):
    """Périodes déjà importées (pour éviter les doublons)."""
    __tablename__ = 'history_periods'
    
    id = db.Column(db.Integer, primary_key=True)
    date_min = db.Column(db.Date, nullable=False)
    date_max = db.Column(db.Date, nullable=False)
    nb_lignes_importees = db.Column(db.Integer)
    filename = db.Column(db.String(255))
    imported_at = db.Column(db.DateTime, default=datetime.utcnow)
