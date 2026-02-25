# -*- coding: utf-8 -*-
"""Module d'import des fichiers Excel MADIC - détection automatique des colonnes."""
import re
import os
from datetime import datetime
import pandas as pd
from database import db, RawData, HistoryPeriod
from config import COLUMN_KEYWORDS


def _normalize(s):
    """Normalise une chaîne pour la comparaison."""
    if pd.isna(s):
        return ''
    s = str(s).strip().lower()
    s = re.sub(r'[éèêë]', 'e', s)
    s = re.sub(r'[àâä]', 'a', s)
    s = re.sub(r'[ùûü]', 'u', s)
    s = re.sub(r'[îï]', 'i', s)
    s = re.sub(r'[ôö]', 'o', s)
    s = re.sub(r'[ç]', 'c', s)
    s = re.sub(r'\s+', ' ', s)
    return s


def _column_contains(col_normalized, keywords):
    """Vérifie si la colonne matche un des mots-clés."""
    for kw in keywords:
        if kw in col_normalized:
            return True
    return False


def _find_column_index(df, col_std):
    """Trouve l'index de la colonne correspondant au type col_std."""
    keywords = COLUMN_KEYWORDS.get(col_std, [])
    for i, col in enumerate(df.columns):
        cn = _normalize(str(col))
        if _column_contains(cn, keywords):
            return i
    return None


def _find_date_heure_combined(df):
    """Cherche une colonne Date/Heure combinée."""
    for i, col in enumerate(df.columns):
        cn = _normalize(str(col))
        if 'date' in cn and ('heure' in cn or 'horaire' in cn or 'time' in cn):
            return i
    return None


def _map_columns(df):
    """Mappe les colonnes du fichier vers les noms standards. Retourne dict {col_std: col_index}."""
    mapping = {}
    used_indices = set()
    
    for col_std, keywords in COLUMN_KEYWORDS.items():
        idx = _find_column_index(df, col_std)
        if idx is not None and idx not in used_indices:
            mapping[col_std] = idx
            used_indices.add(idx)
    
    # Colonne Date/Heure combinée
    if 'date' not in mapping and 'heure' not in mapping:
        idx = _find_date_heure_combined(df)
        if idx is not None:
            mapping['date_heure_combined'] = idx
            used_indices.add(idx)
    
    return mapping, list(df.columns)


def _parse_float(val):
    """Convertit en float (gère virgules, espaces)."""
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(',', '.').replace(' ', '')
    s = re.sub(r'[^\d.\-]', '', s)
    try:
        return float(s) if s else 0.0
    except ValueError:
        return 0.0


def _parse_datetime(date_val, time_val=None):
    """Parse date et heure. Format français jj/mm/aaaa (dayfirst=True)."""
    if pd.isna(date_val):
        return None
    if isinstance(date_val, datetime):
        return date_val
    try:
        # dayfirst=True pour format français jj/mm/aaaa
        def _pd_date(v):
            return pd.to_datetime(v, dayfirst=True).to_pydatetime()
        # Colonne Date/Heure combinée
        if time_val is None and isinstance(date_val, str) and (' ' in date_val or 'T' in date_val):
            return _pd_date(date_val)
        if time_val is not None and not pd.isna(time_val):
            if isinstance(time_val, (datetime, pd.Timestamp)):
                d = pd.to_datetime(date_val, dayfirst=True).date()
                t = time_val.time() if hasattr(time_val, 'time') else datetime.min.time()
                return datetime.combine(d, t)
            time_str = str(time_val)
            if ':' in time_str:
                parts = re.split(r'[:\s.]+', time_str)
                h = int(float(parts[0])) if parts else 0
                m = int(float(parts[1])) if len(parts) > 1 else 0
                s = int(float(parts[2])) if len(parts) > 2 else 0
                d = pd.to_datetime(date_val, dayfirst=True).date()
                return datetime(d.year, d.month, d.day, min(h, 23), min(m, 59), min(s, 59))
        return _pd_date(date_val)
    except Exception:
        return None


def _load_as_text(filepath):
    """Charge un fichier .xls qui est en fait du CSV/text (faux .xls - export MADIC typique)."""
    encodings = ['utf-8', 'cp1252', 'latin-1', 'iso-8859-1']
    separators = ['\t', ';', ',']
    
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc, errors='ignore') as f:
                sample = f.read(2000)
            first_line = sample.split('\n')[0] if sample else ''
            first_lower = first_line.lower()
            if 'date' not in first_lower and 'parc' not in first_lower and 'heure' not in first_lower:
                continue
            for sep in separators:
                try:
                    kw = {'encoding': enc, 'sep': sep, 'header': 0, 'engine': 'python'}
                    try:
                        df = pd.read_csv(filepath, **kw, on_bad_lines='skip')
                    except TypeError:
                        df = pd.read_csv(filepath, **kw)
                    if df.shape[1] >= 3 and df.shape[0] >= 1:
                        df.columns = [str(c).strip() for c in df.columns]
                        mapping, _ = _map_columns(df)
                        if ('date' in mapping or 'date_heure_combined' in mapping) and 'parc' in mapping:
                            return (df, 'csv', 0)
                except Exception:
                    continue
        except Exception:
            continue
    return None


def _load_excel_raw(filepath):
    """Charge le fichier Excel, essaie plusieurs engines et header rows.
    Gère aussi les faux .xls (CSV/text renommés).
    Retourne le premier df pour lequel on trouve une mapping date+parc valide."""
    ext = filepath.lower().rsplit('.', 1)[-1] if '.' in os.path.basename(filepath) else ''
    
    # Fichier .xls : si xlrd échoue avec BOF/corrupt = faux .xls (CSV), essayer en premier
    if ext == 'xls':
        try:
            pd.read_excel(filepath, engine='xlrd', header=0)
        except Exception as e:
            if 'BOF' in str(e) or 'Unsupported format' in str(e) or 'corrupt' in str(e).lower() or 'Expected' in str(e):
                text_result = _load_as_text(filepath)
                if text_result:
                    return text_result[0], 'csv', 0
    
    engines = (['xlrd', 'openpyxl'] if ext == 'xls' else ['openpyxl', 'xlrd'])
    
    for engine in engines:
        try:
            for sheet in [0, 1]:  # Première et deuxième feuille
                for header in range(6):  # Essayer les 6 premières lignes comme header
                    try:
                        df = pd.read_excel(filepath, engine=engine, header=header, sheet_name=sheet)
                        if df.shape[1] < 3 or df.shape[0] < 1:
                            continue
                        mapping, _ = _map_columns(df)
                        has_date = 'date' in mapping or 'date_heure_combined' in mapping
                        has_parc = 'parc' in mapping
                        if has_date and has_parc:
                            return df, engine, header
                    except Exception:
                        continue
        except Exception:
            continue
    
    # Faux .xls : fichier CSV/text avec extension .xls (export MADIC typique)
    if ext == 'xls':
        text_result = _load_as_text(filepath)
        if text_result:
            return text_result[0], 'csv', 0
    
    # Dernier essai: header=0 et on lève une erreur explicite
    try:
        df = pd.read_excel(filepath, engine='xlrd' if ext == 'xls' else 'openpyxl')
        raise ValueError(
            f"Colonnes détectées: {list(df.columns)}. "
            "Le fichier doit contenir des colonnes comme: Date, N° Parc (ou Véhicule/Parc), Quantité, Compteur."
        )
    except ValueError:
        raise
    except Exception as e:
        # Si "Expected BOF" = faux .xls (CSV), réessayer en texte
        if 'BOF' in str(e) or 'Unsupported format' in str(e) or 'corrupt' in str(e).lower():
            text_result = _load_as_text(filepath)
            if text_result:
                return text_result[0], 'csv', 0
        raise ValueError(f"Impossible de lire le fichier. {e}")


def load_excel(filepath):
    """
    Charge un fichier Excel et retourne un DataFrame normalisé.
    Détection automatique des colonnes MADIC.
    """
    df, _, _ = _load_excel_raw(filepath)
    
    mapping, col_names = _map_columns(df)
    
    # Colonnes obligatoires : au minimum date (ou date_heure), parc, quantite, compteur
    has_date = 'date' in mapping or 'date_heure_combined' in mapping
    has_parc = 'parc' in mapping
    has_quantite = 'quantite' in mapping
    has_compteur = 'compteur' in mapping
    
    if not has_date or not has_parc:
        raise ValueError(
            f"Colonnes requises non trouvées. Colonnes détectées: {list(df.columns)}. "
            "Le fichier doit contenir au minimum: Date, N° Parc (ou Véhicule), Quantité, Compteur."
        )
    
    result = []
    
    for row_idx in range(len(df)):
        row = df.iloc[row_idx]
        
        # Date
        if 'date_heure_combined' in mapping:
            dt = _parse_datetime(row.iloc[mapping['date_heure_combined']])
        else:
            date_val = row.iloc[mapping['date']] if 'date' in mapping else None
            heure_val = row.iloc[mapping['heure']] if 'heure' in mapping else None
            dt = _parse_datetime(date_val, heure_val)
        
        if dt is None:
            continue
        
        # Parc - obligatoire
        parc_idx = mapping.get('parc')
        if parc_idx is None:
            continue
        parc = str(row.iloc[parc_idx]).strip()
        if not parc or parc.lower() in ('nan', 'none', ''):
            continue
        
        # Quantité et compteur - avec défaut 0
        quantite = _parse_float(row.iloc[mapping['quantite']]) if 'quantite' in mapping else 0.0
        compteur = _parse_float(row.iloc[mapping['compteur']]) if 'compteur' in mapping else 0.0
        
        def get_val(prop, maxlen=100):
            idx = mapping.get(prop)
            if idx is None:
                return ''
            v = row.iloc[idx]
            return str(v).strip()[:maxlen] if not pd.isna(v) else ''
        
        result.append({
            'date_heure': dt,
            'parc': parc[:50],
            'service_vehicule': get_val('service_vehicule', 100),
            'personne': get_val('personne', 100),
            'service_personne': get_val('service_personne', 100),
            'produit': get_val('produit', 100),
            'quantite': quantite,
            'compteur': compteur,
            'unite': get_val('unite', 20) or 'L',
        })
    
    out = pd.DataFrame(result)
    if out.empty:
        raise ValueError(
            "Aucune ligne valide trouvée. Vérifiez que le fichier contient des données "
            "avec Date, N° Parc, Quantité et Compteur renseignés."
        )
    return out


def get_existing_dates():
    """Retourne l'ensemble des (date_heure, parc) déjà en base. Un doublon = même date/heure pour la même machine."""
    rows = RawData.query.with_entities(RawData.date_heure, RawData.parc).all()
    return {(r[0], r[1]) for r in rows}


def import_excel(filepath, filename=''):
    """
    Importe un fichier Excel en base.
    - Ignore les lignes déjà présentes
    - Enregistre la période importée
    - Retourne (nb_imported, nb_skipped, date_min, date_max, errors)
    """
    df = load_excel(filepath)
    if df.empty:
        return 0, 0, None, None, ["Aucune donnée valide trouvée"]
    
    existing = get_existing_dates()
    to_insert = []
    
    for _, row in df.iterrows():
        key = (row['date_heure'], row['parc'])
        if key in existing:
            continue
        to_insert.append(RawData(
            date_heure=row['date_heure'],
            parc=row['parc'],
            service_vehicule=row.get('service_vehicule', ''),
            personne=row.get('personne', ''),
            service_personne=row.get('service_personne', ''),
            produit=row.get('produit', ''),
            quantite=row['quantite'],
            compteur=row['compteur'],
            unite=row.get('unite', ''),
        ))
        existing.add(key)  # évite doublons dans le même fichier
    
    nb_skipped = len(df) - len(to_insert)
    
    if to_insert:
        date_min = min(r.date_heure.date() for r in to_insert)
        date_max = max(r.date_heure.date() for r in to_insert)
        
        hp = HistoryPeriod(
            date_min=date_min, date_max=date_max,
            nb_lignes_importees=len(to_insert), filename=filename or 'Fichier Excel'
        )
        db.session.add(hp)
        db.session.flush()
        
        for r in to_insert:
            r.history_period_id = hp.id
        db.session.bulk_save_objects(to_insert)
        db.session.commit()
        
        return len(to_insert), nb_skipped, date_min, date_max, []
    
    db.session.commit()
    date_min = df['date_heure'].min().date() if len(df) else None
    date_max = df['date_heure'].max().date() if len(df) else None
    return 0, nb_skipped, date_min, date_max, []
