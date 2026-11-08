-- وين لقيتها؟ — ترقية جدول wl_news لدعم أخبار الأسعار (غلاء / انخفاض)
-- شغّله مرة واحدة في Supabase > SQL Editor إن كان الجدول موجوداً من قبل. آمن لإعادة التشغيل، ولا يحذف بيانات.

alter table public.wl_news drop constraint if exists wl_news_status_check;
alter table public.wl_news add constraint wl_news_status_check
  check (status in ('out','available','mixed','price_up','price_down'));

alter table public.wl_news drop constraint if exists wl_news_source_url_item_key;
alter table public.wl_news drop constraint if exists wl_news_source_item_status_key;
alter table public.wl_news add constraint wl_news_source_item_status_key
  unique (source_url, item, status);
