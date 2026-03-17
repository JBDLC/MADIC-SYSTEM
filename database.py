# -*- coding: utf-8 -*-
"""Configuration et modèles de base de données pour MADIC (PostgreSQL / SQLite)."""
import os
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from config import DATABASE_URL, DATABASE_PATH, UPLOAD_FOLDER, REPORTS_FOLDER, MAX_COUNTER_JUMP

# Créer les dossiers si nécessaire
for folder in [UPLOAD_FOLDER, REPORTS_FOLDER]:
    os.makedirs(folder, exist_ok=True)

db = SQLAlchemy()


def _migrate_anomalie_produit(app):
    """Ajoute la colonne produit à anomalies si elle n'existe pas."""
    from sqlalchemy import text
    try:
        with app.app_context():
            with db.engine.connect() as conn:
                uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
                if 'sqlite' in uri:
                    result = conn.execute(text("PRAGMA table_info(anomalies)"))
                    col_exists = 'produit' in [r[1] for r in result]
                else:
                    result = conn.execute(text("""
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='anomalies' AND column_name='produit'
                    """))
                    col_exists = result.fetchone() is not None
                if not col_exists:
                    if 'sqlite' in uri:
                        conn.execute(text("ALTER TABLE anomalies ADD COLUMN produit VARCHAR(100)"))
                    else:
                        conn.execute(text("ALTER TABLE anomalies ADD COLUMN produit VARCHAR(100)"))
                    conn.commit()
    except Exception:
        pass


def _migrate_user_anomalie_produits(app):
    """Ajoute la colonne produits_json à user_anomalie_config si elle n'existe pas."""
    from sqlalchemy import text
    try:
        with app.app_context():
            with db.engine.connect() as conn:
                uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
                if 'sqlite' in uri:
                    result = conn.execute(text("PRAGMA table_info(user_anomalie_config)"))
                    col_exists = 'produits_json' in [r[1] for r in result]
                else:
                    result = conn.execute(text("""
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='user_anomalie_config' AND column_name='produits_json'
                    """))
                    col_exists = result.fetchone() is not None
                if not col_exists:
                    if 'sqlite' in uri:
                        conn.execute(text("ALTER TABLE user_anomalie_config ADD COLUMN produits_json TEXT DEFAULT '[]'"))
                    else:
                        conn.execute(text("ALTER TABLE user_anomalie_config ADD COLUMN produits_json TEXT DEFAULT '[]'"))
                    conn.commit()
    except Exception:
        pass


def _migrate_add_history_period_id(app):
    """Ajoute la colonne history_period_id à raw_data si elle n'existe pas (migration)."""
    from sqlalchemy import text
    uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    is_sqlite = 'sqlite' in uri
    try:
        with app.app_context():
            with db.engine.connect() as conn:
                col_exists = False
                if is_sqlite:
                    result = conn.execute(text("PRAGMA table_info(raw_data)"))
                    col_exists = 'history_period_id' in [r[1] for r in result]
                else:
                    result = conn.execute(text("""
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='raw_data' AND column_name='history_period_id'
                    """))
                    col_exists = result.fetchone() is not None
                if not col_exists:
                    if is_sqlite:
                        conn.execute(text("ALTER TABLE raw_data ADD COLUMN history_period_id INTEGER"))
                    else:
                        conn.execute(text("ALTER TABLE raw_data ADD COLUMN history_period_id INTEGER REFERENCES history_periods(id)"))
                    conn.commit()
    except Exception:
        pass


def init_db(app):
    """Initialise la base de données avec l'application Flask."""
    if DATABASE_URL:
        app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True, 'pool_recycle': 300}
    elif os.environ.get('DATABASE_URL') and '://' not in os.environ.get('DATABASE_URL', ''):
        raise ValueError(
            "DATABASE_URL invalide. Sur Render : va dans PostgreSQL → ta base → Connections, "
            "copie l'Internal Database URL et colle-la dans Environment du Web Service (variable DATABASE_URL)."
        )
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DATABASE_PATH}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['REPORTS_FOLDER'] = REPORTS_FOLDER
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        _migrate_add_history_period_id(app)
        _migrate_anomalie_produit(app)
        _migrate_user_anomalie_produits(app)
        _ensure_admin_user()
        _ensure_anomalie_type_config()


def _ensure_admin_user():
    """Crée l'utilisateur admin si inexistant."""
    from werkzeug.security import generate_password_hash
    if User.query.filter_by(username='admin').first() is None:
        u = User(username='admin', password_hash=generate_password_hash('admin123'), role='admin')
        db.session.add(u)
        db.session.commit()


class RawData(db.Model):
    """Données brutes importées du fichier Excel (sans duplication)."""
    __tablename__ = 'raw_data'
    
    id = db.Column(db.Integer, primary_key=True)
    history_period_id = db.Column(db.Integer, db.ForeignKey('history_periods.id'), nullable=True)
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
    produit = db.Column(db.String(100))  # Produit concerné (lors du relevé)
    date = db.Column(db.DateTime, nullable=False)
    prev_date = db.Column(db.DateTime)
    personne = db.Column(db.String(100))
    compteur_before = db.Column(db.Float)
    compteur_after = db.Column(db.Float)
    quantite_before = db.Column(db.Float)
    quantite_after = db.Column(db.Float)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class User(UserMixin, db.Model):
    """Utilisateurs MADIC avec rôles (admin, utilisateur, visualisation)."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='utilisateur')  # admin, utilisateur, visualisation
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UserFilter(db.Model):
    """Filtres dashboard par utilisateur (machines, personnes)."""
    __tablename__ = 'user_filters'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    machines_json = db.Column(db.Text, default='[]')  # JSON array
    personnes_json = db.Column(db.Text, default='[]')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SavedIndicator(db.Model):
    """Configurations indicateurs enregistrées par utilisateur."""
    __tablename__ = 'saved_indicators'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(120), default='Sans nom')
    config_json = db.Column(db.Text, nullable=False)  # JSON: x_axis, x_date_group, serie_dim, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AnomalieTypeConfig(db.Model):
    """Catalogue des types d'anomalies (label, ordre)."""
    __tablename__ = 'anomalie_type_config'
    
    id = db.Column(db.Integer, primary_key=True)
    type_key = db.Column(db.String(50), unique=True, nullable=False)
    label = db.Column(db.String(120), nullable=False)
    sort_order = db.Column(db.Integer, default=0)


class UserAnomalieConfig(db.Model):
    """Configuration anomalies par utilisateur : détecter, inclure dans le décompte, produits ciblés."""
    __tablename__ = 'user_anomalie_config'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    type_key = db.Column(db.String(50), primary_key=True)
    enabled = db.Column(db.Boolean, default=True)  # Prendre en compte ce type
    include_in_count = db.Column(db.Boolean, default=True)  # Inclure dans le décompte
    produits_json = db.Column(db.Text, default='[]')  # JSON: produits pour cette alarme. [] = tous
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def _ensure_anomalie_type_config():
    """Crée le catalogue des types d'anomalies."""
    defaults = [
        ('zero_quantity', 'Zero quantity', 1),
        ('compteur_decreased', 'Compteur decreased', 2),
        ('jump', 'Saut compteur > seuil', 3),
        ('compteur_zero', 'Compteur zero', 4),
        ('compteur_identique', 'Compteur identique malgré plein', 5),
    ]
    for key, label, order in defaults:
        if AnomalieTypeConfig.query.filter_by(type_key=key).first() is None:
            c = AnomalieTypeConfig(type_key=key, label=label, sort_order=order)
            db.session.add(c)
    db.session.commit()


def get_anomalie_type_key(type_anomalie):
    """Mappe type_anomalie (string en base) vers type_key."""
    if not type_anomalie:
        return None
    s = str(type_anomalie).strip()
    if s == 'Zero quantity':
        return 'zero_quantity'
    if s == 'Compteur decreased':
        return 'compteur_decreased'
    if s and s.startswith('Jump >'):
        return 'jump'
    if s == 'Compteur zero':
        return 'compteur_zero'
    if s == 'Compteur identique malgré plein':
        return 'compteur_identique'
    return None


def ensure_user_anomalie_config(user_id):
    """Crée les configs utilisateur si inexistantes (valeurs par défaut)."""
    types_catalog = AnomalieTypeConfig.query.order_by(AnomalieTypeConfig.sort_order).all()
    for t in types_catalog:
        if UserAnomalieConfig.query.filter_by(user_id=user_id, type_key=t.type_key).first() is None:
            c = UserAnomalieConfig(user_id=user_id, type_key=t.type_key, enabled=True, include_in_count=True)
            db.session.add(c)
    db.session.commit()


def get_user_anomalie_configs(user_id):
    """Retourne la config anomalies de l'utilisateur, en la créant si besoin."""
    import json
    ensure_user_anomalie_config(user_id)
    configs = UserAnomalieConfig.query.filter_by(user_id=user_id).all()
    catalog = {t.type_key: t for t in AnomalieTypeConfig.query.all()}
    out = []
    for c in configs:
        cat = catalog.get(c.type_key)
        try:
            produits = json.loads(c.produits_json or '[]')
        except (TypeError, ValueError):
            produits = []
        out.append({
            'type_key': c.type_key,
            'label': cat.label if cat else c.type_key,
            'enabled': c.enabled,
            'include_in_count': c.include_in_count,
            'produits': produits if isinstance(produits, list) else [],
            'sort_order': cat.sort_order if cat else 0,
        })
    return sorted(out, key=lambda x: x['sort_order'])


def get_anomalie_filter_conditions(user_id, for_include_in_count=True):
    """
    Retourne la clause SQLAlchemy (or_) pour filtrer les anomalies selon la config user.
    for_include_in_count: True= décompte, False= affichage (enabled).
    Pour chaque type activé : type match AND (produits vide OU produit in produits).
    """
    from sqlalchemy import or_, and_
    if not user_id:
        return Anomalie.id < 0  # aucun
    ensure_user_anomalie_config(user_id)
    import json
    attr = 'include_in_count' if for_include_in_count else 'enabled'
    configs = UserAnomalieConfig.query.filter_by(user_id=user_id).filter(
        getattr(UserAnomalieConfig, attr) == True
    ).all()
    type_conds = {
        'zero_quantity': Anomalie.type_anomalie == 'Zero quantity',
        'compteur_decreased': Anomalie.type_anomalie == 'Compteur decreased',
        'jump': Anomalie.type_anomalie.like('Jump >%'),
        'compteur_zero': Anomalie.type_anomalie == 'Compteur zero',
        'compteur_identique': Anomalie.type_anomalie == 'Compteur identique malgré plein',
    }
    out = []
    for c in configs:
        type_cond = type_conds.get(c.type_key)
        if type_cond is None:
            continue
        try:
            produits = json.loads(c.produits_json or '[]')
        except (TypeError, ValueError):
            produits = []
        if not produits:
            out.append(type_cond)
        else:
            out.append(and_(type_cond, Anomalie.produit.in_(produits)))
    return or_(*out) if out else (Anomalie.id < 0)  # jamais vrai si vide


def get_anomalie_types_include_in_count(user_id):
    """Retourne les type_key dont include_in_count=True pour cet utilisateur."""
    ensure_user_anomalie_config(user_id)
    rows = UserAnomalieConfig.query.filter_by(
        user_id=user_id, include_in_count=True
    ).with_entities(UserAnomalieConfig.type_key).all()
    return {r[0] for r in rows}


def get_anomalie_types_enabled(user_id):
    """Retourne les type_key dont enabled=True pour cet utilisateur (types pris en compte)."""
    ensure_user_anomalie_config(user_id)
    rows = UserAnomalieConfig.query.filter_by(
        user_id=user_id, enabled=True
    ).with_entities(UserAnomalieConfig.type_key).all()
    return {r[0] for r in rows}


class SystemConfig(db.Model):
    """Paramètres globaux de l'application (seuil saut compteur, etc.)."""
    __tablename__ = 'system_config'
    
    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def get_jump_threshold():
    """Retourne le seuil de saut compteur (km) pour la détection. Par défaut MAX_COUNTER_JUMP."""
    try:
        row = SystemConfig.query.filter_by(key='jump_threshold').first()
        if row and row.value:
            return int(row.value)
    except (ValueError, TypeError):
        pass
    return MAX_COUNTER_JUMP


def set_jump_threshold(value):
    """Enregistre le seuil de saut compteur."""
    try:
        v = int(value)
        if v < 1:
            v = 1
    except (ValueError, TypeError):
        v = MAX_COUNTER_JUMP
    row = SystemConfig.query.filter_by(key='jump_threshold').first()
    if row:
        row.value = str(v)
    else:
        row = SystemConfig(key='jump_threshold', value=str(v))
        db.session.add(row)
    db.session.commit()
    return v


class HistoryPeriod(db.Model):
    """Périodes déjà importées (pour éviter les doublons)."""
    __tablename__ = 'history_periods'
    
    id = db.Column(db.Integer, primary_key=True)
    date_min = db.Column(db.Date, nullable=False)
    date_max = db.Column(db.Date, nullable=False)
    nb_lignes_importees = db.Column(db.Integer)
    filename = db.Column(db.String(255))
    imported_at = db.Column(db.DateTime, default=datetime.utcnow)
