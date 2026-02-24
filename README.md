# MADIC - Analyse Carburant

Application Flask pour importer, analyser et générer des rapports à partir des fichiers Excel MADIC.

## Installation

```bash
pip install -r requirements.txt
```

## Lancement

```bash
py app.py
```

Puis ouvrir **http://127.0.0.1:5000** dans le navigateur.

## Créer un fichier Excel de test

```bash
py create_sample_excel.py
```

Cela crée `exemple_madic.xlsx` que vous pouvez importer pour tester.

## Fonctionnalités

1. **Import Excel** : Colonnes attendues - Date, Heure, N° Parc, Service véhicule, Personne, Service personne, Produit, Quantité, Compteur, Unité
2. **Détection des doublons** : Les lignes déjà importées sont ignorées
3. **Import fractionné** : Import 1-15 janv. puis 16-31 janv. = mois complet sans doublons
4. **Anomalies** : Quantité 0, compteur qui baisse, saut >1000 km (configurable dans `config.py`)
5. **Rapports** : Export PDF et Excel

## Structure

- `app.py` : Application Flask principale
- `config.py` : Configuration (seuil saut km, chemins)
- `database.py` : Modèles SQLite (raw_data, processed_data, anomalies, history_periods)
- `excel_importer.py` : Import et dédoublonnage
- `processor.py` : Traitement et détection d'anomalies
- `reports.py` : Génération PDF/Excel
