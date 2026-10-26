"""ใช้ไฟล์ Excel (data/hora.xlsx) เป็น database

โครงสร้างออกแบบให้ต่อ Tableau ได้ทันที
  sheet "charts"  : 1 แถว = 1 ดวง (ข้อมูลหลัก ใช้ทำสถิติ/กราฟ)
  sheet "planets" : 1 แถว = ดาว 1 ดวงของ 1 ดวงชาตา (long format, เชื่อมกับ charts ด้วย chart_id)
"""
import os
import sys
from datetime import datetime, date
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'hora.xlsx')

CHART_COLS = [
    'chart_id', 'บันทึกเมื่อ', 'ชื่อเล่น',
    'วันเกิด', 'ปีเกิด_พศ', 'เดือนเกิด', 'เวลาเกิด', 'ชั่วโมงเกิด', 'จังหวัดเกิด',
    'ลัคนา', 'ลัคนา_องศา', 'ชาวราศี',
    'ตนุลัคน์', 'ตนุลัคน์_ภพ', 'ตนุเศษ', 'ตนุเศษ_ภพ',
    'ภพกัมมะ_ราศี', 'ดาวกัมมะ', 'ดาวกัมมะ_ภพ', 'ดาวกัมมะ_ตำแหน่ง', 'ดาวกัมมะ_คุณภาพ',
    'อาชีพทำนาย_1', 'อาชีพทำนาย_2', 'อาชีพทำนาย_3',
    'สายงานจริง', 'ทำนายตรงอันดับ1', 'ทำนายตรงใน3อันดับ',
]
PLANET_COLS = ['chart_id', 'ดาว_เลข', 'ดาว', 'ราศี', 'ราศี_ลำดับ', 'องศาในราศี',
               'ลองจิจูด', 'ภพ', 'ตำแหน่ง']


class ExcelLockedError(Exception):
    """ไฟล์ Excel ถูกเปิดค้างอยู่ในโปรแกรม Excel จึงบันทึกไม่ได้"""


def _style_header(ws, cols):
    ws.append(cols)
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='5B3E8F')
        cell.alignment = Alignment(horizontal='center')
    ws.freeze_panes = 'A2'
    for i, name in enumerate(cols, 1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = max(12, len(name) + 4)


def init_db():
    """สร้างไฟล์ Excel พร้อมหัวตาราง ถ้ายังไม่มี"""
    if os.path.exists(DB_PATH):
        return
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    wb = Workbook()
    ws = wb.active; ws.title = 'charts'
    _style_header(ws, CHART_COLS)
    _style_header(wb.create_sheet('planets'), PLANET_COLS)
    wb.save(DB_PATH)


def _save(wb):
    try:
        wb.save(DB_PATH)
    except PermissionError:
        raise ExcelLockedError('ไฟล์ hora.xlsx เปิดค้างอยู่ใน Excel กรุณาปิดไฟล์แล้วลองใหม่')


def save_chart(result, nickname='', actual=''):
    """บันทึกผลจาก career.analyze() ลง Excel คืน chart_id"""
    init_db()
    try:
        wb = load_workbook(DB_PATH)
    except PermissionError:
        raise ExcelLockedError('ไฟล์ hora.xlsx เปิดค้างอยู่ใน Excel กรุณาปิดไฟล์แล้วลองใหม่')
    ws, wp = wb['charts'], wb['planets']
    ids = [r[0] for r in ws.iter_rows(min_row=2, max_col=1, values_only=True)
           if isinstance(r[0], int)]
    chart_id = max(ids, default=0) + 1   # ไม่ซ้ำแม้มีคนลบแถวใน Excel

    i, k = result['input'], result['karma']
    top = [t['group'] for t in result['top_careers']] + ['', '', '']
    pair_bad = any(not p['good'] for p in k['pairs'])
    match1 = (actual == top[0]) if actual else None
    match3 = (actual in top[:3]) if actual else None

    ws.append([
        chart_id, datetime.now().replace(microsecond=0), nickname,
        date(i['year_be'] - 543, i['month'], i['day']), i['year_be'], i['month'],
        f"{i['hh']:02d}:{i['mm']:02d}", i['hh'], i['province'],
        result['lagna']['sign'], round(result['lagna']['lon'] % 30, 2), result['sun_sign'],
        result['tanu_lagna']['name'], result['tanu_lagna']['house'],
        result['tanuset']['name'], result['tanuset']['house'],
        k['sign'], k['lord_name'], k['lord_house'], k['dignity'],
        'เสื่อมคุณภาพ' if pair_bad else 'ทรงคุณภาพ',
        top[0], top[1], top[2],
        actual or None, match1, match3,
    ])
    ws.cell(ws.max_row, 2).number_format = 'yyyy-mm-dd hh:mm'
    ws.cell(ws.max_row, 4).number_format = 'yyyy-mm-dd'

    for p in result['planets']:
        wp.append([chart_id, p['no'], p['name'], p['sign'], p['sign_no'] + 1,
                   p['deg_in_sign'], p['lon'], p['house'], p['dignity']])
    _save(wb)
    return chart_id


def list_charts():
    """อ่าน sheet charts ทั้งหมด คืน list ของ dict (ใหม่สุดก่อน)"""
    init_db()
    wb = load_workbook(DB_PATH, read_only=True)
    rows = list(wb['charts'].iter_rows(values_only=True))
    wb.close()
    head, data = rows[0], rows[1:]
    return [dict(zip(head, r)) for r in reversed(data) if r[0] is not None]


def get_chart(chart_id):
    for row in list_charts():
        if row['chart_id'] == chart_id:
            return row
    return None
