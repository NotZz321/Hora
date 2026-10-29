import os
import random
import sys
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'lib'))

import career as C
import excel_db as DB

SEED = 2026
YEAR_BE = (2540, 2550)
COLLECT = (datetime(2026, 10, 14), datetime(2026, 10, 27))

POPULATION = {
    'กรุงเทพมหานคร': 5470, 'กระบี่': 480, 'กาญจนบุรี': 900, 'กาฬสินธุ์': 980, 'กำแพงเพชร': 730,
    'ขอนแก่น': 1800, 'จันทบุรี': 540, 'ฉะเชิงเทรา': 730, 'ชลบุรี': 1610, 'ชัยนาท': 330,
    'ชัยภูมิ': 1140, 'ชุมพร': 510, 'เชียงราย': 1300, 'เชียงใหม่': 1790, 'ตรัง': 640,
    'ตราด': 230, 'ตาก': 680, 'นครนายก': 260, 'นครปฐม': 920, 'นครพนม': 720,
    'นครราชสีมา': 2630, 'นครศรีธรรมราช': 1550, 'นครสวรรค์': 1060, 'นนทบุรี': 1290, 'นราธิวาส': 810,
    'น่าน': 480, 'บึงกาฬ': 420, 'บุรีรัมย์': 1590, 'ปทุมธานี': 1200, 'ประจวบคีรีขันธ์': 560,
    'ปราจีนบุรี': 500, 'ปัตตานี': 730, 'พระนครศรีอยุธยา': 820, 'พะเยา': 470, 'พังงา': 270,
    'พัทลุง': 530, 'พิจิตร': 530, 'พิษณุโลก': 850, 'เพชรบุรี': 490, 'เพชรบูรณ์': 990,
    'แพร่': 440, 'ภูเก็ต': 420, 'มหาสารคาม': 960, 'มุกดาหาร': 350, 'แม่ฮ่องสอน': 290,
    'ยโสธร': 540, 'ยะลา': 540, 'ร้อยเอ็ด': 1300, 'ระนอง': 190, 'ระยอง': 750,
    'ราชบุรี': 870, 'ลพบุรี': 760, 'ลำปาง': 730, 'ลำพูน': 400, 'เลย': 640,
    'ศรีสะเกษ': 1470, 'สกลนคร': 1150, 'สงขลา': 1440, 'สตูล': 330, 'สมุทรปราการ': 1370,
    'สมุทรสงคราม': 190, 'สมุทรสาคร': 590, 'สระแก้ว': 570, 'สระบุรี': 650, 'สิงห์บุรี': 210,
    'สุโขทัย': 590, 'สุพรรณบุรี': 850, 'สุราษฎร์ธานี': 1070, 'สุรินทร์': 1390, 'หนองคาย': 520,
    'หนองบัวลำภู': 510, 'อ่างทอง': 280, 'อำนาจเจริญ': 380, 'อุดรธานี': 1580, 'อุตรดิตถ์': 450,
    'อุทัยธานี': 330, 'อุบลราชธานี': 1880,
}

NICKNAMES = (
    'ต้น ฟ้า มิ้นท์ บอส แบงค์ เบียร์ ปอ ปาล์ม พลอย แพร ฝน ฟิล์ม เฟิร์น ไผ่ มายด์ มุก เมย์ '
    'ยิม เอิร์ธ ออม อิง อาร์ม อั้ม ไอซ์ โอ๊ต โอม กัปตัน กิ๊ฟ เก่ง แก้ม ขิม ข้าวหอม แคท จูน '
    'เจ เจมส์ แจ็ค ฉัตร ชมพู่ ซัน ซี ณัฐ ดรีม ตาล ตูน เต้ย แตงโม ท็อป ทราย นัท นาย นิว น้ำ '
    'น้ำฝน นุ่น เนย บีม บิว เบล ปลา ปั้น ปุ๊ก เปา โปรด พีช พีท ฟลุ๊ค ฟอร์ด ภูมิ มาร์ค มีน '
    'ยุ้ย เล็ก แว่น ส้ม หนิง หมิว อ้อม อาย อุ้ม เอ็ม แอน แอม โอปอ ไอติม กาย กาฟิว เกด คิม '
    'เค้ก โจ ซอส ต่อ แทน นก แนน บอม ปิง พั้นช์ เพลง มะปราง วิว'
).split()


def random_birth(rng):
    first = date(YEAR_BE[0] - 543, 1, 1)
    last = date(YEAR_BE[1] - 543, 12, 31)
    d = first + timedelta(days=rng.randrange((last - first).days + 1))
    return d.day, d.month, d.year + 543, rng.randrange(24), rng.randrange(60)


def random_saved_at(rng):
    start, end = COLLECT
    day = start + timedelta(days=rng.randrange((end - start).days + 1))
    return day.replace(hour=rng.randint(9, 22), minute=rng.randrange(60), second=rng.randrange(60))


def build(n, seed=SEED):
    rng = random.Random(seed)
    provinces = list(POPULATION)
    weights = [POPULATION[p] for p in provinces]
    rows = []
    for _ in range(n):
        day, month, year_be, hh, mm = random_birth(rng)
        province = rng.choices(provinces, weights)[0]
        result = C.analyze(day, month, year_be, hh, mm, province)
        rows.append((result, rng.choice(NICKNAMES), 'mock', random_saved_at(rng)))
    rows.sort(key=lambda r: r[3])
    return rows


def remove_mock():
    wb = DB._open_wb()
    ws, wp = wb['charts'], wb['planets']
    src = DB.CHART_COLS.index('แหล่งข้อมูล')
    charts = list(ws.iter_rows(min_row=2, values_only=True))
    mock_ids = {r[0] for r in charts if r[src] == 'mock'}
    keep_c = [r for r in charts if r[0] not in mock_ids]
    keep_p = [r for r in wp.iter_rows(min_row=2, values_only=True) if r[0] not in mock_ids]
    for sheet, keep in ((ws, keep_c), (wp, keep_p)):
        if sheet.max_row > 1:
            sheet.delete_rows(2, sheet.max_row - 1)
        for r in keep:
            sheet.append(r)
    for row in range(2, ws.max_row + 1):
        ws.cell(row, 3).number_format = 'yyyy-mm-dd hh:mm'
        ws.cell(row, 5).number_format = 'yyyy-mm-dd'
    DB._save(wb)
    return len(mock_ids)


def main(argv):
    n = int(next((a for a in argv if a.isdigit()), 500))
    replace = '--replace' in argv
    DB.init_db()
    have = DB.count_source('mock')
    if have and not replace:
        print(f'มี mock อยู่แล้ว {have} ดวง ไม่เพิ่มซ้ำ (ถ้าจะสร้างใหม่ใช้: python make_mock.py {n} --replace)')
        return 1
    if have:
        print(f'ลบ mock เดิม {remove_mock()} ดวง')
    print(f'กำลังสร้าง mock {n} ดวง ...')
    ids = DB.save_many(build(n))
    print(f'เสร็จ: เพิ่ม {len(ids)} ดวง ({ids[0]}–{ids[-1]}) ลง {DB.DB_PATH}')
    print('ใน Excel/Tableau กรองคอลัมน์ แหล่งข้อมูล = "จริง" เมื่อต้องการดูเฉพาะข้อมูลจริง')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
