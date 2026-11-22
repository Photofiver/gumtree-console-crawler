---
name: attention-guard
description: 'Use when Google AI Konsultant is selected and the user wants real external Attention, persistent focus, prioritisation, or to diagnose Attention status in GitHub Actions.'
---

# Attention Guard 1.8.12 — rzeczywisty zewnętrzny Attention

- `phone_google_ask/attention_guard.py` w repozytorium `Photofiver/gumtree-console-crawler` używa wytrenowanego wielojęzycznego transformera `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` i oblicza matematyczny scaled dot-product attention `softmax(QK^T/sqrt(d))V` dla celu użytkownika i wymagań.
- Naprawa 1.8.12: NumPy i Tensor nie mogą przechodzić przez `if not keys`; funkcja jawnie sprawdza długości, test regresyjny używa tablic, których wartość logiczna wywołuje `ValueError`.
- Nigdy nie zakładaj stałego £100. `explore.budget_limit_gbp` wyznacza limit z bieżącego zadania lub `budget_max_gbp`. Zwrot `budget_mode=uncapped` oznacza, że droższe panele nie mogą być odrzucane wyłącznie przez cenę; brak potwierdzonej ceny nadal blokuje ocenę opłacalności.
- Przed stwierdzeniem, że Attention działa, sprawdź raport z faktycznego, nowego wykonania `[consult]`: `attention.status=active` i prawidłowy hash bieżących wymagań. `unavailable` oznacza niedziałanie; po naprawie `error_detail` dostarcza diagnostykę. Weryfikuj też `exploration.budget_mode` i `by_status.reject_known_price_over_budget`.
- Mechanizm wyłącznie szereguje priorytety dla audytu Google AI; **wszystkie** warunki są obowiązkowe. Nie jest częścią wewnętrznego Attention GPT. Nie odczytuje automatycznie całej rozmowy.
- `DO POPRAWY` i `NIEPOTWIERDZONE` nie mogą zostać zastąpione fikcyjnym PASS: pełny zestaw solarny wymaga niezależnych dowodów zgodności elektrycznej, zakupu i realnej energii zimą. Podaj dokładny link do issue oraz liczbę wysłanych i odebranych zapytań Google AI.
