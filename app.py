# -*- coding: utf-8 -*-
"""
MADIC - Application Flask d'analyse des données carburant.
Lancer avec : py app.py
"""
import io
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session
from werkzeug.utils import secure_filename

from config import UPLOAD_FOLDER
from database import init_db, db, RawData, ProcessedData, Anomalie, HistoryPeriod
from excel_importer import import_excel
from processor import process_all_machines
from reports import get_stats, get_consumption_by_machine, get_consumption_by_person, get_anomalies_detail, get_date_range, generate_pdf, generate_excel, get_all_machines_for_filter, get_all_personnes_for_filter, get_machine_detail, get_person_detail
from indicators import get_indicator_data, get_available_values

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or os.urandom(24).hex()
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max

ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

init_db(app)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def safe_filename(filename):
    """Gère les noms de fichiers avec accents ou caractères spéciaux."""
    s = secure_filename(filename)
    if not s:
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'xls'
        import uuid
        s = f"import_{uuid.uuid4().hex[:8]}.{ext}"
    return s


@app.route('/reset-data', methods=['POST'])
def reset_data():
    """Vide toutes les données pour permettre une réimportation propre (corrige les dates mal parsées)."""
    try:
        Anomalie.query.delete()
        ProcessedData.query.delete()
        RawData.query.delete()
        HistoryPeriod.query.delete()
        db.session.commit()
        flash('Données réinitialisées. Vous pouvez réimporter votre fichier Excel (les dates seront correctement interprétées en jj/mm/aaaa).', 'success')
    except Exception as e:
        flash(f'Erreur : {str(e)}', 'error')
    return redirect(url_for('index'))


@app.route('/', methods=['GET', 'POST'])
def index():
    """Page d'accueil / Dashboard. Le filtre reste figé (session) jusqu'à modification par l'utilisateur."""
    machine_filter = None
    person_filter = None
    if request.method == 'POST':
        machine_filter = request.form.getlist('machines')
        person_filter = request.form.getlist('personnes')
        session['dashboard_filter'] = {'machines': machine_filter, 'personnes': person_filter}
        return redirect(url_for('index'))
    if request.args.get('clear_filter'):
        session.pop('dashboard_filter', None)
        return redirect(url_for('index'))
    filter_data = session.get('dashboard_filter')
    if filter_data:
        machine_filter = filter_data.get('machines') or []
        person_filter = filter_data.get('personnes') or []
    stats = get_stats(machine_filter=machine_filter if machine_filter else None,
                     person_filter=person_filter if person_filter else None)
    all_machines = get_all_machines_for_filter()
    all_personnes = get_all_personnes_for_filter()
    has_filter = bool(machine_filter or person_filter)
    return render_template('index.html',
        stats=stats,
        all_machines=all_machines,
        all_personnes=all_personnes,
        selected_machines=set(machine_filter or []),
        selected_personnes=set(person_filter or []),
        has_filter=has_filter)


def _do_import(filepath, filename):
    """Exécute l'import et le traitement."""
    nb_imported, nb_skipped, date_min, date_max, errors = import_excel(filepath, filename)
    if errors:
        raise ValueError('; '.join(errors))
    if nb_imported > 0:
        process_all_machines()
    return nb_imported, nb_skipped, date_min, date_max


@app.route('/importer-excel', methods=['GET', 'POST'])
def importer_excel():
    """Import d'un fichier Excel (upload ou chemin)."""
    if request.method == 'GET':
        return redirect(url_for('index'))
    
    # Option 1: Import par chemin (contourne les blocages upload)
    path_from_form = (request.form.get('filepath') or '').strip()
    if path_from_form and os.path.isfile(path_from_form):
        ext = path_from_form.lower().rsplit('.', 1)[-1] if '.' in path_from_form else ''
        if ext in ALLOWED_EXTENSIONS:
            try:
                nb_imported, nb_skipped, date_min, date_max = _do_import(path_from_form, os.path.basename(path_from_form))
                if nb_imported > 0:
                    msg = f'{nb_imported} lignes importées'
                    if nb_skipped:
                        msg += f', {nb_skipped} doublons ignorés'
                    msg += f'. Période : {date_min} à {date_max}.'
                    flash(msg, 'success')
                elif nb_skipped > 0:
                    flash(f'Toutes les lignes ({nb_skipped}) étaient déjà présentes.', 'warning')
                else:
                    flash('Aucune donnée valide trouvée.', 'warning')
                return redirect(url_for('index'))
            except Exception as e:
                flash(f'Erreur : {str(e)}', 'error')
                return redirect(url_for('index'))
        else:
            flash('Format non autorisé. Utilisez .xlsx ou .xls', 'error')
            return redirect(url_for('index'))
    
    # Option 2: Upload classique
    if 'file' not in request.files:
        flash('Aucun fichier. Glissez-déposez ou collez le chemin complet du fichier.', 'error')
        return redirect(url_for('index'))
    
    file = request.files['file']
    if file.filename == '':
        flash('Aucun fichier sélectionné.', 'error')
        return redirect(url_for('index'))
    
    if not allowed_file(file.filename):
        flash('Format non autorisé. Utilisez .xlsx ou .xls', 'error')
        return redirect(url_for('index'))
    
    filename = safe_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    try:
        file.save(filepath)
    except Exception as e:
        flash(f'Impossible de sauvegarder le fichier (antivirus?). Collez le chemin dans le champ ci-dessous : {e}', 'error')
        return redirect(url_for('index'))
    
    try:
        nb_imported, nb_skipped, date_min, date_max = _do_import(filepath, filename)
        if nb_imported > 0:
            msg = f'{nb_imported} lignes importées'
            if nb_skipped:
                msg += f', {nb_skipped} doublons ignorés'
            msg += f'. Période : {date_min} à {date_max}.'
            flash(msg, 'success')
        elif nb_skipped > 0:
            flash(f'Toutes les lignes ({nb_skipped}) étaient déjà présentes.', 'warning')
        else:
            flash('Aucune donnée valide trouvée.', 'warning')
    except Exception as e:
        flash(f'Erreur : {str(e)}', 'error')
    finally:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass
    
    return redirect(url_for('index'))


@app.route('/download-template')
def download_template():
    """Télécharge un modèle Excel vide avec les colonnes attendues et des exemples."""
    import pandas as pd
    cols = ['Date', 'Heure', 'N° Parc', 'Service véhicule', 'Personne',
            'Service personne', 'Produit', 'Quantité', 'Compteur', 'Unité']
    rows = [
        {'Date': '01/02/2025', 'Heure': '08:30:00', 'N° Parc': 'H56-001', 'Service véhicule': 'Fleet',
         'Personne': 'Dupont', 'Service personne': 'Opérations', 'Produit': 'Diesel',
         'Quantité': 45.5, 'Compteur': 125000, 'Unité': 'L'},
        {'Date': '02/02/2025', 'Heure': '14:15:00', 'N° Parc': 'H56-002', 'Service véhicule': 'Fleet',
         'Personne': 'Martin', 'Service personne': 'Opérations', 'Produit': 'Diesel',
         'Quantité': 52.3, 'Compteur': 87500, 'Unité': 'L'},
    ]
    df = pd.DataFrame(rows, columns=cols)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, sheet_name='Transactions')
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name='modele_madic.xlsx',
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.route('/gestion-imports')
def gestion_imports():
    """Page de gestion des imports Excel."""
    imports_list = HistoryPeriod.query.order_by(HistoryPeriod.imported_at.desc()).all()
    import_counts = {}
    for hp in imports_list:
        n = RawData.query.filter_by(history_period_id=hp.id).count()
        import_counts[hp.id] = n
    return render_template('gestion_imports.html', imports_list=imports_list, import_counts=import_counts)


@app.route('/imports/<int:import_id>/supprimer', methods=['POST'])
def supprimer_import(import_id):
    """Supprime un import et met à jour les données du site."""
    hp = HistoryPeriod.query.get_or_404(import_id)
    nb_linked = RawData.query.filter_by(history_period_id=import_id).count()
    if nb_linked == 0:
        flash("Cet import n'a pas de données liées (import ancien). Utilisez 'Réinitialiser les données' pour tout effacer.", 'warning')
        db.session.delete(hp)
        db.session.commit()
        return redirect(url_for('gestion_imports'))
    try:
        RawData.query.filter_by(history_period_id=import_id).delete()
        db.session.delete(hp)
        db.session.commit()
        process_all_machines()
        flash(f'Import supprimé ({nb_linked} lignes retirées). Les données du site ont été mises à jour.', 'success')
    except Exception as e:
        flash(f'Erreur lors de la suppression : {str(e)}', 'error')
    return redirect(url_for('gestion_imports'))


@app.route('/indicateurs')
def indicateurs():
    """Page créateur d'indicateurs - graphiques personnalisables."""
    date_min, date_max = get_date_range()
    def _to_iso(d):
        if d is None:
            return ''
        if hasattr(d, 'isoformat'):
            return d.isoformat()
        return str(d)[:10] if d else ''
    return render_template('indicateurs.html',
        date_min_str=_to_iso(date_min),
        date_max_str=_to_iso(date_max))


@app.route('/api/indicateurs/data')
def api_indicateurs_data():
    """API retournant les données agrégées pour le graphique (JSON)."""
    x_axis = request.args.get('x_axis', 'date')
    x_date_group = request.args.get('x_date_group', 'mois')
    serie_dim = request.args.get('serie_dim') or None
    if serie_dim == '':
        serie_dim = None
    
    y_metrics_raw = request.args.get('y_metrics', 'quantite|sum')
    y_metrics = []
    for part in y_metrics_raw.split(';'):
        part = part.strip()
        if not part:
            continue
        sp = part.split('|')
        if len(sp) >= 2:
            y_metrics.append({'metric': sp[0], 'agg': sp[1]})
        else:
            y_metrics.append({'metric': 'quantite', 'agg': 'sum'})
    if not y_metrics:
        y_metrics = [{'metric': 'quantite', 'agg': 'sum'}]
    
    date_from = date_to = None
    try:
        df = request.args.get('date_from', '')
        dt = request.args.get('date_to', '')
        if df:
            date_from = datetime.strptime(df, '%Y-%m-%d').date()
        if dt:
            date_to = datetime.strptime(dt, '%Y-%m-%d').date()
    except ValueError:
        pass
    
    serie_filter_raw = request.args.get('serie_filter', '')  # machines, produits, personnes à inclure (séparés par virgule)
    serie_filter = [v.strip() for v in serie_filter_raw.split(',') if v.strip()] if serie_filter_raw else None
    
    try:
        data = get_indicator_data(x_axis, x_date_group, y_metrics, serie_dim, date_from, date_to, serie_filter)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/indicateurs/values/<dimension>')
def api_indicateurs_values(dimension):
    """API retournant les valeurs disponibles pour une dimension (parc, personne, produit)."""
    if dimension not in ('parc', 'personne', 'produit'):
        return jsonify([])
    date_from = date_to = None
    try:
        if request.args.get('date_from'):
            date_from = datetime.strptime(request.args.get('date_from'), '%Y-%m-%d').date()
        if request.args.get('date_to'):
            date_to = datetime.strptime(request.args.get('date_to'), '%Y-%m-%d').date()
    except ValueError:
        pass
    values = get_available_values(dimension, date_from, date_to)
    return jsonify(values)


@app.route('/detail/machine')
def machine_detail():
    """Page détail d'une machine avec graphiques et données."""
    parc = request.args.get('parc')
    if not parc:
        flash('Machine non spécifiée.', 'error')
        return redirect(url_for('index'))
    date_from = date_to = None
    try:
        df = request.args.get('date_from', '')
        dt = request.args.get('date_to', '')
        if df:
            date_from = datetime.strptime(df, '%Y-%m-%d').date()
        if dt:
            date_to = datetime.strptime(dt, '%Y-%m-%d').date()
    except ValueError:
        pass
    detail = get_machine_detail(parc, date_from, date_to)
    detail['by_date_chart'] = [[str(d.dt) if hasattr(d, 'dt') else d[0], float(d.total) if hasattr(d, 'total') else d[1]] for d in (detail.get('by_date') or [])]
    detail['by_personne_chart'] = [[str(p[0]) or '-', float(p[1]) if len(p) > 1 else 0] for p in (detail.get('by_personne') or [])]
    detail['anomalies_json'] = [{'type_anomalie': a.type_anomalie} for a in (detail.get('anomalies') or [])]
    date_min, date_max = get_date_range()
    def _to_iso(d):
        if d is None:
            return ''
        return d.isoformat() if hasattr(d, 'isoformat') else str(d)[:10]
    return render_template('detail_machine.html',
        detail=detail,
        date_min_str=_to_iso(date_min),
        date_max_str=_to_iso(date_max))


@app.route('/detail/personne')
def personne_detail():
    """Page détail d'une personne avec graphiques et données."""
    nom = request.args.get('nom')
    if not nom:
        flash('Personne non spécifiée.', 'error')
        return redirect(url_for('index'))
    date_from = date_to = None
    try:
        df = request.args.get('date_from', '')
        dt = request.args.get('date_to', '')
        if df:
            date_from = datetime.strptime(df, '%Y-%m-%d').date()
        if dt:
            date_to = datetime.strptime(dt, '%Y-%m-%d').date()
    except ValueError:
        pass
    detail = get_person_detail(nom, date_from, date_to)
    detail['by_date_chart'] = [[str(d.dt) if hasattr(d, 'dt') else d[0], float(d.total) if hasattr(d, 'total') else d[1]] for d in (detail.get('by_date') or [])]
    detail['by_machine_chart'] = [[str(m[0]) or '-', float(m[1]) if len(m) > 1 else 0] for m in (detail.get('by_machine') or [])]
    detail['anomalies_json'] = [{'type_anomalie': a.type_anomalie} for a in (detail.get('anomalies') or [])]
    date_min, date_max = get_date_range()
    def _to_iso(d):
        if d is None:
            return ''
        return d.isoformat() if hasattr(d, 'isoformat') else str(d)[:10]
    return render_template('detail_personne.html',
        detail=detail,
        date_min_str=_to_iso(date_min),
        date_max_str=_to_iso(date_max))


@app.route('/rapports')
def rapports():
    """Page des rapports détaillés avec filtre par dates."""
    date_from_s = request.args.get('date_from', '')
    date_to_s = request.args.get('date_to', '')
    date_from = date_to = None
    try:
        if date_from_s:
            date_from = datetime.strptime(date_from_s, '%Y-%m-%d').date()
        if date_to_s:
            date_to = datetime.strptime(date_to_s, '%Y-%m-%d').date()
    except ValueError:
        pass
    date_min, date_max = get_date_range()
    # Fallback: si aucune date mais des données, prendre sur une requête directe
    if (date_min is None or date_max is None) and RawData.query.first():
        first = RawData.query.order_by(RawData.date_heure.asc()).first()
        last = RawData.query.order_by(RawData.date_heure.desc()).first()
        if first:
            date_min = date_min or (first.date_heure.date() if hasattr(first.date_heure, 'date') else str(first.date_heure)[:10])
        if last:
            date_max = date_max or (last.date_heure.date() if hasattr(last.date_heure, 'date') else str(last.date_heure)[:10])
    def _to_iso(d):
        if d is None:
            return ''
        if hasattr(d, 'isoformat'):
            return d.isoformat()
        return str(d)[:10] if d else ''
    date_min_str = _to_iso(date_min)
    date_max_str = _to_iso(date_max)
    def _fmt_display(s):
        if not s or len(s) < 10:
            return s
        p = s.replace('/', '-').split('-')
        return f"{p[2]}/{p[1]}/{p[0]}" if len(p) == 3 else s
    date_range_display = f"du {_fmt_display(date_min_str)} au {_fmt_display(date_max_str)}" if date_min_str and date_max_str else "Aucune donnée importée"
    date_from_display = _fmt_display(date_from_s) if date_from_s else ''
    date_to_display = _fmt_display(date_to_s) if date_to_s else ''
    machines = get_consumption_by_machine(date_from, date_to)
    personnes = get_consumption_by_person(date_from, date_to)
    anomalies = get_anomalies_detail(date_from, date_to)
    return render_template('rapports.html',
        machines=machines, personnes=personnes, anomalies=anomalies,
        date_from=date_from_s, date_to=date_to_s,
        date_from_display=date_from_display, date_to_display=date_to_display,
        date_min_str=date_min_str, date_max_str=date_max_str,
        date_range_display=date_range_display)


@app.route('/download/<format>')
def download_report(format):
    """Télécharge le rapport PDF ou Excel (avec filtre dates si fourni)."""
    if format not in ('pdf', 'excel'):
        flash('Format non valide.', 'error')
        return redirect(url_for('rapports'))
    
    date_from = date_to = None
    try:
        df = request.args.get('date_from', '')
        dt = request.args.get('date_to', '')
        if df:
            date_from = datetime.strptime(df, '%Y-%m-%d').date()
        if dt:
            date_to = datetime.strptime(dt, '%Y-%m-%d').date()
    except ValueError:
        pass
    
    try:
        if format == 'pdf':
            filepath = generate_pdf(date_from, date_to)
        else:
            filepath = generate_excel(date_from, date_to)
        
        return send_file(filepath, as_attachment=True, download_name=os.path.basename(filepath))
    except Exception as e:
        flash(f'Erreur génération rapport : {str(e)}', 'error')
        return redirect(url_for('rapports'))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    if os.environ.get('RENDER'):
        app.run(host='0.0.0.0', port=port)
    else:
        print("MADIC SYSTEM - Serveur démarré.")
        print("  → http://127.0.0.1:5000")
        app.run(debug=debug, host='127.0.0.1', port=port, threaded=True)
