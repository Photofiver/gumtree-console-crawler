---
name: google-ai-second-opinion
description: 'Use when Google AI Konsultant is selected. ChatGPT researches, chooses, revises and resubmits; GitHub only screens configurations and transports real Google AI reviews.'
---

# Google AI Konsultant 1.8.15 — ChatGPT rozwiązuje i poprawia; GitHub transportuje

## Nadrzędna zasada i odpowiedzialności

**Wyłącznym autorem rozwiązania oraz poprawek jest ChatGPT, NIE skrypt GitHub.** Google AI jest niezależnym recenzentem, może wykrywać braki i błędy; jego odpowiedzi nie są same w sobie dowodami. GitHub Actions obsługuje połączenie z Google AI, raport z realnych zapytań/odpowiedzi, obliczeniowy przesiew konfiguracji oraz zewnętrzne Attention. Nie wymyśla cen, nie wybiera za ChatGPT rozwiązania i nie stosuje automatycznych zmian tekstu.

Wprowadzone w 1.8.15 pole correction_owner=chatgpt i next_action=chatgpt_research_revise_and_resubmit są sygnałem dla ChatGPT, nie dowodem wykonania korekty. Nie wystawiaj pozytywnej oceny za samą obecność tych pól.

## Obowiązkowy proces gdy wtyczka została uruchomiona

1. ChatGPT zbiera **wszystkie aktualne wymagania** użytkownika i ocenia, czy cel ma sens techniczny; nigdy nie stosuje starego limitu ceny z poprzedniego zadania. Gdy budżet bez górnej granicy, utrzymuje budget_mode=uncapped.
2. ChatGPT samodzielnie wyszukuje i **otwiera** rzeczywiste oferty, instrukcje i karty techniczne, porównuje modele, ceny oraz akcesoria. Brak źródła oznacza brak dowodu, nie nieistnienie produktu.
3. ChatGPT tworzy konkretny szkic odpowiedzi, pełną checklistę warunków i candidate_log z rzeczywiście znalezionymi modelami. W przypadku zadania z 1000 wariantów przekazuje idea_target=1000; GitHub jedynie oblicza kombinacje i ich wstępny przesiew, nie wykonuje 1000 prawdziwych zakupów.
4. ChatGPT publikuje nowe publiczne issue [consult] w Photofiver/gumtree-console-crawler z obiektem JSON zawierającym question, draft, checks (każdy z requirement, status, finding, ewentualnie source i quote), a przy porównaniach także candidate_log, search_log, feasibility i idea_target. Nie przesyła do publicznego issue poufnych danych.
5. GitHub uruchamia Attention i obliczenia, wysyła szkic do Google AI, a następnie zwraca do ChatGPT **oryginalny werdykt i konkretne powody** w komentarzu Konsultant/2. Dla audytu wielu części sprawdź reviewed, parts, failed_parts i unreadable_parts. Nie myl PASS fragmentu z kompletnym zestawem.
6. Gdy review=DO POPRAWY, status=NIEPOTWIERDZONE lub są niespełnione warunki, **ChatGPT sam** ocenia każdą uwagę Google AI: sprawdza ją ze źródłami, poszukuje brakujących danych, zmienia model/konfigurację gdy to konieczne, wylicza koszty i przygotowuje **cały nowy szkic**. Nie przekazuje tego skryptowi GitHub do automatycznej korekty.
7. ChatGPT zakłada następne issue [consult] z nowym draft, niezmienionym pełnym question i checks uaktualnionymi wyłącznie o faktycznie zweryfikowane dowody. Dodaje parent_issue wskazujący poprzedni numer, review_round i faktyczną diagnozę zmian. **Każda zmiana wymaga osobnej rzeczywistej recenzji Google AI.**
8. ChatGPT powtarza badanie → poprawę → nowy audyt w ramach aktualnego zadania, kiedy poprawki mają rzeczywistą podstawę i są dostępne narzędzia oraz czas. Nie zatrzymuje się tylko dlatego, że pierwsza propozycja została odrzucona; nie zapętla identycznej odpowiedzi i nie obiecuje nieskończonej pracy w tle.
9. Wynik POTWIERDZONE wolno ogłosić wyłącznie, gdy wszystkie twarde warunki **jednej konkretnej konfiguracji** mają niezależne dowody, Google AI faktycznie ją oceniło i nie ma niewyjaśnionych sprzeczności. Jeśli cel jest fizycznie niewykonalny w żądanych warunkach lub brakuje dostępnych potwierdzeń, należy jasno powiedzieć NIEPOTWIERDZONE, wskazać najbliższy wariant i realną przeszkodę, bez fałszywego sukcesu.
10. W raporcie rozróżniaj: znalezione produkty, przesiane matematyczne konfiguracje, potwierdzone ceny i podzespoły, liczba zapytań/odpowiedzi Google AI, numery issue i faktyczny końcowy werdykt.

## S700 — zachowaj dokładnie obecny cel użytkownika

Stacja ALLPOWERS S700 ma 606 Wh, wejście Anderson 12,7–24 V, maks. 5 A i 100 W; pozostaje wewnątrz domu. Panele są sztywne, odporne na pogodę i montowane na zewnątrz w Belfaście. Zakupy tylko Amazon UK lub Argos; obecne żądanie to **panele również droższe niż £100 i brak górnego limitu budżetu**. Wymagane są sprawdzenie zimnego Voc, Isc, kompatybilności napięcia i prądu, poprawnej polaryzacji, przetwornicy/MPPT, przewodów, złączy, zabezpieczeń, mocowań i łącznego kosztu. Sprawdź rzeczywisty dzienny bilans energii i clipping do 100 W; nie zakładaj idealnego słońca ani gwarantowanego ładowania podczas każdego mocno pochmurnego 48-godzinnego okresu.

Jeżeli jeden produkt nie jest odpowiedni, ChatGPT sprawdza kolejne modele i metody: panel bezpośredni, równoległe, szeregowe, przetwornica z ograniczeniem parametrów wyjścia, inne zgodne wejścia, bufor/hybryda i porównanie rynku. Znane niezgodności elektryczne i brak potwierdzonego osprzętu muszą być jawnie raportowane. Liczby z przesiewu GitHub nie są dowodem kompatybilności.

## Egzekwowanie, ograniczenia i uczciwe raportowanie

Plugin zawiera hook review_turn.py, który w obsługiwanych środowiskach przekazuje ChatGPT obowiązek dokonania samodzielnej poprawy i ponownego wysłania analizy po negatywnej recenzji. Jest to instrukcja/procedura, a nie techniczna modyfikacja modelu GPT: środowisko ChatGPT nie musi uruchamiać hooków we wszystkich klientach ani wywoływać tego pluginu dla każdej wiadomości. Nie zapewnia to samoczynnej pracy po zakończeniu odpowiedzi.

Silnik produkcyjny phone_google_ask/consult.py korzysta z review_for_chatgpt(), który wykonuje wyłącznie autentyczną ocenę Google AI i zwraca niezmieniony szkic. Starszy solve() pozostaje wyłącznie na potrzeby zgodności i starych testów; nie może być drogą produkcyjną do samodzielnego poprawiania tekstu przez GitHub.

Po DO POPRAWY nie kopiuj bezkrytycznie słów Google AI — sprawdź, czy krytyka nie wynika z podziału materiału na fragmenty i czy źródła rzeczywiście ją potwierdzają. Jeżeli Google AI nie zwrócił sprawdzalnej odpowiedzi, napisz, że brak potwierdzenia; nie deklaruj PASS. Zakończ tylko odpowiedzią popartą prawdziwymi testami i źródłami.
