# -*- coding: utf-8 -*-
"""Module pour le créateur d'indicateurs - agrégations flexibles des données MADIC."""
from datetime import datetime, date
from collections import defaultdict

from database import db, RawData, Anomalie


def _date_filter(query, model, date_from=None, date_to=None):
    """Applique un filtre date sur une requête."""
    col = getattr(model, 'date_heure', None) or getattr(model, 'date', None)
    if col is None:
        return query
    if date_from:
        query = query.filter(col >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        query = query.filter(col <= datetime.combine(date_to, datetime.max.time()))
    return query


def _truncate_date(dt, group_by):
    """Tronque une date selon la granularité (jour, semaine, mois, annee)."""
    if dt is None:
        return None
    d = dt.date() if hasattr(dt, 'date') else (dt[:10] if isinstance(dt, str) else dt)
    if isinstance(d, str) and len(d) >= 10:
        d = datetime.strptime(d[:10], '%Y-%m-%d').date()
    if group_by == 'jour':
        return d.isoformat()
    if group_by == 'semaine':
        # Lundi de la semaine
        from datetime import timedelta
        j = d.weekday()
        lundi = d - timedelta(days=j)
        return lundi.isoformat()
    if group_by == 'mois':
        return d.replace(day=1).isoformat()
    if group_by == 'annee':
        return date(d.year, 1, 1).isoformat()
    return d.isoformat()


def get_indicator_data(x_axis, x_date_group, y_metrics, serie_dim, date_from=None, date_to=None, serie_filter=None):
    """
    Retourne les données agrégées pour le graphique.
    
    x_axis: 'date' | 'parc' | 'personne' | 'produit' | 'type_anomalie'
    x_date_group: 'jour' | 'semaine' | 'mois' | 'annee' (si x_axis=date)
    y_metrics: liste de {'metric': ..., 'agg': ...}
    serie_dim: None | 'parc' | 'personne' | 'produit' (pour plusieurs courbes)
    serie_filter: liste optionnelle de valeurs à inclure (ex: ['Parc1','Parc2']). Si fournie, seules ces séries sont affichées.
    """
    result = defaultdict(lambda: defaultdict(float))
    series_keys = set()
    
    # Mapping colonnes RawData
    raw_col_map = {
        'quantite': RawData.quantite,
        'compteur': RawData.compteur,
        'parc': RawData.parc,
        'personne': RawData.personne,
        'produit': RawData.produit,
    }
    
    # Données carburant (RawData)
    if any(m['metric'] != 'nb_anomalies' for m in y_metrics):
        q = db.session.query(
            RawData.date_heure,
            RawData.parc,
            RawData.personne,
            RawData.produit,
            RawData.quantite,
            RawData.compteur,
        )
        q = _date_filter(q, RawData, date_from, date_to)
        rows = q.all()
        
        for r in rows:
            # Clé axe X
            if x_axis == 'date':
                x_key = _truncate_date(r.date_heure, x_date_group or 'jour')
            elif x_axis == 'parc':
                x_key = str(r.parc or '')
            elif x_axis == 'personne':
                x_key = str(r.personne or '(vide)')
            elif x_axis == 'produit':
                x_key = str(r.produit or '(vide)')
            else:
                x_key = '?'
            
            # Clé série (ou None pour une seule courbe)
            if serie_dim:
                if serie_dim == 'parc':
                    s_key = str(r.parc or '')
                elif serie_dim == 'personne':
                    s_key = str(r.personne or '(vide)')
                elif serie_dim == 'produit':
                    s_key = str(r.produit or '(vide)')
                else:
                    s_key = 'Global'
            else:
                s_key = '__global__'
            
            series_keys.add(s_key)
            
            # Agrégation des métriques
            for ym in y_metrics:
                if ym.get('metric') == 'nb_anomalies':
                    continue
                mid = ym.get('metric', 'quantite') + '_' + ym.get('agg', 'sum')
                val = 0
                if ym['metric'] == 'quantite':
                    val = float(r.quantite or 0)
                elif ym['metric'] == 'compteur':
                    val = float(r.compteur or 0)
                elif ym['metric'] == 'nb_releves':
                    val = 1
                
                if ym['agg'] == 'sum':
                    result[(x_key, s_key)][mid] += val
                elif ym['agg'] == 'avg':
                    result[(x_key, s_key)][mid] += val  # on va diviser par count après
                elif ym['agg'] == 'count' or ym['metric'] == 'nb_releves':
                    result[(x_key, s_key)][mid] += 1
                elif ym['agg'] == 'max':
                    cur = result[(x_key, s_key)].get(mid, 0)
                    result[(x_key, s_key)][mid] = max(cur, val)
    
    # Compter les rows pour avg
    counts = defaultdict(lambda: defaultdict(int))
    if any(m.get('agg') == 'avg' for m in y_metrics):
        q = db.session.query(
            RawData.date_heure,
            RawData.parc,
            RawData.personne,
            RawData.produit,
        )
        q = _date_filter(q, RawData, date_from, date_to)
        for r in q.all():
            if x_axis == 'date':
                x_key = _truncate_date(r.date_heure, x_date_group or 'jour')
            elif x_axis == 'parc':
                x_key = str(r.parc or '')
            elif x_axis == 'personne':
                x_key = str(r.personne or '(vide)')
            elif x_axis == 'produit':
                x_key = str(r.produit or '(vide)')
            else:
                x_key = '?'
            if serie_dim == 'parc':
                s_key = str(r.parc or '')
            elif serie_dim == 'personne':
                s_key = str(r.personne or '(vide)')
            elif serie_dim == 'produit':
                s_key = str(r.produit or '(vide)')
            else:
                s_key = '__global__'
            counts[(x_key, s_key)] += 1
    
    for (x_key, s_key), vals in result.items():
        c = counts.get((x_key, s_key), 0)
        for ym in y_metrics:
            if ym['metric'] == 'nb_anomalies':
                continue
            mid = ym['metric'] + '_' + ym.get('agg', 'sum')
            if ym.get('agg') == 'avg' and mid in vals and c > 0:
                vals[mid] = vals[mid] / c
    
    # Anomalies
    if any(m.get('metric') == 'nb_anomalies' for m in y_metrics):
        q = Anomalie.query
        q = _date_filter(q, Anomalie, date_from, date_to)
        anomalies = q.all()
        
        for a in anomalies:
            if x_axis == 'date':
                x_key = _truncate_date(a.date, x_date_group or 'jour')
            elif x_axis == 'parc':
                x_key = str(a.machine or '')
            elif x_axis == 'personne':
                x_key = str(a.personne or '(vide)')
            elif x_axis == 'produit':
                x_key = '(vide)'  # anomalie n'a pas produit
            elif x_axis == 'type_anomalie':
                x_key = str(a.type_anomalie or '')
            else:
                x_key = '?'
            
            if serie_dim == 'parc':
                s_key = str(a.machine or '')
            elif serie_dim == 'personne':
                s_key = str(a.personne or '(vide)')
            elif serie_dim == 'produit':
                s_key = '(vide)'
            else:
                s_key = '__global__'
            
            series_keys.add(s_key)
            result[(x_key, s_key)]['nb_anomalies_count'] += 1
    
    # Construire la réponse structurée
    x_labels = sorted(set(k[0] for k in result.keys()))
    series_list = sorted(s for s in series_keys if s != '__global__') or ['__global__']
    
    # Filtrer les séries si serie_filter fourni (sélectionner quelles machines/personnes/produits afficher)
    if serie_filter and len(serie_filter) > 0:
        allowed = set(serie_filter)
        series_list = [s for s in series_list if s in allowed]
    
    datasets = []
    colors = [
        '#3498db', '#27ae60', '#e74c3c', '#f39c12', '#9b59b6',
        '#1abc9c', '#e67e22', '#34495e', '#16a085', '#c0392b'
    ]
    
    for i, s_key in enumerate(series_list):
        for ym in y_metrics:
            agg = ym.get('agg', 'sum')
            met = ym.get('metric', 'quantite')
            mid = met + '_' + agg
            if met == 'nb_anomalies':
                mid = 'nb_anomalies_count'
            label = ym.get('label') or f"{met} ({agg})"
            if s_key != '__global__':
                label = f"{s_key} - {label}"
            
            data = []
            for x in x_labels:
                val = result.get((x, s_key), {}).get(mid, 0)
                data.append(round(val, 2) if isinstance(val, float) else val)
            
            color = colors[(i + len(datasets)) % len(colors)]
            datasets.append({
                'label': label,
                'data': data,
                'borderColor': color,
                'backgroundColor': color + '33',
                'tension': 0.2,
                'fill': False,
            })
    
    return {
        'labels': x_labels,
        'datasets': datasets,
    }


def get_available_values(dimension, date_from=None, date_to=None):
    """Retourne les valeurs distinctes pour une dimension (parc, personne, produit)."""
    q = db.session.query
    if dimension == 'parc':
        base = q(RawData.parc).distinct().filter(RawData.parc != '')
    elif dimension == 'personne':
        base = q(RawData.personne).distinct()
    elif dimension == 'produit':
        base = q(RawData.produit).distinct().filter(RawData.produit != '')
    else:
        return []
    base = _date_filter(base, RawData, date_from, date_to)
    rows = base.order_by(getattr(RawData, dimension)).all()
    if dimension == 'personne':
        return [r[0] if r[0] else '(vide)' for r in rows]
    return [r[0] for r in rows if r[0]]
