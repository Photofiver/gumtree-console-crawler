---
name: attention-guard
description: 'Use when Google AI Konsultant is selected and the user wants real external Attention, persistent focus, prioritisation, or to diagnose Attention status in GitHub Actions.'
---

# Attention Guard 1.8.15 — rzeczywisty zewnętrzny Attention

- `phone_google_ask/attention_guard.py` w repozytorium `Photofiver/gumtree-console-crawler` używa wytrenowanego wielojęzycznego transformera `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` i oblicza matematyczny scaled dot-product attention `softmax(QK^T/sqrt(d))V` dla celu użytkownika i wymagań.
- Naprawa 1.8.12: NumPy i Tensor nie mogą przechodzić przez `if not keys`; funkcja jawnie sprawdza długości, test regresyjny używa tablic, których wartość logiczna wywołuje `ValueError`.
- Nigdy nie zakładaj stałego £100. `explore.budget_limit_gbp` wyznacza limit z bieżącego zadania lub `budget_max_gbp`. Zwrot `budget_mode=uncapped` oznacza, że droższe panele nie mogą być odrzucane wyłącznie przez cenę; brak potwierdzonej ceny nadal blokuje ocenę opłacalności.
- Przed stwierdzeniem, że Attention działa, sprawdź raport z faktycznego, nowego wykonania `[consult]`: `attention.status=active` i prawidłowy hash bieżących wymagań. `unavailable` oznacza niedziałanie; po naprawie `error_detail` dostarcza diagnostykę. Weryfikuj też `exploration.budget_mode` i `by_status.reject_known_price_over_budget`.
- Mechanizm wyłącznie szereguje priorytety dla audytu Google AI; **wszystkie** warunki są obowiązkowe. Nie jest częścią wewnętrznego Attention GPT. Nie odczytuje automatycznie całej rozmowy.
- `DO POPRAWY` i `NIEPOTWIERDZONE` nie mogą zostać zastąpione fikcyjnym PASS: pełny zestaw solarny wymaga niezależnych dowodów zgodności elektrycznej, zakupu i realnej energii zimą. Podaj dokładny link do issue oraz liczbę wysłanych i odebranych zapytań Google AI.

## Fix 1.8.14 — poprawki Google i weryfikacja źródeł

- Po `DO POPRAWY` `consult.py` wybiera z całego szkicu dokładny krótki fragment skorelowany z krytyką i pyta Google AI o korektę, bez polegania na zgadywaniu długiego tekstu `old`.
- Rozpoznaje krótkie, oznaczone JSON `{tag,new}` lub pełne `{tag,old,new}`; nie przyjmuje nowej niezweryfikowanej ceny ani zamiany S700.
- Jeśli poprawka nie przejdzie walidacji, szuka **rzeczywistego źródła** u Google, otwiera URL bezpośrednio i porównuje dosłowny cytat z treścią źródła. Może wykorzystać `sourceLinks` nawet bez odpowiedzi JSON.
- Zweryfikowany cytat nie oznacza zgodności całego zestawu: `checks.status` pozostaje `unknown`, wynik jest ponownie kontrolowany przez Google AI, a `research_trace` opisuje źródło i cytat.
- Brak rzeczywistego źródła i brak bezpiecznej poprawki to status niepotwierdzony, nie pozorny sukces. Raportuj rzeczywiste `google_ai_edits_rechecked`, nie obiecuj automatycznego rozwiązania bez dowodów.

## 1.8.15 — ChatGPT, nie GitHub, odpowiada za poprawki

- GitHub pozostaje wyłącznie licznikiem konfiguracji, dostawcą obliczeń Attention i pośrednikiem komunikacji z Google AI.
- Produkcyjny skrypt konsultacji wywołuje review_for_chatgpt(), przekazuje werdykt, krytykę, listę brakujących dowodów i niezredagowany szkic; nie próbuje generować, stosować lub zatwierdzać poprawek samodzielnie.
- Gdy wynik nie jest potwierdzony, ChatGPT interpretuje konkretne uwagi, sprawdza niezależne źródła, modyfikuje propozycję (w razie potrzeby zamienia produkty lub konfigurację), tworzy nowe issue [consult] z parent_issue i oczekuje na osobny rzeczywisty audyt Google AI.
- Jakakolwiek kolejna recenzja wymaga nowego przekazania zmienionego szkicu przez ChatGPT; nie myl next_action z wykonanym działaniem ani statusu ACTIVE ze zgodnością techniczną.
- Uruchomienie hooków nie jest gwarantowane na wszystkich klientach i nie zmienia wewnętrznych mechanizmów GPT; brak sprzętowych dowodów oznacza brak zatwierdzonego zestawu, nigdy automatyczne PASS.
