"""اختبارات بلا شبكة: عناوين حقيقية ظهرت في الأخبار + حالات حدّية."""
from fetch_news import classify, norm, parse_feed

def one(title, summary=""):
    return [(i, s, w) for i, s, w in classify(title, summary)]

cases = [
    # (العنوان, السلعة المتوقعة, الحالة المتوقعة)
    ("ندرة الزيت.. شركة أخرى تطمئن!", "oil", "mixed"),
    ("ندرة الزيت.. “سيفيتال” و”سيم” و”لابال” يطمئنون الجزائريين", "oil", "mixed"),
    ("اختفاء زيت المائدة من الرفوف في الجزائر: ما الذي يحدث فعلاً؟", "oil", "out"),
    ("هل ستشهد الجزائر ندرة في زيت المائدة؟ سيفيتال وسيم توضحان", "oil", "out"),
    ("نقص حاد في حليب الأطفال بالصيدليات", "baby_milk", "out"),
    ("لا توجد ندرة في الحليب حسب وزارة التجارة", "milk", "available"),
    ("وفرة البطاطس في الأسواق بعد تدخل الدولة", "potato", "available"),
    ("طوابير أمام محلات بيع السميد في وهران", "semolina", "out"),
    # أسعار
    ("ارتفاع أسعار البطاطس في أسواق الجملة بوهران", "potato", "price_up"),
    ("مرضى السكري يشتكون من غلاء الأنسولين", "medicine", "price_up"),
    ("تراجع أسعار الدجاج بعد تدخل وزارة التجارة", "chicken", "price_down"),
    ("ندرة الزيت وارتفاع سعره في الأسواق", "oil", "out"),
    ("ندرة الزيت وارتفاع سعره في الأسواق", "oil", "price_up"),
    ("غلاء المعيشة يؤرق الجزائريين", "general", "price_up"),
    ("لهيب أسعار الخضر والفواكه مع بداية الشتاء", "veg", "price_up"),
    ("ارتفاع جنوني لأسعار الدجاج في الأسواق", "chicken", "price_up"),
    ("أسعار الخضر تلتهب مع بداية الشتاء", "veg", "price_up"),
    ("أسعار اللحوم تشتعل قبل رمضان", "meat", "price_up"),
    ("قفزة في أسعار الزيت بمحلات الجملة", "oil", "price_up"),
    ("انهيار أسعار البطاطس بعد وفرة الإنتاج", "potato", "price_down"),
]
bad = 0
for title, item, status in cases:
    got = one(title)
    ok = any(g[0] == item and g[1] == status for g in got)
    bad += (not ok)
    print(("✓" if ok else "✗"), title[:60], "→", got)

# يجب تجاهلها
ignore = [
    "تصدير 2.3 طن من الأدوية نحو جمهورية كوت ديفوار",            # لا دليل ندرة/وفرة
    "الجزائر تعتمد أول قائمة وطنية للأدوية الأساسية",
    "لا ارتفاع في أسعار الخبز حسب الوزارة",                         # نفي صريح للغلاء
    "ارتفاع درجات الحرارة بولايات الجنوب",
    "ارتفاع أسعار النفط في الأسواق العالمية",                      # أسعار عالمية
    "زيادة في عدد المصابين بالإنفلونزا",                            # بلا «سعر»                         # «ارتفاع» وحدها ليست غلاء
    "ندرة المياه تهدد السدود",                                       # ماء غير مدعومة
    "فوز شباب بلوزداد على الزمالك",
]
for title in ignore:
    got = one(title)
    ok = not got
    bad += (not ok)
    print(("✓" if ok else "✗"), "تجاهل:", title[:50], "→", got)

# الولايات
w = classify("اختفاء زيت المائدة من الرفوف في وهران وسطيف وتلمسان")[0][2]
assert set(w) == {"وهران", "سطيف", "تلمسان"}, w
w = classify("نقص الحليب في الجزائر العاصمة")[0][2]
assert w == ["الجزائر"], w
w = classify("ندرة الزيت في الجزائر")[0][2]
assert w == [], w   # اسم البلد وليس الولاية → وطني
w = classify("نفاد البيض من الأسواق")[0]
assert w[0] == "eggs" and w[2] == [], w   # «البيض» ليست ولاية

# تحليل RSS
rss = """<?xml version='1.0'?><rss version='2.0'><channel><item><title>ندرة الزيت</title>
<link>https://x.dz/a</link><pubDate>Thu, 05 Nov 2026 13:06:00 +0000</pubDate>
<description>&lt;p&gt;نص&lt;/p&gt;</description></item></channel></rss>""".encode("utf-8")
f = parse_feed(rss)
assert f[0]["title"] == "ندرة الزيت" and f[0]["summary"] == "نص" and f[0]["date"].year == 2026

# تجميع Google News: وسم <source> وإزالة اسم الناشر من العنوان وإسقاط التكرار
import fetch_news
gn = """<?xml version='1.0'?><rss version='2.0'><channel>
<item><title>ندرة الزيت في الأسواق - التلفزيون الجزائري</title><link>https://news.google.com/rss/articles/AAA</link>
<pubDate>Sun, 08 Nov 2026 01:00:00 +0000</pubDate><description>x</description><source url="https://entv.dz">التلفزيون الجزائري</source></item>
<item><title>ندرة الزيت في الأسواق - الإذاعة الجزائرية</title><link>https://news.google.com/rss/articles/BBB</link>
<pubDate>Sun, 08 Nov 2026 01:05:00 +0000</pubDate><description>x</description><source url="https://radioalgerie.dz">الإذاعة الجزائرية</source></item>
</channel></rss>""".encode("utf-8")
assert parse_feed(gn)[0]["src"] == "التلفزيون الجزائري"
from datetime import datetime, timezone
fetch_news.ALL_SOURCES = [("تجميع: ندرة", ["u"])]
fetch_news.http_get = lambda u, timeout=15: gn.replace(b"Sun, 08 Nov 2026", datetime.now(timezone.utc).strftime("%a, %d %b %Y").encode())
fetch_news.time.sleep = lambda s: None
rows = fetch_news.collect(verbose=False)
assert len(rows) == 1, rows                       # الخبران بعنوان واحد → خبر واحد
assert rows[0]["source_name"] == "التلفزيون الجزائري" and rows[0]["title"] == "ندرة الزيت في الأسواق", rows

print("\nفشل:", bad)
raise SystemExit(1 if bad else 0)
