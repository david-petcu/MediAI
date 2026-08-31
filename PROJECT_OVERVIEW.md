# MediAI Project Overview

Acest fisier rezuma rolul fiecarui fisier de cod important din proiect si fluxurile principale ale aplicatiei.

## Structura generala

MediAI este o aplicatie Streamlit conectata la Supabase/PostgreSQL. Utilizatorii pot cauta doctori, pot vedea profiluri, pot adauga review-uri si pot sterge propriile review-uri. Review-urile sunt analizate cu Groq AI pentru tag-uri, scor de consistenta si sumar AI pe profilul doctorului.

## Fisiere principale din root

### `app.py`

Fisierul de pornire al aplicatiei Streamlit. Seteaza configurarea principala a paginii si redirectioneaza utilizatorul catre pagina de cautare a doctorilor.

### `database.py`

Initializeaza clientul public Supabase, clientii autentificati per sesiune si clientul administrativ folosit doar de scripturile server-side.

Citeste din `.env`:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `SUPABASE_SECRET_KEY`

Aplicatia publica necesita primele doua variabile. Worker-ele AI si scripturile de mentenanta necesita si `SUPABASE_SECRET_KEY`, pastrata numai pe server.

### `auth_session.py`

Pastraza tokenurile Supabase Auth in sesiunea Streamlit si creeaza un client autentificat separat pentru fiecare utilizator.

### `sidebar.py`

Contine functia care deseneaza meniul lateral al aplicatiei. In functie de starea utilizatorului, afiseaza linkuri catre paginile principale si optiuni de autentificare/logout.

### `seed_database.py`

Populeaza baza de date cu date demo:

- specialitati medicale;
- doctori;
- useri seed;
- identitati gestionate prin Supabase Auth;
- randuri initiale in `reviews_summary`.

Este gandit pentru initializarea unei baze goale.

### `supabase_auth_rls.sql`

Adauga triggerul pentru profilurile utilizatorilor, activeaza RLS si permite inserarea sau stergerea unui review numai proprietarului autentificat.

### `smart_import.py`

Importa review-uri din CSV-ul german, le curata, le traduce in engleza, le anonimizeaza si le asociaza cu doctori din baza de date.

Face:

- citirea CSV-ului;
- eliminarea HTML-ului din texte;
- filtrarea review-urilor prea scurte;
- traducere si anonimizare prin Groq;
- alegerea specialitatii potrivite;
- distribuirea echilibrata intre doctori;
- distribuirea userilor seed in mod round-robin;
- inserarea review-urilor in Supabase.

In varianta actuala este pregatit sa importe `300` review-uri pentru o baza de date goala.

### `ai_engine.py`

Contine functiile de comunicare cu Groq API.

Functii principale:

- `call_groq()` trimite prompturi catre Groq si intoarce raspunsul modelului.
- `analyze_review_full()` extrage `ai_tags` si estimeaza ratingul AI pentru un review.
- `generate_doctor_summary()` genereaza un sumar scurt pentru profilul doctorului pe baza review-urilor recente.

### `ai_worker.py`

Proceseaza review-urile noi adaugate din aplicatia Streamlit.

Roluri:

- porneste un thread de background dupa submit;
- trimite review-ul la AI;
- salveaza `ai_tags` si `consistency_score`;
- recalculeaza `average_rating` si `review_count`;
- genereaza un nou AI Summary pentru doctor;
- actualizeaza tabela `reviews_summary`;
- regenereaza summary-ul dupa stergerea unui review.

### `ai_batch_processor.py`

Proceseaza manual review-urile ramase neanalizate, adica cele cu:

```text
ai_tags = null
```

Este util daca aplicatia Streamlit se opreste inainte ca worker-ul de background sa termine.

Face:

- cauta review-uri neprocesate;
- genereaza `ai_tags`;
- calculeaza `consistency_score`;
- actualizeaza review-urile;
- recalculeaza summary-ul doctorilor afectati.

Se ruleaza manual:

```powershell
.\.venv\Scripts\python.exe .\ai_batch_processor.py
```

### `ai_summary_generator.py`

Regenereaza manual summary-urile pentru toti doctorii.

Este util cand vrei sa refaci complet `reviews_summary` dupa importuri mari sau modificari de date.

Face:

- parcurge toti doctorii;
- ia review-urile fiecarui doctor;
- calculeaza rating mediu si numar de review-uri;
- genereaza summary AI;
- actualizeaza tabela `reviews_summary`.

### `db_validations.sql`

Script SQL pentru validari la nivel de baza de date.

Adauga constrangeri pentru:

- username nevid;
- email lowercase;
- email cu format de baza valid;
- nume doctor nevid;
- stamp doctor format din exact 6 cifre;
- review text nevid;
- `consistency_score` intre 0 si 1;
- `ai_tags` ca array JSONB;
- rating mediu intre 0 si 5;
- `review_count` nenegativ.

### `requirements.txt`

Lista dependintelor Python ale proiectului:

- Streamlit;
- Supabase client;
- Groq client;
- Supabase Auth;
- pandas;
- python-dotenv;
- requests.

Se foloseste pentru refacerea mediului virtual:

```powershell
pip install -r requirements.txt
```

## Pagini Streamlit

### `pages/0_Login.py`

Pagina de login si sign up.

Face:

- autentificare cu email si parola;
- normalizarea emailului cu `strip().lower()`;
- verificarea parolei prin Supabase Auth;
- inregistrarea userilor noi;
- stocarea tokenurilor de sesiune in `st.session_state`;
- folosirea JWT-ului utilizatorului pentru politicile RLS.

### `pages/1_Search.py`

Pagina de cautare a doctorilor.

Face:

- afiseaza lista de doctori;
- permite cautare dupa nume;
- permite filtrare dupa specialitate;
- permite sortare dupa recomandare, rating sau numar de review-uri;
- afiseaza rating, numar de review-uri, stamp code si AI Score;
- calculeaza AI Recommendation Score din rating, trust score si popularitate;
- trimite userul catre profilul doctorului selectat.

### `pages/2_Profile.py`

Pagina de profil a doctorului.

Face:

- afiseaza numele doctorului, specialitatea si stamp code-ul;
- afiseaza ratingul mediu, numarul de review-uri si AI Recommendation Score;
- citeste live datele din `reviews_summary`;
- afiseaza AI Summary;
- extrage Patient Highlights din `ai_tags`;
- afiseaza lista review-urilor;
- afiseaza AI Trust Score pentru fiecare review;
- marcheaza review-urile cu scor de consistenta scazut.

### `pages/3_Add_Review.py`

Pagina pentru adaugarea unui review.

Face:

- verifica daca userul este logat;
- incarca lista doctorilor;
- permite alegerea doctorului;
- permite alegerea ratingului;
- valideaza ca textul review-ului nu este gol;
- insereaza review-ul in Supabase;
- porneste `ai_worker.py` in background;
- curata cache-ul Streamlit;
- afiseaza mesajul ca analiza AI este in progres.

### `pages/4_User_Profile.py`

Pagina profilului userului logat.

Face:

- afiseaza review-urile userului;
- afiseaza ratingul si AI Trust Score pentru fiecare review;
- permite stergerea propriilor review-uri;
- sterge review-ul doar daca apartine userului logat;
- recalculeaza `average_rating` si `review_count`;
- porneste regenerarea summary-ului doctorului dupa delete;
- afiseaza mesaj de succes dupa stergere.

## Fluxuri principale

### 1. Adaugarea unui review

```text
User -> Add Review page -> Supabase reviews -> ai_worker.py -> Groq -> reviews + reviews_summary
```

Rezultat:

- review-ul apare in baza de date;
- AI genereaza tag-uri;
- se calculeaza AI Trust Score;
- profilul doctorului primeste summary actualizat.

### 2. Stergerea unui review

```text
User Profile -> Supabase reviews delete -> reviews_summary rating/count update -> ai_worker.py summary regeneration
```

Rezultat:

- review-ul este sters;
- ratingul si numarul de review-uri se actualizeaza;
- AI Summary se regenereaza pentru doctor.

### 3. Importul initial al datelor

```text
seed_database.py -> smart_import.py -> ai_batch_processor.py
```

Ordine recomandata pentru baza goala:

```powershell
.\.venv\Scripts\python.exe .\seed_database.py
.\.venv\Scripts\python.exe .\smart_import.py
.\.venv\Scripts\python.exe .\ai_batch_processor.py
```

### 4. Regenerarea completa a summary-urilor

```powershell
.\.venv\Scripts\python.exe .\ai_summary_generator.py
```

Se foloseste doar cand vrei sa refaci summary-urile pentru toti doctorii, nu la fiecare review normal.

## Observatii importante

- Parolele si sesiunile sunt gestionate de Supabase Auth. Tabela publica `users` nu stocheaza parole sau hash-uri de parole.
- RLS permite inserarea si stergerea review-urilor numai cand `auth.uid()` corespunde cu `user_id`.
- `ai_tags` sunt salvate ca JSONB array.
- `Petcu David` nu este user seed si nu este folosit de importul automat.
- Worker-ul AI ruleaza in thread de background cu `daemon=True`.
- Daca un review ramane neprocesat, `ai_batch_processor.py` poate recupera analiza.
- Pentru demo/licenta, structura este suficient de clara si usor de explicat.
