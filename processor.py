# -*- coding: utf-8 -*-
"""Traitement des données et détection des anomalies."""
from datetime import datetime
from database import db, RawData, ProcessedData, Anomalie, get_jump_threshold, get_compteur_zero_excluded_products


def process_all_machines():
    """
    Traite toutes les machines : tri par date, calcul des diff, détection anomalies.
    Supprime et régénère processed_data et anomalies.
    """
    ProcessedData.query.delete()
    Anomalie.query.delete()
    
    parcs = db.session.query(RawData.parc).distinct().all()
    parcs = [p[0] for p in parcs]
    
    for parc in parcs:
        _process_machine(parc)
    
    db.session.commit()


def _process_machine(parc):
    """Traite une machine : tri, calculs, anomalies.
    Produits exclus (ex: ADB) : pas d'anomalie compteur zero, et on "saute" ces relevés
    pour le calcul des diff (on utilise les 2 relevés normaux qui entourent).
    """
    rows = RawData.query.filter_by(parc=parc).order_by(RawData.date_heure).all()
    excluded_products = get_compteur_zero_excluded_products()
    
    prev = None
    prev_normal = None  # Dernier relevé dont le produit n'est pas exclu (pour bridger)
    for row in rows:
        produit = (row.produit or '').strip()
        is_excluded = produit in excluded_products
        
        # Pour les comparaisons de compteur, on utilise prev_normal (saute les exclus)
        compteur_after = row.compteur
        if prev_normal is not None:
            compteur_before = prev_normal.compteur
            prev_date = prev_normal.date_heure
            diff_compteur = compteur_after - compteur_before
        else:
            compteur_before = row.compteur
            prev_date = prev.date_heure if prev else None
            diff_compteur = 0
        
        quantite_before = prev.quantite if prev else row.quantite
        quantite_after = row.quantite
        
        pd_row = ProcessedData(
            raw_data_id=row.id,
            parc=parc,
            date_heure=row.date_heure,
            prev_date_heure=prev_date,
            personne=row.personne,
            produit=row.produit,
            quantite=row.quantite,
            quantite_before=quantite_before,
            quantite_after=quantite_after,
            compteur=row.compteur,
            compteur_before=compteur_before,
            compteur_after=compteur_after,
            diff_compteur=diff_compteur,
        )
        db.session.add(pd_row)
        
        # Détection des anomalies (skip_compteur_zero pour produits exclus)
        anomalies = _detect_anomalies(
            parc=parc,
            date=row.date_heure,
            prev_date=prev_date,
            personne=row.personne,
            produit=row.produit,
            compteur_before=compteur_before,
            compteur_after=compteur_after,
            quantite_before=quantite_before,
            quantite_after=quantite_after,
            diff_compteur=diff_compteur,
            skip_compteur_zero=is_excluded,
        )
        # Pour les relevés exclus (ex: ADB), on ne crée aucune anomalie (compteur non fiable)
        if not is_excluded:
            for a in anomalies:
                db.session.add(a)
        
        prev = row
        if not is_excluded:
            prev_normal = row


def _detect_anomalies(parc, date, prev_date, personne, produit=None,
                      compteur_before=0, compteur_after=0, 
                      quantite_before=0, quantite_after=0, diff_compteur=0,
                      skip_compteur_zero=False):
    """Détecte les anomalies. skip_compteur_zero=True pour les produits exclus (ex: ADB)."""
    anomalies = []
    
    # 1. Zero quantity
    if quantite_after == 0:
        anomalies.append(Anomalie(
            machine=parc, type_anomalie='Zero quantity', produit=produit, date=date, prev_date=prev_date,
            personne=personne, compteur_before=compteur_before, compteur_after=compteur_after,
            quantite_before=quantite_before, quantite_after=quantite_after,
            details='Quantité égale à 0'
        ))
    
    # 2. Compteur decreased
    if prev_date is not None and compteur_after < compteur_before:
        anomalies.append(Anomalie(
            machine=parc, type_anomalie='Compteur decreased', produit=produit, date=date, prev_date=prev_date,
            personne=personne, compteur_before=compteur_before, compteur_after=compteur_after,
            quantite_before=quantite_before, quantite_after=quantite_after,
            details=f'Compteur a baissé de {compteur_before} à {compteur_after}'
        ))
    
    # 3. Jump > seuil
    threshold = get_jump_threshold()
    if prev_date is not None and diff_compteur > threshold:
        anomalies.append(Anomalie(
            machine=parc, type_anomalie=f'Jump >{threshold}', produit=produit, date=date, prev_date=prev_date,
            personne=personne, compteur_before=compteur_before, compteur_after=compteur_after,
            quantite_before=quantite_before, quantite_after=quantite_after,
            details=f'Saut de {diff_compteur} km (seuil: {threshold})'
        ))
    
    # 4. Compteur == 0 (sauf produits exclus comme ADB où le compteur n'est pas demandé)
    if compteur_after == 0 and not skip_compteur_zero:
        anomalies.append(Anomalie(
            machine=parc, type_anomalie='Compteur zero', produit=produit, date=date, prev_date=prev_date,
            personne=personne, compteur_before=compteur_before, compteur_after=compteur_after,
            quantite_before=quantite_before, quantite_after=quantite_after,
            details='Compteur à 0'
        ))
    
    # 5. Compteur identique malgré un plein (quantité > 0 mais diff = 0)
    if prev_date is not None and quantite_after > 0 and diff_compteur == 0:
        anomalies.append(Anomalie(
            machine=parc, type_anomalie='Compteur identique malgré plein', produit=produit, date=date, prev_date=prev_date,
            personne=personne, compteur_before=compteur_before, compteur_after=compteur_after,
            quantite_before=quantite_before, quantite_after=quantite_after,
            details=f'Quantité {quantite_after} mais compteur inchangé'
        ))
    
    return anomalies
