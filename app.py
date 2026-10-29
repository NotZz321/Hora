import os
import sys
import threading
import webbrowser
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))

from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, abort

import career as C
import suriyayatra_v3 as S
import excel_db as DB
from chart_svg import render as render_chart
from deities import DEITIES
from make_provinces import ROWS as PROVINCE_ROWS

app = Flask(__name__)
CHART_SIZE = 480
app.secret_key = 'hora-local-demo'
app.config['TEMPLATES_AUTO_RELOAD'] = True

THAI_MONTHS = ['มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
               'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม']


def _thai_sort_key(name):
    return name[1:] + name[0] if name[0] in 'เแโใไ' else name


PROVINCE_LIST = sorted(S.PROVINCES, key=_thai_sort_key)
PROVINCE_ISO = {row[0]: row[2] for row in PROVINCE_ROWS}


THAI_MONTHS_SHORT = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
                     'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']


@app.context_processor
def common():
    asset_version = max(os.stat(os.path.join(app.static_folder, name)).st_mtime_ns
                        for name in ('style.css', 'sky.js', 'dashboard.js'))
    return {'months': THAI_MONTHS, 'months_short': THAI_MONTHS_SHORT,
            'deities': DEITIES, 'asset_version': asset_version}


@app.route('/deities/<filename>')
def deity_image(filename):
    if filename not in {d['image'] for d in DEITIES.values()}:
        abort(404)
    return send_from_directory(os.path.join(app.root_path, 'image'), filename, max_age=86400)


@app.route('/')
def index():
    return render_template('index.html', provinces=PROVINCE_LIST,
                           form=request.args)


@app.route('/predict', methods=['POST'])
def predict():
    f = request.form
    try:
        day, month, year_be = int(f['day']), int(f['month']), int(f['year_be'])
        hh, mm = int(f['hh']), int(f['mm'])
        province = f['province']
        if province not in S.PROVINCES:
            raise ValueError('ไม่พบจังหวัด')
        if not 2400 <= year_be <= 2600:
            raise ValueError('ปี พ.ศ. ต้องอยู่ระหว่าง 2400–2600')
        date(year_be - 543, month, day)
    except (KeyError, ValueError) as e:
        msg = str(e) if 'พ.ศ.' in str(e) or 'จังหวัด' in str(e) else 'วันที่ไม่ถูกต้อง กรุณาตรวจอีกครั้ง'
        flash(msg)
        return redirect(url_for('index', **f))

    result = C.analyze(day, month, year_be, hh, mm, province)
    nickname = f.get('nickname', '').strip()
    warning, saved = None, False
    try:
        DB.save_chart(result, nickname)
        saved = True
    except DB.ExcelLockedError as e:
        warning = str(e)
    return render_template('result.html', r=result, svg=render_chart(result, size=CHART_SIZE),
                           nickname=nickname, saved=saved, warning=warning)


@app.route('/dashboard')
def dashboard():
    warning = None
    try:
        charts = DB.list_charts()
    except DB.ExcelLockedError as e:
        charts, warning = [], str(e)
    rows = []
    for c in charts:
        try:
            month = int(c.get('เดือนเกิด') or 0)
        except (TypeError, ValueError):
            month = 0
        rows.append({'c': c.get('อาชีพทำนาย_1') or '',
                     'm': month,
                     'p': PROVINCE_ISO.get(str(c.get('จังหวัดเกิด') or '').strip(), '')})
    data = {'rows': rows, 'th': {iso: th for th, iso in PROVINCE_ISO.items()}}
    return render_template('dashboard.html', data=data, warning=warning)


if __name__ == '__main__':
    DB.init_db()
    threading.Timer(1.0, lambda: webbrowser.open('http://127.0.0.1:5000')).start()
    app.run(debug=False, port=5000)
