# -*- coding: utf-8 -*-
"""Crée un fichier Excel d'exemple pour tester l'import MADIC."""
import pandas as pd
from datetime import datetime, timedelta
import os

# Format type "Transactions MADIC" (variantes de noms possibles)
cols = ['Date', 'Heure', 'N° Parc', 'Service véhicule', 'Personne', 
        'Service personne', 'Produit', 'Quantité', 'Compteur', 'Unité']

rows = []
base_date = datetime(2025, 1, 1)
parcs = ['V001', 'V002', 'V003']
personnes = ['Dupont J.', 'Martin P.', 'Bernard L.']

# Générer 30 jours de données
for i in range(30):
    d = base_date + timedelta(days=i)
    for j, parc in enumerate(parcs):
        compteur = 10000 + i * 150 + j * 50
        qty = 45.5 + (i % 5) * 2.3
        rows.append({
            'Date': d.date(),
            'Heure': f'08:{i%60:02d}:00',
            'N° Parc': parc,
            'Service véhicule': 'Fleet',
            'Personne': personnes[j % 3],
            'Service personne': 'Operations',
            'Produit': 'Diesel',
            'Quantité': round(qty, 2),
            'Compteur': compteur,
            'Unité': 'L'
        })

# Ajouter quelques anomalies pour les tests
rows.append({
    'Date': datetime(2025, 1, 15).date(),
    'Heure': '12:00:00',
    'N° Parc': 'V001',
    'Service véhicule': 'Fleet',
    'Personne': 'Dupont J.',
    'Service personne': 'Operations',
    'Produit': 'Diesel',
    'Quantité': 0,  # Zero quantity
    'Compteur': 11500,
    'Unité': 'L'
})

df = pd.DataFrame(rows)
out = os.path.join(os.path.dirname(__file__), 'exemple_madic.xlsx')
df.to_excel(out, index=False)
print(f"Fichier créé : {out}")
