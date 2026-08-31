-- Run this file in the Supabase SQL Editor before migrating existing users.
-- It enables Supabase Auth integration and Row Level Security for MediAI.

begin;

-- Passwords are managed by Supabase Auth after this migration.
alter table public.users
drop column if exists password_hash;

-- New Auth users receive a matching profile row with the same UUID.
create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
declare
    profile_username text;
begin
    profile_username := coalesce(
        nullif(btrim(new.raw_user_meta_data ->> 'username'), ''),
        split_part(new.email, '@', 1)
    );

    insert into public.users (id, username, email)
    values (new.id, profile_username, lower(new.email))
    on conflict (id) do update
    set username = excluded.username,
        email = excluded.email;

    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.handle_new_auth_user();

-- Connect public user profiles to Supabase Auth identities.
do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'users_auth_user_id_fkey'
    ) then
        alter table public.users
        add constraint users_auth_user_id_fkey
        foreign key (id) references auth.users(id)
        not valid;
    end if;
end $$;

alter table public.users enable row level security;
alter table public.specialties enable row level security;
alter table public.doctors enable row level security;
alter table public.reviews enable row level security;
alter table public.reviews_summary enable row level security;

-- Remove broad API privileges before granting only what the application needs.
revoke all on table public.users from anon, authenticated;
revoke all on table public.specialties from anon, authenticated;
revoke all on table public.doctors from anon, authenticated;
revoke all on table public.reviews from anon, authenticated;
revoke all on table public.reviews_summary from anon, authenticated;

grant select (id, username) on table public.users to anon, authenticated;
grant select on table public.specialties to anon, authenticated;
grant select on table public.doctors to anon, authenticated;
grant select on table public.reviews to anon, authenticated;
grant insert, delete on table public.reviews to authenticated;
grant select on table public.reviews_summary to anon, authenticated;
grant usage, select on sequence public.reviews_id_seq to authenticated;

drop policy if exists "Public profiles are readable" on public.users;
create policy "Public profiles are readable"
on public.users
for select
to anon, authenticated
using (true);

drop policy if exists "Specialties are publicly readable" on public.specialties;
create policy "Specialties are publicly readable"
on public.specialties
for select
to anon, authenticated
using (true);

drop policy if exists "Doctors are publicly readable" on public.doctors;
create policy "Doctors are publicly readable"
on public.doctors
for select
to anon, authenticated
using (true);

drop policy if exists "Reviews are publicly readable" on public.reviews;
create policy "Reviews are publicly readable"
on public.reviews
for select
to anon, authenticated
using (true);

drop policy if exists "Authenticated users can create own reviews" on public.reviews;
create policy "Authenticated users can create own reviews"
on public.reviews
for insert
to authenticated
with check ((select auth.uid()) = user_id);

drop policy if exists "Authenticated users can delete own reviews" on public.reviews;
create policy "Authenticated users can delete own reviews"
on public.reviews
for delete
to authenticated
using ((select auth.uid()) = user_id);

drop policy if exists "Review summaries are publicly readable" on public.reviews_summary;
create policy "Review summaries are publicly readable"
on public.reviews_summary
for select
to anon, authenticated
using (true);

commit;

alter table public.users
validate constraint users_auth_user_id_fkey;
