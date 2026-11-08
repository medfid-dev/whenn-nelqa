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
    "مرضى السكري يشتكون من غلاء الأنسولين",                       # «السكري» ليست «السكر»
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

print("\nفشل:", bad)
raise SystemExit(1 if bad else 0)
