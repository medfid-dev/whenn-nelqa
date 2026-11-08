-- وين لقيتها؟ — جدول أخبار الندرة من المصادر العامة (إضافة، لا تلمس wl_reports)
-- شغّله مرة واحدة في Supabase > SQL Editor بعد setup.sql

create table if not exists public.wl_news (
  id           bigint generated always as identity primary key,
  item         text not null check (char_length(item) between 2 and 30),
  status       text not null check (status in ('out','available','mixed')),
  wilayas      text[] not null default '{}',
  title        text not null check (char_length(title) <= 250),
  source_name  text not null check (char_length(source_name) <= 60),
  source_url   text not null check (source_url ~ '^https?://' and char_length(source_url) <= 600),
  published_at timestamptz not null,
  created_at   timestamptz not null default now(),
  unique (source_url, item)
);

create index if not exists wl_news_pub_idx on public.wl_news (published_at desc);

alter table public.wl_news enable row level security;

-- القراءة العامة: أخبار آخر 48 ساعة فقط
drop policy if exists "wl news read" on public.wl_news;
create policy "wl news read" on public.wl_news
  for select to anon, authenticated
  using (published_at > now() - interval '48 hours');

-- لا سياسة إدراج: الكتابة تتم فقط بمفتاح service_role من GitHub Actions
revoke all on public.wl_news from anon, authenticated;
grant select (id, item, status, wilayas, title, source_name, source_url, published_at)
  on public.wl_news to anon, authenticated;
