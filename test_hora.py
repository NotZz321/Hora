"""ชุดทดสอบ — รันหลังแก้โค้ดทุกครั้ง:  python test_hora.py
ค่าที่คาดไว้มาจากชีทเรียนและวันย้ายราศีจริง (ดู CLAUDE.md หัวข้อ "ที่มาของค่าทดสอบ")
"""
import os
import sys
import tempfile
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'lib'))

import suriyayatra_v3 as S
import career as C

passed = failed = 0


def check(name, got, expected):
    global passed, failed
    if got == expected:
        passed += 1
        print(f'  ✓ {name}')
    else:
        failed += 1
        print(f'  ✗ {name}: ได้ {got!r} ต้องการ {expected!r}')


def sign_of(d, hh, mm, planet, lon=100.5):
    pos, _ = S.chart(d, hh, mm, lon)
    return S.SIGNS[int(pos[planet] // 30)]


print('1) ตัวอย่างในชีทครั้งที่ 10: 20 เม.ย. 2549 23:20 น.')
pos, lg, frame = S.horoscope(20, 4, 2549, 23, 20)
check('ชาวราศีเมษ', S.SIGNS[int(pos[1] // 30)], 'เมษ')
check('ลัคนาธนู', S.SIGNS[int(lg // 30)], 'ธนู')

print('2) สูตรตนุเศษ (ชีทครั้งที่ 10)')


def tanuset_case(A, B):
    """สร้างดวงสมมติ ลัคนาเมษ ให้นับจากลัคนาถึงตนุลัคน์ = A และนับต่อไปถึงเจ้าเรือน = B"""
    lag = 0
    t = S.KASET[lag]                    # ๓
    ts = (lag + A - 1) % 12
    signs = {p: 6 for p in S.PLANET_NAMES}
    signs[t] = ts
    lord = S.KASET[ts]
    if lord != t:
        signs[lord] = (ts + B - 1) % 12
    return S.life_frame(signs, lag)['ตนุเศษ'][0]


check('9×2 เศษ 4 → ๔', tanuset_case(9, 2), 4)
check('9×3 เศษ 6 → ๖', tanuset_case(9, 3), 6)
check('9×4 เศษ 1 → ๑', tanuset_case(9, 4), 1)
check('ตนุลัคน์กุมลัคนา → ๑', tanuset_case(1, 1), 1)
check('ตนุลัคน์เล็งลัคนา → ๗', tanuset_case(7, 2), 7)

print('3) ตำแหน่งมาตรฐานดาว (ชีทครั้งที่ 07, 10, 11)')
SIGN_NO = {n: i for i, n in enumerate(S.SIGNS)}


def names(p, sign_name):
    s = SIGN_NO[sign_name]
    return {n for n, t in C.POSITIONS.items() if s in t.get(p, ())}


# ตัวอย่างในชีท 10–11
check('๑ ในกรกฎ = มหาจักร', 'มหาจักร' in names(1, 'กรกฎ'), True)
check('๕ ในตุลย์ = เทวีโชค', 'เทวีโชค' in names(5, 'ตุลย์'), True)
check('๗ ในตุลย์ = อุจจ์', 'อุจจ์' in names(7, 'ตุลย์'), True)
check('๓ ในตุลย์ = ประเกษตร', 'ประเกษตร' in names(3, 'ตุลย์'), True)
check('๘ ในมีน = ปกติ', names(8, 'มีน'), set())
# จุดพิเศษในชีท 07: ๗ เกษตรทั้งมังกรและกุมภ์ แต่ประเกษตรแค่กรกฎ, ๘ ประเกษตรสิงห์
check('๗ ในกุมภ์ = เกษตร', 'เกษตร' in names(7, 'กุมภ์'), True)
check('๗ ในสิงห์ ไม่ใช่ประเกษตร', 'ประเกษตร' in names(7, 'สิงห์'), False)
check('๘ ในสิงห์ = ประเกษตร', 'ประเกษตร' in names(8, 'สิงห์'), True)
# เฉลยแบบทดสอบในชีท 07 (เช็กว่าตำแหน่งที่เฉลยมีครบในผลของโปรแกรม)
for p, sign, expect in [
        (3, 'พิจิก', {'เกษตร', 'เทวีโชค'}), (4, 'กันย์', {'เกษตร', 'อุจจ์'}),
        (7, 'พิจิก', {'จุลจักร', 'ราชาโชค'}), (7, 'พฤษภ', {'มหาจักร', 'เทวีโชค'}),
        (4, 'มีน', {'ประเกษตร', 'นิจ'}), (6, 'เมษ', {'อุจจาภิมุข', 'ประเกษตร'}),
        (4, 'สิงห์', {'ราชาโชค', 'อุจจาวิลาส'}), (2, 'เมถุน', {'อุจจาภิมุข'}),
        (2, 'ตุลย์', {'จุลจักร'}), (8, 'มังกร', {'มหาจักร'})]:
    check(f'เฉลย: {p} ใน{sign} มี {"/".join(sorted(expect))}', expect <= names(p, sign), True)
# ทุกตำแหน่งต้องมีครบดาว ๑–๘
check('ทุกตำแหน่งมีครบดาว ๑–๘', all(set(t) == set(range(1, 9)) for t in C.POSITIONS.values()), True)
# ความหมายราชาโชค/เทวีโชคกลับเมื่อเกณฑ์ ๕ เสื่อม (ชีท 07)
check('ราชาโชค ๕− = ถูกนินทา', 'ถูกนินทา' in C.dignity(5, 0, k5_good=False), True)
check('เทวีโชค ๕+ = โชคจากเสน่ห์', 'โชคจากเสน่ห์' in C.dignity(5, 6, k5_good=True), True)

print('4) วันย้ายราศีจริง (ใช้ปรับเทียบ ทดสอบ 1 วันหลังย้าย)')
check('ราหูเข้ากุมภ์ 5 พ.ค. 68', sign_of(date(2025, 5, 6), 12, 0, 8), 'กุมภ์')
check('ราหูยังอยู่กุมภ์ 21 พ.ย. 69', sign_of(date(2026, 11, 21), 12, 0, 8), 'กุมภ์')
check('เสาร์เข้ามีน 19 พ.ค. 68', sign_of(date(2025, 5, 20), 12, 0, 7), 'มีน')
check('พฤหัสเข้ากรกฎ 1 มิ.ย. 69', sign_of(date(2026, 6, 2), 12, 0, 5), 'กรกฎ')
check('เกตุเข้าเมถุน 30 ต.ค. 64', sign_of(date(2021, 10, 31), 12, 0, 9), 'เมถุน')
check('เกตุเข้ากรกฎ 14 ก.ค. 66', sign_of(date(2023, 7, 15), 12, 0, 9), 'กรกฎ')
check('มฤตยูเข้าพฤษภ 7 ก.ค. 65', sign_of(date(2022, 7, 9), 12, 0, 0), 'พฤษภ')

print('5) กรอบอาชีพ ดวงตัวอย่าง 20/4/2549')
r = C.analyze(20, 4, 2549, 23, 20)
check('ภพกัมมะ = กันย์', r['karma']['sign'], 'กันย์')
check('ดาวกัมมะ = ๔', r['karma']['lord'], 4)
check('3 อันดับ = ๔ ๕ ๘', [t['planet'] for t in r['top_careers']], [4, 5, 8])

print('5.1) เกณฑ์ 5 (หลักการที่ผู้ใช้กำหนด: ๕ นิจ = เสื่อม, ที่เหลือ = ทรงคุณภาพ)')
check('๕ ในมังกร (นิจ) = เสื่อมคุณภาพ', C.kesana5({5: 9})['good'], False)
check('๕ ในกรกฎ (อุจจ์) = ทรงคุณภาพ', C.kesana5({5: 3})['good'], True)
check('๕ ในตุลย์ = ทรงคุณภาพ', C.kesana5({5: 6})['good'], True)
check('analyze() มีเกณฑ์ 5', 'kesana5' in r, True)

print('6) Excel บันทึกแล้วอ่านกลับได้ (ใช้ไฟล์ชั่วคราว ไม่แตะ data/hora.xlsx)')
import excel_db as DB
DB.DB_PATH = os.path.join(tempfile.mkdtemp(), 'test.xlsx')
cid = DB.save_chart(r, 'ทดสอบ', 'สื่อสาร/การตลาด')
row = DB.get_chart(cid)
check('chart_id = 1', cid, 1)
check('ลัคนาใน Excel', row['ลัคนา'], 'ธนู')
check('ทำนายตรงอันดับ1', row['ทำนายตรงอันดับ1'], True)

print(f'\nผ่าน {passed} / {passed + failed}')
sys.exit(1 if failed else 0)
