# -*- coding: utf-8 -*-
"""Script pour analyser la structure d'un fichier Excel MADIC.
Usage: py analyze_excel.py "chemin\vers\fichier.xls"
Fermez Excel avant de lancer si le fichier est ouvert."""
import sys
import os

def analyze(filepath):
    if not os.path.exists(filepath):
        print(f"Fichier introuvable: {filepath}")
        return
    
    print(f"Analyse de: {filepath}")
    print("=" * 60)
    
    import pandas as pd
    
    ext = filepath.lower().rsplit('.', 1)[-1] if '.' in filepath else ''
    engines = ['xlrd', 'openpyxl'] if ext == 'xls' else ['openpyxl', 'xlrd']
    
    for engine in engines:
        try:
            print(f"\nEngine {engine}:")
            for header in range(5):
                try:
                    df = pd.read_excel(filepath, engine=engine, header=header)
                    print(f"  Header row {header}: {list(df.columns)}")
                    print(f"  Shape: {df.shape}")
                    print(f"  Première ligne: {list(df.iloc[0].values) if len(df) > 0 else 'vide'}")
                    if df.shape[0] > 0 and df.shape[1] > 0:
                        print(f"\n  Aperçu (3 lignes):")
                        print(df.head(3).to_string())
                    break
                except Exception as e:
                    print(f"  Header {header}: erreur - {e}")
            break
        except Exception as e:
            print(f"  Erreur engine {engine}: {e}")
    
    print("\n" + "=" * 60)
    print("Test d'import MADIC...")
    try:
        from excel_importer import load_excel
        df = load_excel(filepath)
        print(f"OK! {len(df)} lignes importées.")
        print(df.head(3))
    except Exception as e:
        print(f"ERREUR import: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else r"c:\Users\jean.brunet-de-la-ch\Downloads\Transactions MADIC 26_01 au 16_02.xls"
    analyze(path)
