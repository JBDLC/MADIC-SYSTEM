"""Importeur CP30 (Excel) avec dedoublonnage incremental."""
import hashlib
from datetime import datetime

import pandas as pd

from database import db, CP30Data


EXPECTED_COLUMNS = [
    'Date du dernier RDV',
    'Date de péremption',
    'Site',
    'N°  de parc',
    'Demandeur',
    'Service',
    'Entreprise',
    'KM',
    'Statut',
]


def _clean_text(v):
    if pd.isna(v):
        return ''
    return str(v).strip()


def _parse_date(v):
    if pd.isna(v):
        return None
    try:
        d = pd.to_datetime(v, dayfirst=True, errors='coerce')
        if pd.isna(d):
            return None
        return d.date()
    except Exception:
        return None


def _parse_km(v):
    if pd.isna(v):
        return None
    try:
        if isinstance(v, (int, float)):
            return float(v)
        txt = str(v).replace(' ', '').replace(',', '.')
        return float(txt) if txt else None
    except Exception:
        return None


def _vehicle_type_from_parc(parc_ou_immat):
    p = _clean_text(parc_ou_immat).upper()
    return 'interne' if p.startswith('P') else 'prestataire'


def _build_import_key(payload):
    raw = "|".join([
        str(payload.get('date_dernier_rdv') or ''),
        str(payload.get('date_peremption') or ''),
        payload.get('site', ''),
        payload.get('parc_ou_immat', ''),
        payload.get('demandeur', ''),
        payload.get('service', ''),
        payload.get('entreprise', ''),
        str(payload.get('km') if payload.get('km') is not None else ''),
        payload.get('statut', ''),
    ])
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()


def _load_cp30_sheet(filepath):
    # Le fichier fourni contient l'entete en ligne 2 => header=1
    df = pd.read_excel(filepath, sheet_name=0, header=1)
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Colonnes CP30 manquantes: {missing}")
    return df


def import_cp30_excel(filepath, filename=''):
    """Importe les lignes CP30 avec dedoublonnage sur cle metier hash."""
    df = _load_cp30_sheet(filepath)
    existing_keys = {r[0] for r in CP30Data.query.with_entities(CP30Data.import_key).all()}
    to_insert = []

    for _, row in df.iterrows():
        payload = {
            'date_dernier_rdv': _parse_date(row.get('Date du dernier RDV')),
            'date_peremption': _parse_date(row.get('Date de péremption')),
            'site': _clean_text(row.get('Site')),
            'parc_ou_immat': _clean_text(row.get('N°  de parc')),
            'demandeur': _clean_text(row.get('Demandeur')),
            'service': _clean_text(row.get('Service')),
            'entreprise': _clean_text(row.get('Entreprise')),
            'km': _parse_km(row.get('KM')),
            'statut': _clean_text(row.get('Statut')),
        }
        if not payload['date_peremption'] and not payload['date_dernier_rdv']:
            continue
        payload['vehicle_type'] = _vehicle_type_from_parc(payload['parc_ou_immat'])
        payload['import_key'] = _build_import_key(payload)
        if payload['import_key'] in existing_keys:
            continue
        to_insert.append(CP30Data(
            date_dernier_rdv=payload['date_dernier_rdv'],
            date_peremption=payload['date_peremption'],
            site=payload['site'][:120],
            parc_ou_immat=payload['parc_ou_immat'][:80],
            demandeur=payload['demandeur'][:150],
            service=payload['service'][:150],
            entreprise=payload['entreprise'][:150],
            km=payload['km'],
            statut=payload['statut'][:80],
            vehicle_type=payload['vehicle_type'],
            import_key=payload['import_key'],
            source_filename=(filename or '')[:255],
            imported_at=datetime.utcnow(),
        ))
        existing_keys.add(payload['import_key'])

    nb_skipped = len(df) - len(to_insert)
    if to_insert:
        db.session.bulk_save_objects(to_insert)
    db.session.commit()
    return len(to_insert), nb_skipped
