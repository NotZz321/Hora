"""เว็บผูกดวงทำนายกรอบอาชีพ (สุริยยาตร์) — ใช้ Excel เป็น database

รัน:  python app.py   แล้วเปิด http://127.0.0.1:5000
"""
import os
import sys
import threading
import webbrowser
from datetime import date

# ใช้ไลบรารีที่แนบมาในโฟลเดอร์ lib/ ก่อน → ไม่ต้อง pip install
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))

from flask import Flask, render_template, request, redirect, url_for, send_file, flash

import career as C
import suriyayatra_v3 as S
import excel_db as DB
from chart_svg import render as render_chart

app = Flask(__name__)
app.secret_key = 'hora-local-demo'

THAI_MONTHS = ['มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
               'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม']


def _thai_sort_key(name):
    # ย้ายสระหน้า (เ แ โ ใ ไ) ไปท้าย ให้เรียงตามพยัญชนะต้นแบบพจนานุกรม
    return name[1:] + name[0] if name[0] in 'เแโใไ' else name


PROVINCE_LIST = sorted(S.PROVINCES, key=_thai_sort_key)
ACTUAL_CHOICES = C.CAREER_GROUPS + ['นักศึกษา (ยังไม่เลือกสาย)', 'อื่น ๆ']


THAI_MONTHS_SHORT = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
                     'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']


@app.context_processor
def common():
    return {'months': THAI_MONTHS, 'months_short': THAI_MONTHS_SHORT}


@app.route('/')
def index():
    return render_template('index.html', provinces=PROVINCE_LIST, actual_choices=ACTUAL_CHOICES,
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
        date(year_be - 543, month, day)          # เช็กว่าวันที่มีจริง เช่น 31 เม.ย. ไม่มี
    except (KeyError, ValueError) as e:
        msg = str(e) if 'พ.ศ.' in str(e) or 'จังหวัด' in str(e) else 'วันที่ไม่ถูกต้อง กรุณาตรวจอีกครั้ง'
        flash(msg)
        return redirect(url_for('index', **f))

    result = C.analyze(day, month, year_be, hh, mm, province)
    nickname = f.get('nickname', '').strip()
    actual = f.get('actual', '').strip()
    try:
        chart_id = DB.save_chart(result, nickname, actual)
    except DB.ExcelLockedError as e:
        # บันทึกไม่ได้ แต่ยังแสดงผลให้ดู
        return render_template('result.html', r=result, svg=render_chart(result),
                               nickname=nickname, chart_id=None, warning=str(e))
    return redirect(url_for('show_chart', chart_id=chart_id))


@app.route('/chart/<int:chart_id>')
def show_chart(chart_id):
    row = DB.get_chart(chart_id)
    if row is None:
        flash(f'ไม่พบดวงหมายเลข {chart_id}')
        return redirect(url_for('history'))
    hh, mm = map(int, row['เวลาเกิด'].split(':'))
    d = row['วันเกิด']
    result = C.analyze(d.day, d.month, row['ปีเกิด_พศ'], hh, mm, row['จังหวัดเกิด'])
    return render_template('result.html', r=result, svg=render_chart(result),
                           nickname=row['ชื่อเล่น'] or '', chart_id=chart_id,
                           actual=row['สายงานจริง'], warning=None)


@app.route('/history')
def history():
    return render_template('history.html', rows=DB.list_charts())


@app.route('/download')
def download():
    DB.init_db()
    return send_file(DB.DB_PATH, as_attachment=True, download_name='hora.xlsx')


if __name__ == '__main__':
    DB.init_db()
    threading.Timer(1.0, lambda: webbrowser.open('http://127.0.0.1:5000')).start()
    app.run(debug=False, port=5000)
