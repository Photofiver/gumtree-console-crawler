---
name: google-ai-second-opinion
description: 'Use when Google AI Konsultant is selected. For solution and product research, conduct active evidence-backed discovery across feasible configurations, challenge negative conclusions, then use GitHub Google AI to verify precise findings; never mistake approval of a narrow draft for an actual solution.'
---

# Google AI Konsultant — wersja 1.7.1: najpierw rozwiązanie, potem recenzja

## Cel i zasady

**Znalezienie wykonalnego rozwiązania jest celem. `SPRAWDZONE` od Google AI potwierdza wyłącznie konkretny oceniony szkic — nie jest sukcesem poszukiwań ani dowodem wyczerpania internetu.** Nie kończ tylko dlatego, że kilka pierwszych modeli nie pasuje albo Google AI zatwierdziło zdanie „nie znaleziono”. Szukaj kontrprzykładu, innej konfiguracji i zgodnych części; sprawdzaj źródła, parametry, koszty i wszystkie twarde ograniczenia użytkownika.

Nie wymyślaj produktów, cen, danych pogodowych, obejść zabezpieczeń ani źródeł. Nie proponuj niedozwolonego wariantu jako zgodnego. Ograniczony czas i dostępność narzędzi uniemożliwiają udowodnienie, że sprawdzono **wszystkie** oferty w internecie; nie twierdź tego. Nie pracuj w tle ani nie obiecuj wyniku później.

## Aktywny etap poszukiwań — nie zastępuj go samą konsultacją Google AI

1. Wyodrębnij wszystkie warunki użytkownika i rozróżnij: elektryczne bezpieczeństwo, cenę całego zestawu, sprzedawcę, użytkowanie, porę roku, **średnie** 48 h vs **każde** 48 h w zimie. Nie zmieniaj wymagań po cichu.
2. Zanim napiszesz negatywny szkic, użyj dostępnego wyszukiwania ofert/sklepów i źródeł producentów; sprawdzaj konkretne numery modeli, warianty, ceny, źródła techniczne, akcesoria, zgodność złączy, polaryzację, zimne Voc, dopuszczalny prąd i pełny koszt. Nie uznawaj samej nazwy Amazon albo etykiety „12 V” za dowód kompatybilności.
3. Jeśli pierwsza droga nie działa, **zmień konstrukcję poszukiwań**, nie tylko zapytanie o podobne panele. Dla ALLPOWERS S700 w Belfaście wykonaj oddzielnie poniższe 7 klas, o ile są relewantne, i udokumentuj każdą w `search_log` odpowiednim identyfikatorem `route`:
   - `direct_panel`: jeden panel sztywny, bezpośrednio zgodny z zimnym Voc i wejściem.
   - `parallel_panels`: panele równoległe, sumowanie prądu, ograniczniki i efekt obcinania.
   - `series_panels`: panele szeregowe, sumowanie napięcia, wymagania przetwornicy.
   - `regulated_converter`: większe pole PV przez regulator DC-DC/MPPT z bezpiecznym wyjściem dla stacji i stratami.
   - `other_input`: inne rzeczywiście obsługiwane wejścia i jednoczesne ładowanie wyłącznie po sprawdzeniu instrukcji konkretnej S700.
   - `buffer_or_hybrid`: bufor akumulatorowy lub hybryda, uwzględnij skąd pochodzi energia i dodatkowe koszty.
   - `market_comparison`: porównanie ofert Amazon UK/Argos, zestawów, kabli, wariantów i kosztu całkowitego.
4. Porównaj co najmniej **5 różnych konkretnych modeli/ofert** (jeśli tylko są dostępne); zapisz osobno `candidate_log` z `model`, `source`, `limitation`. Nie wypełniaj tabeli fikcyjnymi pozycjami; gdy naprawdę brak dostępnych modeli lub źródeł, nazwij lukę i podaj stan nierozstrzygnięty, nie tezę „nie istnieje”. Po nieudanym kandydacie sprawdzaj, czy jeden parametr można bezpiecznie zmienić przez dodatkową część w budżecie.
5. W `feasibility` dokumentuj `energy_balance`, `port_limits`, `weather_uncertainty`, `closest_option`, `unmet_requirement`. Modeluj zimowe uzyski energii w Wh i straty, uwzględniaj prąd/napięcie po konwersji oraz cenę **wszystkich** elementów. Zapytaj, czy podstawowe granice fizyczne wykluczają absolutne „każde 48 godzin” przy zerowym nasłonecznieniu: takiego terminu nie może zagwarantować wyłącznie solar niezależnie od liczby paneli. Nie myl tej gwarancji z możliwością ładowania w 48 godzin przy części zimowych warunków.
6. Gdy znaleziono kandydaturę, przeprowadź weryfikację **całego** zestawu: panel, regulator jeśli potrzebny, kabel, cena, biegunowość, Voc podczas mrozu, maksymalny prąd, dostępność i rzeczywisty uzysk. Jeśli jest zgodna — podaj jak ją podłączyć. Jeśli nie jest — zapisz powód, sprawdź następną opcję.
7. Użyj Google AI jako niezależnego recenzenta ustaleń. Zlecaj recenzję konkretnej alternatywy i próby obalenia negatywnej konkluzji, a nie wyłącznie obronę odmowy. Jeśli odrzuci dane, popraw i sprawdź znowu; jeśli zatwierdzi wąskie obliczenia, **nie** ogłaszaj całości za zweryfikowaną.

## Protokół wykonawczy 1.7.1

Po sprawdzeniu ofert otwórz w Photofiver/gumtree-console-crawler issue o prefiksie [consult]. Jeżeli hook nadał tytuł, zachowaj go. Body jest czystym JSON z question (pełne pytanie), draft (pełna analiza) i checks (osobny wpis dla każdego wymagania). Wpis ma requirement, status (met/failed/unknown), finding, source (bezpośredni URL) i quote (dokładny fragment widocznej treści). Przy niepotwierdzonych danych wpisz unknown i konkretną lukę. Zachowaj także search_log, candidate_log i feasibility dla poszukiwań S700. Każde wymaganie ma dotyczyć tego samego zestawu i wariantu. Nie wysyłaj prywatnych danych bez zgody.

Workflow otwiera strony, sprawdza cytaty, dzieli dane w UTF-8 i pyta Google AI. Po uwagach lub niepełnym pokryciu szuka poprawionej analizy i ponawia przegląd do trzech rund. W aktywnej turze uruchom python3 hooks/review_turn.py --wait NUMER (ścieżka względem katalogu wtyczki). Oczekuj na zakończenie procesu. Bez lokalnego wykonawcy użyj GitHub: pobieraj komentarze oraz stan przebiegu google-ai-ask.yml pod nazwą Google AI issue #NUMER. Odczekuj 30 s, limit 27 minut od zgłoszenia. Odczytaj wyłącznie Konsultant/2 od github-actions[bot] z numerem issue, SHA-256 dokładnego body i ID odpowiedniego runu. Brak komentarza w trakcie pracy oznacza oczekiwanie.

Po DO POPRAWY sprawdź uzasadnienie i nową ofertę bezpośrednio. Jeżeli automat nie zdołał pozyskać korekty, aktywny ChatGPT poprawia draft i dowody i tworzy nową recenzję [consult] z polem parent_issue i sufiksem tytułu /2 lub /3. Przydziel najwyżej trzy zgłoszenia w turze. Nie powtarzaj tego samego szkicu. Jeśli Google zatwierdziło analizę, porównaj każdy warunek z pierwotnym pytaniem, konkretną ofertą i pełnym kosztem. PASS fragmentów nie daje pozytywnego wyniku całości. Przy pozytywnym wyniku dołącz dokładny zaakceptowany szkic. W odpowiedzi podaj możliwości, przeszkody, źródła, osobny wiersz POTWIERDZONE albo NIEPOTWIERDZONE oraz link do ostatniego issue. Przy awarii podaj konkretną przyczynę i wynik dotychczasowych poszukiwań. ChatGPT może kontynuować podczas otwartej tury; sam komentarz GitHub nie uruchamia kolejnej tury.
