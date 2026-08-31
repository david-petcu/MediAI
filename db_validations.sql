-- Run this in the Supabase SQL Editor.
-- The script is idempotent: it only adds constraints that do not already exist.

do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'users_username_not_empty') then
        alter table public.users
        add constraint users_username_not_empty
        check (length(btrim(username)) >= 2);
    end if;

    if not exists (select 1 from pg_constraint where conname = 'users_email_lowercase') then
        alter table public.users
        add constraint users_email_lowercase
        check (email = lower(email));
    end if;

    if not exists (select 1 from pg_constraint where conname = 'users_email_basic_format') then
        alter table public.users
        add constraint users_email_basic_format
        check (email ~* '^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$');
    end if;

    if not exists (select 1 from pg_constraint where conname = 'doctors_full_name_not_empty') then
        alter table public.doctors
        add constraint doctors_full_name_not_empty
        check (length(btrim(full_name)) >= 2);
    end if;

    if not exists (select 1 from pg_constraint where conname = 'doctors_stamp_six_digits') then
        alter table public.doctors
        add constraint doctors_stamp_six_digits
        check (stamp is not null and stamp ~ '^[0-9]{6}$');
    end if;

    if not exists (select 1 from pg_constraint where conname = 'specialties_name_not_empty') then
        alter table public.specialties
        add constraint specialties_name_not_empty
        check (length(btrim(name)) >= 2);
    end if;

    if not exists (select 1 from pg_constraint where conname = 'reviews_text_not_empty') then
        alter table public.reviews
        add constraint reviews_text_not_empty
        check (length(btrim(review_text)) > 0);
    end if;

    if not exists (select 1 from pg_constraint where conname = 'reviews_consistency_score_range') then
        alter table public.reviews
        add constraint reviews_consistency_score_range
        check (consistency_score is null or consistency_score between 0 and 1);
    end if;

    if not exists (select 1 from pg_constraint where conname = 'reviews_ai_tags_array') then
        alter table public.reviews
        add constraint reviews_ai_tags_array
        check (ai_tags is null or jsonb_typeof(ai_tags) = 'array');
    end if;

    if not exists (select 1 from pg_constraint where conname = 'reviews_summary_rating_range') then
        alter table public.reviews_summary
        add constraint reviews_summary_rating_range
        check (average_rating is null or average_rating between 0 and 5);
    end if;

    if not exists (select 1 from pg_constraint where conname = 'reviews_summary_count_nonnegative') then
        alter table public.reviews_summary
        add constraint reviews_summary_count_nonnegative
        check (review_count is null or review_count >= 0);
    end if;
end $$;

-- Enforces one review per user, per doctor, per UTC calendar day.
create unique index if not exists reviews_user_doctor_day_unique
on public.reviews (
    user_id,
    doctor_id,
    ((created_at at time zone 'UTC')::date)
);
