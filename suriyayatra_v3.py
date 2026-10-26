"""Suriyayatra prototype — Thai traditional planet positions.
Sources: Gislén & Eade (2019) JAHH 22(3) papers 2 and 5."""
from datetime import date
from math import sin, cos, asin, sqrt, radians, degrees

SIGNS = ['เมษ','พฤษภ','เมถุน','กรกฎ','สิงห์','กันย์','ตุลย์','พิจิก','ธนู','มังกร','กุมภ์','มีน']
MAHAYUGA = 1577917800          # days (Thai-scaled Suryasiddhanta)
KALI_OFFSET = 1365702          # Kali ahargana = horakhun + this (checked: exact w/ 373)
EPOCH_K = date(638, 3, 25).toordinal() + 1721425 - 1   # JDN - horakhun

def jdn(d): return d.toordinal() + 1721425
def horakhun(d): return jdn(d) - EPOCH_K           # day count, 1 = CS epoch day

def norm(x): return x % 360

# ---------- Sun ----------
def mean_sun(hk):                       # hk = continuous horakhun (h-1 + t/24)
    parts = (hk * 800 - 373) % 292207
    return parts / 292207 * 360 - 3/60

SUN_CHAYA  = [0, 35, 67, 94, 116, 129, 134]        # arcmin, every 15°
MOON_CHAYA = [0, 77, 148, 209, 256, 286, 296]

def chaya(table, anomaly):
    a = norm(anomaly); sgn = 1
    if a > 180: a, sgn = 360 - a, -1
    if a > 90: a = 180 - a
    i = min(int(a // 15), 5); f = (a - 15*i) / 15
    return sgn * (table[i] + (table[i+1] - table[i]) * f) / 60

def true_sun(hk):
    L = mean_sun(hk)
    return norm(L - chaya(SUN_CHAYA, L - 80))

# ---------- Moon (avoman method) ----------
def mean_moon(hk):
    h = int(hk) + 1                     # end-of-day integer horakhun
    def at(h):
        av = (h * 11 + 650) % 692
        tithi = (h + (h * 11 + 650) // 692) % 30
        elong = tithi * 12 + av * (1 + 1/25) / 60
        return norm(mean_sun(h) + elong - 40/60)
    a, b = at(h - 1), at(h)
    frac = hk - (h - 1)
    return norm(a + ((b - a) % 360) * frac)

def moon_apogee(hk):
    return (hk + 2611) % 3232 / 3232 * 360

def true_moon(hk):
    L = mean_moon(hk)
    return norm(L - chaya(MOON_CHAYA, L - moon_apogee(hk)))

# ---------- Planets (Suryasiddhanta scheme) ----------
REVS = {'mercury': 17937000, 'venus': 7022388, 'mars': 2296824,
        'jupiter': 364220, 'saturn': 146564}
PARAMS = {  # e, rho, apogee w
    'mercury': (28/360, 132/360, 220), 'venus': (14/360, 260/360, 80),
    'mars': (70/360, 234/360, 110), 'jupiter': (32/360, 72/360, 160),
    'saturn': (60/360, 40/360, 240)}

# ปรับค่าตั้งต้น (องศา) ให้ตรงปฏิทินโหราไทย — fit จากวันย้ายราศีจริง
CAL = {'jupiter': -3.43,   # fit: พฤหัสเข้ากรกฎ 1 มิ.ย. 69 (เช็ก 13 พ.ค. 68, 19 ต.ค. 69 ด้วย)
       'saturn':  +5.56,   # fit: เสาร์เข้ามีน 19 พ.ค. 68
       'mars': 0.0, 'mercury': 0.0, 'venus': 0.0}   # TODO: ยังไม่มีข้อมูลเทียบ
RAHU_EPOCH = 170.22        # fit: ราหูเข้ากุมภ์ 5 พ.ค. 68 และออก 22 พ.ย. 69 (ตรงทั้งสองจุด)

def mean_of(revs, hk, cal=0.0):
    D = hk + KALI_OFFSET
    return ((D * revs % MAHAYUGA) / MAHAYUGA * 360 + cal) % 360

def sighra(rho, eta):
    e = radians(eta)
    return degrees(asin(rho * sin(e) / sqrt((1 + rho*cos(e))**2 + (rho*sin(e))**2)))

def true_planet(name, hk):
    e, rho, w = PARAMS[name]
    S = mean_sun(hk) + 3/60
    P = mean_of(REVS[name], hk, CAL[name])
    L, S = (S, P) if name in ('mercury', 'venus') else (P, S)   # inner: swap
    c1 = sighra(rho, S - L);      w1 = w - c1/2
    c2 = degrees(asin(e * sin(radians(L - w1)))); w2 = w1 + c2/2
    c3 = degrees(asin(e * sin(radians(L - w2)))); L1 = L - c3
    c4 = sighra(rho, S - L1)
    return norm(L1 + c4)

def rahu(hk):                     # mean node, ถอยหลัง
    return norm(RAHU_EPOCH - mean_of(232226, hk))

KETU_EPOCH = 182.3962       # fit: เกตุเข้ากรกฎ 14 ก.ค. 66 16:46 (เช็ก: เข้าเมถุน 30 ต.ค. 64 06:46 ตรงพอดี)

def ketu(hk):
    """เกตุไทย: ดาวสมมติ ถอยหลัง คาบ 679 วัน"""
    return norm(KETU_EPOCH - 360 * hk / 679)

# มฤตยู: ไม่อยู่ในสุริยยาตร์ดั้งเดิม ใช้แบบจำลอง มัธยม + มันทะ + ศีฆระ
# ค่า fit จาก 3 วันย้ายราศีของโหราไทย (7 ก.ค. 65, 8 มี.ค. 66, 18 ก.ค. 72)
# ⚠️ ยังเป็นค่าประมาณ ตรวจกับปีเก่า (เช่น 2510–2540) ไม่ได้ ต้องเทียบ myhora เพิ่ม
URANUS = dict(L0=328.1198, P=31280, e=0.046, w=170, rho=0.03)

def maruetayu(hk):
    u = URANUS
    L = (u['L0'] + 360 * hk / u['P']) % 360
    S = mean_sun(hk) + 3/60
    m = degrees(asin(u['e'] * sin(radians(L - u['w']))))
    return norm(L - m + sighra(u['rho'], S - L))

# ---------- Lagna (Thai oblique-ascension table, lat ~15°45') ----------
OA = [244, 272, 312, 334, 326, 312, 312, 326, 334, 312, 272, 244]   # vinadi/sign

def oblique(lon):
    s, r = int(lon // 30), lon % 30
    return sum(OA[:s]) + OA[s] * r / 30

def half_day_minutes(sun):        # thinpraman from same table: 1800 vinadi ± ...
    THIN = [1800,1868,1922,1944,1922,1868,1800,1732,1678,1656,1678,1732,1800]
    s, r = int(sun // 30), sun % 30
    v = THIN[s] + (THIN[s+1] - THIN[s]) * r / 30
    return v / 2 * 0.4             # vinadi -> minutes (1 vinadi = 24 s)

def lagna_table(sun, local_minutes):
    """แบบตารางอันโตนาทีตามละติจูด + คำนวณเวลาอาทิตย์ขึ้นจริง"""
    sunrise = 720 - half_day_minutes(sun)
    vin = ((local_minutes - sunrise) % 1440) / 0.4
    x = (oblique(sun) + vin) % 3600
    s = 0
    while x >= OA[s]: x -= OA[s]; s += 1
    return s * 30 + x / OA[s] * 30

# อันโตนาทีสามัญ (นาที/ราศี) ตามตำราวิสาลดารุณกร ใช้ได้ทุกพื้นที่
ANTONATHI = [120, 96, 72, 120, 144, 168, 168, 144, 120, 72, 96, 120]

def lagna_samanya(sun, local_minutes, sunrise=360):
    """แบบเดียวกับ myhora: อันโตนาทีสามัญ อาทิตย์อุทัย 06:00 น. + ปรับเวลาท้องถิ่น"""
    s, r = int(sun // 30), sun % 30
    x = sum(ANTONATHI[:s]) + ANTONATHI[s] * r / 30 + (local_minutes - sunrise) % 1440
    x %= 1440
    s = 0
    while x >= ANTONATHI[s]: x -= ANTONATHI[s]; s += 1
    return s * 30 + x / ANTONATHI[s] * 30

LAGNA_METHOD = lagna_samanya      # สลับเป็น lagna_table ได้

# ---------- Chart ----------
def chart(d, hh, mm, lon_east=100.5):
    local = hh*60 + mm - (105 - lon_east) * 4          # ปรับเวลาท้องถิ่น (กทม. −18 นาที)
    hk = horakhun(d) - 1 + local / 1440
    pos = {1: true_sun(hk), 2: true_moon(hk),
           3: true_planet('mars', hk), 4: true_planet('mercury', hk),
           5: true_planet('jupiter', hk), 6: true_planet('venus', hk),
           7: true_planet('saturn', hk), 8: rahu(hk), 9: ketu(hk), 0: maruetayu(hk)}
    return pos, LAGNA_METHOD(pos[1], local)

def fmt(x):
    if x is None: return '(ยังไม่คำนวณ)'
    return f"{SIGNS[int(x//30)]} {int(x%30):2d}°{int(x%1*60):02d}'"

# ---------- ต่อ Level 2: กรอบชีวิต ----------
KASET  = [3, 6, 4, 2, 1, 4, 6, 3, 5, 7, 8, 5]
HOUSES = ['ตนุ','กดุมภะ','สหัชชะ','พันธุ','ปุตตะ','อริ','ปัตนิ','มรณะ','ศุภะ','กัมมะ','ลาภะ','วินาศ']

def count(a, b): return (b - a) % 12 + 1

def life_frame(signs, lag):
    t = KASET[lag]; ts = signs[t]
    A = count(lag, ts)
    if A == 1: tset = 1
    elif A == 7: tset = 7
    else:
        r = (A * count(ts, signs[KASET[ts]])) % 7
        tset = 7 if r == 0 else r
    return {'ลัคนา': SIGNS[lag],
            'ตนุลัคน์': (t, HOUSES[(ts - lag) % 12]),
            'ตนุเศษ': (tset, HOUSES[(signs[tset] - lag) % 12])}

def horoscope(day, month, year_be, hh, mm, lon_east=100.5):
    pos, lg = chart(date(year_be - 543, month, day), hh, mm, lon_east)
    signs = {k: int(v // 30) for k, v in pos.items() if v is not None}
    lag = int(lg // 30)
    return pos, lg, life_frame(signs, lag)


# ลองจิจูดตัวจังหวัด (องศาตะวันออก) ใช้ปรับเวลาท้องถิ่น
PROVINCES = {
 'กรุงเทพมหานคร':100.50,'กระบี่':98.91,'กาญจนบุรี':99.53,'กาฬสินธุ์':103.51,'กำแพงเพชร':99.52,
 'ขอนแก่น':102.84,'จันทบุรี':102.10,'ฉะเชิงเทรา':101.07,'ชลบุรี':100.98,'ชัยนาท':100.13,
 'ชัยภูมิ':102.03,'ชุมพร':99.18,'เชียงราย':99.83,'เชียงใหม่':98.98,'ตรัง':99.61,
 'ตราด':102.52,'ตาก':99.13,'นครนายก':101.21,'นครปฐม':100.06,'นครพนม':104.78,
 'นครราชสีมา':102.10,'นครศรีธรรมราช':99.96,'นครสวรรค์':100.12,'นนทบุรี':100.51,'นราธิวาส':101.82,
 'น่าน':100.77,'บึงกาฬ':103.65,'บุรีรัมย์':103.10,'ปทุมธานี':100.53,'ประจวบคีรีขันธ์':99.80,
 'ปราจีนบุรี':101.37,'ปัตตานี':101.25,'พระนครศรีอยุธยา':100.57,'พะเยา':99.90,'พังงา':98.53,
 'พัทลุง':100.08,'พิจิตร':100.35,'พิษณุโลก':100.26,'เพชรบุรี':99.95,'เพชรบูรณ์':101.16,
 'แพร่':100.14,'ภูเก็ต':98.39,'มหาสารคาม':103.30,'มุกดาหาร':104.72,'แม่ฮ่องสอน':97.97,
 'ยโสธร':104.15,'ยะลา':101.28,'ร้อยเอ็ด':103.65,'ระนอง':98.63,'ระยอง':101.28,
 'ราชบุรี':99.81,'ลพบุรี':100.65,'ลำปาง':99.49,'ลำพูน':99.01,'เลย':101.72,
 'ศรีสะเกษ':104.32,'สกลนคร':104.15,'สงขลา':100.59,'สตูล':100.07,'สมุทรปราการ':100.60,
 'สมุทรสงคราม':100.00,'สมุทรสาคร':100.27,'สระแก้ว':102.07,'สระบุรี':100.91,'สิงห์บุรี':100.40,
 'สุโขทัย':99.82,'สุพรรณบุรี':100.12,'สุราษฎร์ธานี':99.33,'สุรินทร์':103.49,'หนองคาย':102.74,
 'หนองบัวลำภู':102.43,'อ่างทอง':100.45,'อำนาจเจริญ':104.63,'อุดรธานี':102.79,'อุตรดิตถ์':100.10,
 'อุทัยธานี':100.02,'อุบลราชธานี':104.85}
ALIASES = {'กทม':'กรุงเทพมหานคร','กรุงเทพ':'กรุงเทพมหานคร','อยุธยา':'พระนครศรีอยุธยา',
           'โคราช':'นครราชสีมา','อุบล':'อุบลราชธานี','สุราษฎร์':'สุราษฎร์ธานี','นครศรี':'นครศรีธรรมราช',
           'ประจวบ':'ประจวบคีรีขันธ์','หาดใหญ่':'สงขลา','พัทยา':'ชลบุรี'}

def find_province(text):
    t = text.strip().replace('จังหวัด', '').replace('จ.', '').strip()
    if not t: return 'กรุงเทพมหานคร'
    if t in ALIASES: return ALIASES[t]
    hits = [p for p in PROVINCES if t in p]
    if len(hits) == 1: return hits[0]
    if t in hits: return t
    return None

PLANET_NAMES = {1: 'อาทิตย์', 2: 'จันทร์', 3: 'อังคาร', 4: 'พุธ', 5: 'พฤหัส',
                6: 'ศุกร์', 7: 'เสาร์', 8: 'ราหู', 9: 'เกตุ', 0: 'มฤตยู'}

def print_chart(day, month, year_be, hh, mm, province='กรุงเทพมหานคร'):
    pos, lg, frame = horoscope(day, month, year_be, hh, mm, PROVINCES[province])
    print(f"\nดวงเกิด {day}/{month}/{year_be} เวลา {hh:02d}:{mm:02d} น. จ.{province}")
    print(f"  ลัคนา        {fmt(lg)}")
    for k, v in pos.items():
        note = '  (ค่าประมาณ)' if k == 0 else ''
        print(f"  ({k}) {PLANET_NAMES[k]:<7} {fmt(v)}{note}")
    t, t_house = frame['ตนุลัคน์']; s, s_house = frame['ตนุเศษ']
    print(f"\n  ตนุลัคน์ = ดาว {t} ({PLANET_NAMES[t]}) อยู่ภพ{t_house}")
    print(f"  ตนุเศษ  = ดาว {s} ({PLANET_NAMES[s]}) อยู่ภพ{s_house}")

if __name__ == '__main__':
    import sys
    if len(sys.argv) >= 6:            # python suriyayatra_v3.py 20 4 2549 23 20 [จังหวัด]
        a = sys.argv[1:]
        prov = find_province(a[5] if len(a) > 5 else '')
        if prov is None: sys.exit('ไม่พบจังหวัดนี้')
        print_chart(int(a[0]), int(a[1]), int(a[2]), int(a[3]), int(a[4]), prov)
    else:                             # ถามทีละช่อง
        d = input('วันเกิด (วัน/เดือน/ปี พ.ศ. เช่น 20/4/2549): ').strip()
        t = input('เวลาเกิด (ชม:นาที เช่น 23:20): ').strip()
        while True:
            prov = find_province(input('จังหวัดที่เกิด (Enter = กรุงเทพฯ): '))
            if prov: break
            print('  ไม่พบจังหวัดนี้ ลองพิมพ์ชื่อเต็ม เช่น เชียงใหม่, นครราชสีมา')
        day, month, year = map(int, d.split('/'))
        hh, mm = map(int, t.split(':'))
        print_chart(day, month, year, hh, mm, prov)
        input('\nกด Enter เพื่อปิด')      # กันหน้าต่างปิดเองตอนดับเบิลคลิกไฟล์
