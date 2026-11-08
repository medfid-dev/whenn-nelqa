#!/usr/bin/env python3
"""
وين لقيتها؟ — جامع أخبار الندرة من خلاصات RSS للصحف الجزائرية.

- مكتبات بايثون القياسية فقط (بلا pip).
- يخزّن العنوان والرابط واسم المصدر فقط (لا نص المقال).
- التشغيل التجريبي:  python fetch_news.py --dry-run
- التشغيل الفعلي:    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python fetch_news.py
"""
import json, os, re, sys, time, html, argparse
import urllib.request, urllib.error, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

# ───────── المصادر: لكل جريدة عدة مسارات محتملة، يُستخدم أول مسار يعمل ─────────
SOURCES = [
    ("النهار أونلاين",   ["https://www.ennaharonline.com/feed"]),   # مؤكَّد
    ("الشروق أونلاين",   ["https://www.echoroukonline.com/feed", "https://www.echoroukonline.com/feed/"]),
    ("البلاد",           ["https://www.elbilad.net/feed", "https://www.elbilad.net/rss"]),
    ("الخبر",            ["https://www.elkhabar.com/feed", "https://www.elkhabar.com/rss"]),
    ("شهاب برس",         ["https://www.shihabpresse.dz/feed"]),
    ("الجزائر اليوم",    ["https://www.aljazairalyoum.dz/feed"]),
    ("أوراس",            ["https://www.awras.com/feed"]),
    ("اللقاء",           ["https://elikaaonline.com/feed"]),
    ("الأيام نيوز",      ["https://www.elayem.dz/feed", "https://elayem.dz/feed"]),
    ("المساء",           ["https://www.el-massa.com/feed"]),
]

# ───────── مصادر غير صحفية ─────────
# وكالة أنباء وإذاعة رسميتان: المسارات محتملة (غير مؤكَّدة) وتُجرَّب تلقائياً، والفاشل يظهر في السجل
OFFICIAL = [
    ("وكالة الأنباء الجزائرية", ["https://www.aps.dz/ar/feed",
                                 "https://www.aps.dz/ar/economie?format=feed&type=rss",
                                 "https://www.aps.dz/ar/algerie?format=feed&type=rss"]),
    ("الإذاعة الجزائرية",       ["https://www.radioalgerie.dz/news/ar/rss.xml",
                                 "https://www.radioalgerie.dz/news/ar/feed"]),
]

# تجميع Google News: يلتقط التلفزيون والإذاعة والوكالات والبيانات الرسمية ومواقع كثيرة غير المذكورة أعلاه.
# اسم الناشر الحقيقي يؤخذ من وسم <source> في الخبر نفسه، فيظهر في التطبيق كمصدر.
def gnews(q):
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": q + " when:2d", "hl": "ar", "gl": "DZ", "ceid": "DZ:ar"})

AGGREGATORS = [
    ("تجميع: ندرة",           [gnews("ندرة الجزائر")]),
    ("تجميع: نقص واختفاء",    [gnews("نقص OR اختفاء OR نفاد الجزائر")]),
    ("تجميع: غلاء",           [gnews('غلاء OR "ارتفاع الأسعار" الجزائر')]),
    ("تجميع: وزارة التجارة",  [gnews("وزارة التجارة الجزائر")]),
]

# بحث داخل مواقع الصحف الجزائرية عبر Google News (عندما لا تعطينا خلاصتها إلا آخر 10 أخبار)
_KW = "(ندرة OR نقص OR اختفاء OR نفاد OR طوابير OR غلاء OR أسعار OR أزمة)"
SITE_DOMAINS = [
    ("الشروق", "echoroukonline.com"), ("النهار", "ennaharonline.com"), ("البلاد", "elbilad.net"),
    ("الخبر", "elkhabar.com"), ("وكالة الأنباء", "aps.dz"), ("TSA", "tsa-algerie.com"),
    ("الجزائر 360", "algerie360.com"), ("الوطن", "elwatan-dz.com"), ("المجاهد", "elmoudjahid.com"),
    ("أوراس", "awras.com"), ("شهاب", "shihabpresse.dz"), ("الجزائر اليوم", "aljazairalyoum.dz"),
    ("اللقاء", "elikaaonline.com"), ("الإذاعة", "radioalgerie.dz"),
]
AGGREGATORS += [(f"موقع: {n}", [gnews(f"{_KW} site:{d}")]) for n, d in SITE_DOMAINS]
AGGREGATORS += [
    ("موضوع: البطاطا",  [gnews("البطاطا OR البطاطس الجزائر")]),
    ("موضوع: الزيت",    [gnews("زيت المائدة الجزائر")]),
    ("موضوع: الحليب",   [gnews("الحليب الجزائر")]),
    ("موضوع: الأدوية",  [gnews("نقص الأدوية الجزائر")]),
    ("موضوع: الخضر",    [gnews("الخضر OR الطماطم OR البصل الجزائر أسعار")]),
]

ALL_SOURCES = SOURCES + OFFICIAL + AGGREGATORS

MAX_AGE_H = 36          # تجاهل ما هو أقدم
MAX_PER_FEED = 100
UA = "WheenLqithaBot/1.0 (+RSS reader for a community scarcity radar; titles and links only)"

# ───────── تطبيع النص العربي ─────────
_TASHKEEL = re.compile(r"[\u064B-\u065F\u0670\u0640]")
def norm(s: str) -> str:
    s = _TASHKEEL.sub("", s)
    s = re.sub("[أإآٱ]", "ا", s)
    s = s.replace("ى", "ي").replace("ة", "ه")
    return re.sub(r"\s+", " ", s).strip()

AR = "\u0621-\u064A"
def term_re(term: str) -> re.Pattern:
    """كلمة كاملة مع سوابق عربية شائعة، ولا تلتصق بحروف عربية أخرى."""
    t = norm(term)
    return re.compile(rf"(?<![{AR}])(?:وبال|وال|بال|لل|ال|و|ب|ل|ف)?{re.escape(t)}(?![{AR}])")

def cue_re(term: str) -> re.Pattern:
    """مثل term_re لكن تقبل لواحق الضمير (ها، هم، ه، نا...) فتلتقط «غيابها» و«اختفائه»."""
    t = norm(term)
    return re.compile(rf"(?<![{AR}])(?:وبال|وال|بال|لل|ال|و|ب|ل|ف)?{re.escape(t)}(?:ها|هم|هن|ه|نا)?(?![{AR}])")

def any_match(patterns, text):
    return any(p.search(text) for p in patterns)

# ───────── السلع ─────────
ITEM_TERMS = {
    "oil":       ["زيت المائدة", "زيت الطعام", "زيوت المائدة", "الزيوت الغذائية", "زيت غذائي", "زيت", "الزيت"],
    "baby_milk": ["حليب الأطفال", "حليب الرضع", "حليب الاطفال"],
    "milk":      ["حليب", "الحليب", "أكياس الحليب", "الحليب المدعم", "مسحوق الحليب"],
    "semolina":  ["سميد", "السميد"],
    "flour":     ["طحين", "فرينة", "الفرينة", "الدقيق"],
    "bread":     ["الخبز", "خبز"],
    "sugar":     ["السكر", "سكر"],
    "coffee":    ["القهوة", "قهوة"],
    "eggs":      ["البيض", "بيض"],
    "chicken":   ["الدجاج", "لحم الدجاج", "الدواجن", "لحوم الدواجن"],
    "rice":      ["الأرز", "ارز"],
    "pasta":     ["المعجنات", "المعكرونة", "العجائن"],
    "butane":    ["غاز البوتان", "البوتان", "قارورات الغاز", "قارورة الغاز"],
    "fuel":      ["البنزين", "المازوت", "الوقود", "الديزل", "غاز المدينة"],
    "medicine":  ["الأدوية", "الدواء", "دواء", "أدوية", "الأنسولين", "الانسولين"],
    "diapers":   ["الحفاضات", "حفاضات", "الحفاظات"],
    "cash":      ["السيولة", "سيولة نقدية", "الأوراق النقدية"],
    "potato":    ["البطاطس", "البطاطا", "بطاطس"],
    "veg":       ["الخضر", "الخضروات", "الفواكه", "الطماطم", "البصل", "الثوم", "الفلفل", "الجزر"],
    "meat":      ["اللحوم الحمراء", "لحوم حمراء", "لحم الغنم", "لحم البقر", "لحم الخروف", "اللحوم"],
    "fish":      ["السمك", "الأسماك", "السردين"],
}
ITEM_RE = {k: [term_re(t) for t in v] for k, v in ITEM_TERMS.items()}

# عبارات تعني أن الكلمة ليست عن الندرة (مثل «زيت الزيتون» الدارجة قد تدخل، فنستثني بعض الحالات)
ITEM_EXCLUDE = {
    "oil":  [term_re("زيت الزيتون"), term_re("زيوت المحركات"), term_re("النفط")],
    "cash": [],
}

# ───────── الدلائل ─────────
SCARCE_CUES = [cue_re(t) for t in [
    "ندرة", "نقص", "شح", "اختفاء", "اختفى", "انقطاع", "نفاد", "نفدت", "نفد", "طوابير",
    "اضطراب", "اضطرابات", "غياب", "فقدان", "تذبذب", "أزمة", "مفتعلي الندرة", "يختفي", "اختفت",
    "قلة", "تختفي", "صعوبة العثور", "صعوبة الحصول", "صعوبة في العثور", "صعوبة في الحصول",
    "شبه اختفاء", "رفوف فارغة", "الرفوف فارغة", "تفتقد", "يفتقد",
]]
AVAIL_CUES = [term_re(t) for t in [
    "وفرة", "متوفر", "متوفرة", "توفر", "تطمئن", "تطمين", "تطمينات", "يطمئن", "يطمئنون", "يطمئنان",
    "تنفي", "ينفي", "تكذيب", "تؤكد وفرة", "تموين منتظم", "التموين المنتظم", "بكامل طاقتها",
    "تعود إلى الأسواق", "عادت إلى الأسواق", "تعود للأسواق", "عادت للأسواق", "عودة إلى الأسواق",
    "عودة الى الاسواق", "تتوفر من جديد", "عادت للظهور", "تظهر من جديد",
]]
# ───────── دلائل الأسعار (من العنوان فقط، لتقليل الضجيج) ─────────
PRICE_UP_CUES = [term_re(t) for t in [
    "غلاء", "لهيب الأسعار", "لهيب أسعار", "ارتفاع سعره", "ارتفاع سعرها", "ارتفاع أسعارها", "ارتفاع أسعاره", "التهاب الأسعار", "التهاب أسعار", "جنون الأسعار", "أسعار ملتهبة", "أسعار نارية",
    "أسعار خيالية", "أسعار قياسية", "أسعار مرتفعة", "مضاربة", "تلتهب",
    "ارتفاع الأسعار", "ارتفاع أسعار", "ارتفاع سعر", "ارتفاع في الأسعار", "ارتفاع في أسعار", "ارتفاع في سعر",
    "ارتفاعا في الأسعار", "زيادة في الأسعار", "زيادة في أسعار", "زيادة في سعر", "زيادة أسعار",
    "زيادات في أسعار", "زيادات في الأسعار", "ترتفع أسعار", "ترتفع الأسعار", "ارتفعت أسعار", "ارتفعت الأسعار",
    "ارتفع سعر", "يرتفع سعر", "تضاعف سعر", "تضاعفت أسعار", "تضاعف أسعار",
]]
PRICE_DOWN_CUES = [term_re(t) for t in [
    "انخفاض الأسعار", "انخفاض أسعار", "انخفاض سعر", "انخفاض في الأسعار", "انخفاض في أسعار",
    "تراجع الأسعار", "تراجع أسعار", "تراجع سعر", "تراجع في الأسعار", "تراجع في أسعار",
    "هبوط الأسعار", "هبوط أسعار", "تخفيض الأسعار", "تخفيض أسعار", "انخفضت أسعار", "تنخفض أسعار", "تراجعت أسعار",
]]
# قاعدة أوسع: كلمة «سعر/أسعار» مع فعل أو اسم ارتفاع في العنوان نفسه، مثل «ارتفاع جنوني لأسعار الدجاج» و«أسعار الخضر تلتهب»
PRICE_NOUN = [term_re(t) for t in ["سعر", "أسعار", "أسعارها", "أسعاره", "سعره", "سعرها"]]
RISE_CUES = [term_re(t) for t in [
    "ارتفاع", "ارتفاعا", "ارتفعت", "ارتفع", "ترتفع", "يرتفع", "زيادة", "زيادات", "تضاعف", "تضاعفت", "تحلق", "تحليق",
    "تشتعل", "تلتهب", "يلتهب", "لهيب", "التهاب", "جنون", "جنوني", "جنونية", "قفزة", "تقفز", "صاروخي", "صاروخية",
    "خيالية", "قياسية", "مرتفعة", "تصاعد", "تتصاعد", "تصعد", "تحرق", "غلاء",
]]
DROP_CUES = [term_re(t) for t in [
    "انخفاض", "انخفضت", "انخفض", "تنخفض", "ينخفض", "تراجع", "تراجعت", "يتراجع", "تتراجع", "هبوط", "تهاوي", "تهاوت",
    "انهيار", "تنهار", "ينهار", "تخفيض", "تخفيضات",
]]
# أسعار عالمية لا تخص المستهلك الجزائري مباشرة
GENERAL_EXCLUDE = re.compile(r"نفط|برنت|ذهب|دولار|يورو|بورصه|اسهم|عملات")
MISSED = []   # عناوين فيها «أسعار» ولم تُصنَّف: تظهر في السجل لتحسين التصنيف

NEGATED_PRICE = re.compile(rf"(?<![{AR}])لا (?:يوجد |توجد )?(?:ارتفاع|زياده|غلاء)")
GENERAL_PRICE = re.compile(r"اسعار|غلاء|القدره الشرائيه|المعيشه")

# نفي الندرة صراحةً: «لا توجد ندرة»، «لا نقص»
NEGATED_SCARCE = re.compile(
    rf"(?<![{AR}])[وف]?(?:(?:لا|ليس هناك|ليست هناك) (?:توجد |يوجد |وجود |يوجد اي |توجد اي )?|(?:تنفي|ينفي|نفت|نفي|تنفون|ينفون) (?:وجود |اي )*)"
    rf"(?:ندره|نقص|شح|ازمه|اضطراب)")
# «غير متوفر» و«لا يتوفر» و«عدم توفر» تعني نفاداً لا وفرة
NOT_AVAIL = re.compile(
    rf"(?<![{AR}])(?:غير |ليس |ليست |لم يعد |لم تعد |عدم |لا )(?:ال)?(?:متوفر|توفر|يتوفر|تتوفر|متواجد)[هاتن]?(?![{AR}])")

# ───────── الولايات ─────────
WILAYAS = ["أدرار", "الشلف", "الأغواط", "أم البواقي", "باتنة", "بجاية", "بسكرة", "بشار", "البليدة", "البويرة",
           "تمنراست", "تبسة", "تلمسان", "تيارت", "تيزي وزو", "الجلفة", "جيجل", "سطيف", "سعيدة", "سكيكدة",
           "سيدي بلعباس", "عنابة", "قالمة", "قسنطينة", "المدية", "مستغانم", "المسيلة", "معسكر", "ورقلة", "وهران",
           "البيض", "إليزي", "برج بوعريريج", "بومرداس", "الطارف", "تندوف", "تسمسيلت", "الوادي", "خنشلة",
           "سوق أهراس", "تيبازة", "ميلة", "عين الدفلى", "النعامة", "عين تموشنت", "غرداية", "غليزان",
           "تيميمون", "برج باجي مختار", "أولاد جلال", "بني عباس", "عين صالح", "عين قزام", "تقرت", "جانت",
           "المغير", "المنيعة"]
AMBIGUOUS = {"سعيدة", "البيض", "الوادي", "جانت"}   # تُقبل فقط بعد كلمة «ولاية»
WILAYA_ALIASES = {"تيسمسيلت": "تسمسيلت", "الجزائر العاصمة": "الجزائر", "العاصمة": "الجزائر", "ولاية الجزائر": "الجزائر",
                  "الجزائر الوسطى": "الجزائر"}

def wilaya_patterns():
    pats = []
    for w in WILAYAS:
        n = norm(w)
        if w in AMBIGUOUS:
            pats.append((w, re.compile(rf"(?<![{AR}])ولايه {re.escape(n)}(?![{AR}])")))
        else:
            pats.append((w, re.compile(rf"(?<![{AR}])(?:ولايه )?(?:وفي |في |وب|ول|و|ب|ل)?{re.escape(n)}(?![{AR}])")))
    for alias, canon in WILAYA_ALIASES.items():
        pats.append((canon if canon != "تسمسيلت" else "تسمسيلت",
                     re.compile(rf"(?<![{AR}])(?:وب|ول|و|ب|ل)?{re.escape(norm(alias))}(?![{AR}])")))
    return pats
WILAYA_RE = wilaya_patterns()

def find_wilayas(text):
    out = []
    for name, p in WILAYA_RE:
        if p.search(text) and name not in out:
            out.append(name)
    return out

# ───────── التصنيف ─────────
def classify(title: str, summary: str = ""):
    """يرجع قائمة [(item, status, wilayas)]. الحالات: out / available / mixed (ندرة) و price_up / price_down (أسعار)."""
    t = norm(title)
    full = norm(title + " " + (summary or ""))
    scarce = any_match(SCARCE_CUES, t) or any_match(SCARCE_CUES, full)
    t_ok, full_ok = NOT_AVAIL.sub(" ", t), NOT_AVAIL.sub(" ", full)    # «غير متوفر» لا تُحسب وفرة
    avail = any_match(AVAIL_CUES, t_ok) or any_match(AVAIL_CUES, full_ok)
    if NOT_AVAIL.search(full):
        scarce = True
    if NEGATED_SCARCE.search(full):
        scarce = False
        avail = True
    price = None
    if not NEGATED_PRICE.search(t):
        noun = any_match(PRICE_NOUN, t)
        up = any_match(PRICE_UP_CUES, t) or (noun and any_match(RISE_CUES, t))
        down = any_match(PRICE_DOWN_CUES, t) or (noun and any_match(DROP_CUES, t))
        if up and not down:
            price = "price_up"
        elif down and not up:
            price = "price_down"
    if not (scarce or avail or price):
        return []
    statuses = []
    if scarce or avail:
        statuses.append("mixed" if (scarce and avail) else ("out" if scarce else "available"))
    if price:
        statuses.append(price)
    wilayas = find_wilayas(full)

    # السلع: العنوان له الأولوية، فإن لم نجد نبحث في الملخص
    found = []
    for src in (t, full):
        for item, pats in ITEM_RE.items():
            if item in found:
                continue
            if any_match(pats, src) and not any_match(ITEM_EXCLUDE.get(item, []), src):
                found.append(item)
        if found:
            break
    if "baby_milk" in found and "milk" in found:
        found.remove("milk")
    if not found:
        # خبر غلاء عام بلا سلعة محددة
        if price and GENERAL_PRICE.search(t) and not GENERAL_EXCLUDE.search(t):
            return [("general", price, wilayas)]
        return []
    return [(i, st, wilayas) for i in found[:3] for st in statuses]

# ───────── جلب RSS ─────────
def http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def strip_html(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()

def parse_date(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)

def parse_feed(xml_bytes):
    root = ET.fromstring(xml_bytes)
    out = []
    # RSS 2.0
    for it in root.iter("item"):
        out.append({
            "title": strip_html(it.findtext("title")),
            "link": (it.findtext("link") or "").strip(),
            "summary": strip_html(it.findtext("description")),
            "src": strip_html(it.findtext("source")),
            "date": parse_date(it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date")),
        })
    # Atom
    ns = "{http://www.w3.org/2005/Atom}"
    for en in root.iter(ns + "entry"):
        link = ""
        for l in en.findall(ns + "link"):
            if l.get("rel", "alternate") == "alternate":
                link = l.get("href", ""); break
        out.append({
            "title": strip_html(en.findtext(ns + "title")),
            "link": link.strip(),
            "summary": strip_html(en.findtext(ns + "summary")),
            "src": "",
            "date": parse_date(en.findtext(ns + "updated") or en.findtext(ns + "published")),
        })
    return out

def collect(verbose=True):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=MAX_AGE_H)
    rows, report = [], []
    seen = set()
    for name, urls in ALL_SOURCES:
        ok = False
        for u in urls:
            try:
                entries = parse_feed(http_get(u))
                ok = True
                break
            except Exception as e:
                last = f"{type(e).__name__}: {e}"
        if not ok:
            report.append((name, "فشل", last)); continue
        kept = 0
        for e in entries[:MAX_PER_FEED]:
            if not e["title"] or not re.match(r"^https?://", e["link"] or ""):
                continue
            d = e["date"] or now
            if d < cutoff or d > now + timedelta(hours=2):
                continue
            title, sname = e["title"], name
            if e.get("src"):                       # تجميع: الناشر الحقيقي واسمه في آخر العنوان
                sname = e["src"][:60]
                suffix = " - " + e["src"]
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            tkey = norm(title)[:80]
            res = classify(title, e["summary"])
            if not res and (any_match(PRICE_NOUN, tkey) or "غلاء" in tkey) and len(MISSED) < 25:
                MISSED.append(f"{sname}: {title[:90]}")
            for item, status, wilayas in res:
                k = (tkey, item, status)
                if k in seen:                      # نفس الخبر من مصدرين
                    continue
                seen.add(k)
                rows.append({
                    "item": item, "status": status, "wilayas": wilayas,
                    "title": title[:240], "source_name": sname,
                    "source_url": e["link"][:590], "published_at": d.isoformat(),
                })
                kept += 1
        report.append((name, "نجح", f"{len(entries)} خبر، {kept} بلاغ"))
        time.sleep(1)
    if verbose:
        print("— حالة المصادر —")
        for n, s, m in report:
            print(f"  {s:5} {n}: {m}")
        counts = {}
        for r in rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        print("— عدد الأخبار حسب النوع —", counts or "لا شيء")
        if MISSED:
            print("— عناوين فيها «أسعار» أو «غلاء» ولم تُصنَّف (للمراجعة) —")
            for m in MISSED:
                print("  ", m)
    return rows

# ───────── Supabase ─────────
def sb_request(method, path, body=None, extra=None):
    # يتسامح مع SUPABASE_URL المنتهي بـ /rest/v1 (خطأ شائع يسبب 404)
    base = re.sub(r"/rest/v1/?$", "", os.environ["SUPABASE_URL"].strip().rstrip("/")).rstrip("/")
    key = os.environ["SUPABASE_SERVICE_KEY"].strip()
    headers = {"apikey": key, "Content-Type": "application/json"}
    if key.startswith("eyJ"):                 # المفاتيح الجديدة sb_secret_ ليست JWT: تُرسل في apikey فقط
        headers["Authorization"] = "Bearer " + key
    headers.update(extra or {})
    data = json.dumps(body).encode() if body is not None else None
    url = base + "/rest/v1/" + path
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        print(f"خطأ Supabase: HTTP {e.code} عند {method} {base}/rest/v1/{path.split('?')[0]}")
        print("الرد:", detail)
        raise SystemExit(1)

def push(rows):
    if not rows:
        print("لا بلاغات جديدة."); return
    st = sb_request("POST", "wl_news?on_conflict=source_url,item,status", rows,
                    {"Prefer": "resolution=ignore-duplicates,return=minimal"})
    print(f"أُرسل {len(rows)} بلاغ (HTTP {st}).")
    old = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    sb_request("DELETE", "wl_news?published_at=lt." + urllib.parse.quote(old), None, {"Prefer": "return=minimal"})
    print("نُظّفت الأخبار الأقدم من 7 أيام.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    rows = collect()
    print(f"\nالمجموع: {len(rows)} بلاغ")
    for r in rows[:30]:
        print(f"  [{r['status']:9}] {r['item']:9} {','.join(r['wilayas']) or 'وطني':20} {r['title'][:70]}")
    if a.dry_run or not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY")):
        print("\n(وضع تجريبي: لم يُرسل شيء إلى Supabase)")
        return
    push(rows)

if __name__ == "__main__":
    main()
