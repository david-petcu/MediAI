-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.specialties (
  name character varying NOT NULL UNIQUE CHECK (length(btrim(name::text)) >= 2),
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  CONSTRAINT specialties_pkey PRIMARY KEY (id)
);
CREATE TABLE public.users (
  email character varying NOT NULL UNIQUE CHECK (email::text = lower(email::text)),
  created_at timestamp with time zone DEFAULT now(),
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  username character varying NOT NULL UNIQUE CHECK (length(btrim(username::text)) >= 2),
  CONSTRAINT users_pkey PRIMARY KEY (id),
  CONSTRAINT users_auth_user_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id)
);
CREATE TABLE public.doctors (
  specialty_id uuid NOT NULL,
  full_name character varying NOT NULL CHECK (length(btrim(full_name::text)) >= 2),
  stamp character varying UNIQUE CHECK (stamp IS NOT NULL AND stamp::text ~ '^[0-9]{6}$'::text),
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  CONSTRAINT doctors_pkey PRIMARY KEY (id),
  CONSTRAINT doctors_specialty_id_fkey FOREIGN KEY (specialty_id) REFERENCES public.specialties(id)
);
CREATE TABLE public.reviews (
  review_text text NOT NULL CHECK (length(btrim(review_text)) > 0),
  ai_tags jsonb CHECK (ai_tags IS NULL OR jsonb_typeof(ai_tags) = 'array'::text),
  consistency_score double precision CHECK (consistency_score IS NULL OR consistency_score >= 0::double precision AND consistency_score <= 1::double precision),
  id bigint NOT NULL DEFAULT nextval('reviews_id_seq'::regclass),
  created_at timestamp with time zone DEFAULT now(),
  user_id uuid NOT NULL,
  doctor_id uuid NOT NULL,
  stars integer NOT NULL CHECK (stars >= 1 AND stars <= 5),
  CONSTRAINT reviews_pkey PRIMARY KEY (id),
  CONSTRAINT reviews_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id),
  CONSTRAINT reviews_doctor_id_fkey FOREIGN KEY (doctor_id) REFERENCES public.doctors(id)
);
CREATE TABLE public.reviews_summary (
  doctor_id uuid NOT NULL,
  summary text,
  average_rating double precision DEFAULT 0.0 CHECK (average_rating IS NULL OR average_rating >= 0::double precision AND average_rating <= 5::double precision),
  review_count integer DEFAULT 0 CHECK (review_count IS NULL OR review_count >= 0),
  CONSTRAINT reviews_summary_pkey PRIMARY KEY (doctor_id),
  CONSTRAINT reviews_summary_doctor_id_fkey FOREIGN KEY (doctor_id) REFERENCES public.doctors(id)
);