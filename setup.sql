-- وين لقيتها؟ — إعداد قاعدة البيانات على Supabase
-- شغّل هذا الملف كاملاً في: Supabase > SQL Editor > New query > Run
-- لا يلمس أي جداول أخرى في مشروعك القديم (كل الأسماء تبدأ بـ wl_).

create table if not exists public.wl_reports (
  id         bigint generated always as identity primary key,
  item       text not null check (item in (
               'milk','baby_milk','oil','semolina','flour','bread','sugar','coffee',
               'eggs','chicken','rice','pasta','water','butane','fuel','medicine',
               'diapers','cash')),
  status     text not null check (status in ('available','out')),
  lat        double precision not null check (lat between -90 and 90),
  lng        double precision not null check (lng between -180 and 180),
  place      text check (place is null or char_length(place) <= 40),
  device_id  text not null check (char_length(device_id) between 8 and 64),
  created_at timestamptz not null default now()
);

create index if not exists wl_reports_created_idx on public.wl_reports (created_at desc);
create index if not exists wl_reports_geo_idx     on public.wl_reports (lat, lng);

alter table public.wl_reports enable row level security;

-- الزائر المجهول يقرأ البلاغات الحديثة فقط (آخر 12 ساعة)
drop policy if exists "wl read recent" on public.wl_reports;
create policy "wl read recent" on public.wl_reports
  for select to anon, authenticated
  using (created_at > now() - interval '12 hours');

-- والزائر المجهول يضيف بلاغاً جديداً فقط (لا تعديل ولا حذف)
drop policy if exists "wl insert" on public.wl_reports;
create policy "wl insert" on public.wl_reports
  for insert to anon, authenticated
  with check (true);

-- صلاحيات على مستوى الأعمدة: معرّف الجهاز لا يظهر للعموم أبداً
revoke all on public.wl_reports from anon, authenticated;
grant select (id, item, status, lat, lng, place, created_at) on public.wl_reports to anon, authenticated;
grant insert (item, status, lat, lng, place, device_id)      on public.wl_reports to anon, authenticated;

-- حد المعدل: 20 بلاغاً في الساعة لكل جهاز، و3 بلاغات فقط لنفس السلعة في نفس المكان خلال 10 دقائق
create or replace function public.wl_limit_reports()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if (select count(*) from public.wl_reports
        where device_id = new.device_id
          and created_at > now() - interval '1 hour') >= 20 then
    raise exception 'rate limit: too many reports';
  end if;

  if (select count(*) from public.wl_reports
        where device_id = new.device_id
          and item = new.item
          and abs(lat - new.lat) < 0.002
          and abs(lng - new.lng) < 0.002
          and created_at > now() - interval '10 minutes') >= 3 then
    raise exception 'rate limit: duplicate reports';
  end if;

  return new;
end;
$$;

drop trigger if exists wl_limit_trg on public.wl_reports;
create trigger wl_limit_trg
  before insert on public.wl_reports
  for each row execute function public.wl_limit_reports();

-- تنظيف اختياري: احذف البلاغات الأقدم من يومين (شغّله يدوياً أو اجعله Cron من Database > Cron)
-- delete from public.wl_reports where created_at < now() - interval '2 days';
