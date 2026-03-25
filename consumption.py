# -*- coding: utf-8 -*-
"""Règles de comptage « consommation carburant » (camions cuve vs prélèvement stock)."""
from config import STOCK_ROULANT_CUVE_IDS


def effective_quantite_conso_carburant(parc, quantite, cuve_num, camion_parcs, seuil_litres):
    """
    Quantité à inclure dans le total carburant « consommation ».
    - Machine normale : toute la quantité.
    - Camion cuve + prélèvement stock roulant (cuve 4,5,9,10) : consommation.
    - Camion cuve + quantité <= seuil : ravitailllement pour rouler → consommation.
    - Camion cuve + quantité > seuil + cuve fixe (hors stock roulant) : remplissage cuve mobile → 0.
    """
    q = float(quantite or 0)
    if parc not in camion_parcs:
        return q
    try:
        c = int(cuve_num) if cuve_num is not None else None
    except (TypeError, ValueError):
        c = None
    if c is not None and c in STOCK_ROULANT_CUVE_IDS:
        return q
    if q <= float(seuil_litres or 0):
        return q
    return 0.0
