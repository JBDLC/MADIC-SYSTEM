# -*- coding: utf-8 -*-
"""Génération de rapports PDF et Excel."""
import os
from datetime import datetime, date
from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import cm
from database import db, RawData, Anomalie


def _date_filter(query, model, date_from=None, date_to=None):
    """Applique un filtre date sur une requête (colonne date_heure ou date)."""
    if date_from:
        col = getattr(model, 'date_heure', None) or getattr(model, 'date', None)
        if col is not None:
            query = query.filter(col >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        col = getattr(model, 'date_heure', None) or getattr(model, 'date', None)
        if col is not None:
            query = query.filter(col <= datetime.combine(date_to, datetime.max.time()))
    return query


def get_stats():
    """Retourne les statistiques pour le dashboard."""
    total_carburant = db.session.query(db.func.sum(RawData.quantite)).scalar() or 0
    
    top_machines = db.session.query(
        RawData.parc, db.func.sum(RawData.quantite).label('total')
    ).group_by(RawData.parc).order_by(db.desc('total')).limit(10).all()
    
    top_personnes = db.session.query(
        RawData.personne, db.func.sum(RawData.quantite).label('total')
    ).filter(RawData.personne != '').group_by(RawData.personne).order_by(db.desc('total')).limit(10).all()
    
    nb_anomalies = Anomalie.query.count()
    
    return {
        'total_carburant': total_carburant,
        'top_machines': top_machines,
        'top_personnes': top_personnes,
        'nb_anomalies': nb_anomalies,
    }


def get_consumption_by_machine(date_from=None, date_to=None):
    """Tableau des consommations par machine (optionnel: filtre par dates)."""
    q = db.session.query(
        RawData.parc,
        db.func.sum(RawData.quantite).label('quantite_totale'),
        db.func.count(RawData.id).label('nb_releves')
    )
    q = _date_filter(q, RawData, date_from, date_to)
    return q.group_by(RawData.parc).order_by(db.desc('quantite_totale')).all()


def get_consumption_by_person(date_from=None, date_to=None):
    """Tableau des consommations par personne (optionnel: filtre par dates)."""
    q = db.session.query(
        RawData.personne,
        db.func.sum(RawData.quantite).label('quantite_totale'),
        db.func.count(RawData.id).label('nb_releves')
    ).filter(RawData.personne != '')
    q = _date_filter(q, RawData, date_from, date_to)
    return q.group_by(RawData.personne).order_by(db.desc('quantite_totale')).all()


def get_anomalies_detail(date_from=None, date_to=None):
    """Tableau détaillé des anomalies (optionnel: filtre par dates)."""
    q = Anomalie.query
    q = _date_filter(q, Anomalie, date_from, date_to)
    return q.order_by(Anomalie.date.desc()).all()


def get_date_range():
    """Retourne (date_min, date_max) des données en base (en objet date ou str ISO)."""
    try:
        r = db.session.query(
            db.func.min(RawData.date_heure),
            db.func.max(RawData.date_heure)
        ).first()
        if not r or r[0] is None:
            return (None, None)
        dmin, dmax = r[0], r[1]
        # Convertir en date (gère datetime ou str)
        if hasattr(dmin, 'date'):
            dmin = dmin.date()
        elif isinstance(dmin, str) and len(dmin) >= 10:
            dmin = dmin[:10]
        if hasattr(dmax, 'date'):
            dmax = dmax.date()
        elif isinstance(dmax, str) and len(dmax) >= 10:
            dmax = dmax[:10]
        return (dmin, dmax)
    except Exception:
        return (None, None)


def generate_pdf(date_from=None, date_to=None):
    """Génère un rapport PDF et retourne le chemin du fichier (optionnel: filtre par dates)."""
    folder = current_app.config['REPORTS_FOLDER']
    filename = f"rapport_madic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(folder, filename)
    
    doc = SimpleDocTemplate(filepath, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []
    
    story.append(Paragraph("Rapport MADIC - Analyse Carburant", styles['Title']))
    story.append(Spacer(1, 12))
    sub = f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}"
    if date_from or date_to:
        sub += f" — Période : {date_from or '?'} à {date_to or '?'}"
    story.append(Paragraph(sub, styles['Normal']))
    story.append(Spacer(1, 24))
    
    # Consommations par machine
    story.append(Paragraph("1. Consommations par machine", styles['Heading2']))
    story.append(Spacer(1, 12))
    
    data_machines = [['Machine', 'Quantité totale', 'Nombre de relevés']]
    for row in get_consumption_by_machine(date_from, date_to):
        data_machines.append([str(row.parc), f"{row.quantite_totale:.2f}", str(row.nb_releves)])
    
    if len(data_machines) > 1:
        t1 = Table(data_machines)
        t1.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        story.append(t1)
    else:
        story.append(Paragraph("Aucune donnée.", styles['Normal']))
    
    story.append(Spacer(1, 24))
    
    # Consommations par personne
    story.append(Paragraph("2. Consommations par personne", styles['Heading2']))
    story.append(Spacer(1, 12))
    
    data_persons = [['Personne', 'Quantité totale', 'Nombre de relevés']]
    for row in get_consumption_by_person(date_from, date_to):
        data_persons.append([str(row.personne or '-'), f"{row.quantite_totale:.2f}", str(row.nb_releves)])
    
    if len(data_persons) > 1:
        t2 = Table(data_persons)
        t2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        story.append(t2)
    else:
        story.append(Paragraph("Aucune donnée.", styles['Normal']))
    
    story.append(Spacer(1, 24))
    
    # Anomalies
    story.append(Paragraph("3. Anomalies détectées", styles['Heading2']))
    story.append(Spacer(1, 12))
    
    anomalies = get_anomalies_detail(date_from, date_to)
    if anomalies:
        data_anom = [['Machine', 'Type', 'Date', 'Personne', 'Compteur avant', 'Compteur après', 'Détails']]
        for a in anomalies[:50]:  # Limiter à 50 pour le PDF
            data_anom.append([
                str(a.machine), str(a.type_anomalie),
                a.date.strftime('%d/%m/%Y %H:%M') if a.date else '-',
                str(a.personne or '-'),
                str(a.compteur_before or '-'), str(a.compteur_after or '-'),
                str((a.details or '')[:40])
            ])
        t3 = Table(data_anom, colWidths=[50, 70, 70, 60, 55, 55, 120])
        t3.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkred),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        story.append(t3)
        if len(anomalies) > 50:
            story.append(Paragraph(f"... et {len(anomalies) - 50} anomalies supplémentaires.", styles['Normal']))
    else:
        story.append(Paragraph("Aucune anomalie détectée.", styles['Normal']))
    
    doc.build(story)
    return filepath


def generate_excel(date_from=None, date_to=None):
    """Génère un rapport Excel et retourne le chemin du fichier (optionnel: filtre par dates)."""
    import pandas as pd
    
    folder = current_app.config['REPORTS_FOLDER']
    filename = f"rapport_madic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = os.path.join(folder, filename)
    
    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        # Par machine
        mach_data = [{'Machine': r.parc, 'Quantité totale': r.quantite_totale, 'Nb relevés': r.nb_releves} 
                     for r in get_consumption_by_machine(date_from, date_to)]
        pd.DataFrame(mach_data).to_excel(writer, sheet_name='Par machine', index=False)
        
        # Par personne
        pers_data = [{'Personne': r.personne or '-', 'Quantité totale': r.quantite_totale, 'Nb relevés': r.nb_releves} 
                     for r in get_consumption_by_person(date_from, date_to)]
        pd.DataFrame(pers_data).to_excel(writer, sheet_name='Par personne', index=False)
        
        # Anomalies
        anom = get_anomalies_detail(date_from, date_to)
        if anom:
            df_anom = pd.DataFrame([{
                'Machine': a.machine, 'Type': a.type_anomalie,
                'Date': a.date, 'Prev Date': a.prev_date,
                'Personne': a.personne,
                'Compteur before': a.compteur_before, 'Compteur after': a.compteur_after,
                'Quantité before': a.quantite_before, 'Quantité after': a.quantite_after,
                'Détails': a.details
            } for a in anom])
            df_anom.to_excel(writer, sheet_name='Anomalies', index=False)
    
    return filepath
