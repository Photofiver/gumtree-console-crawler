# Blueprint na telefonie — prywatna przeglądarka GitHub Codespaces

Ta wersja **nie używa ChatGPT Work, nie wymaga komputera ani instalacji na telefonie**. Zalogowana sesja Blueprint pozostaje wewnątrz **Twojego prywatnego Codespace**. Zastosowano Playwright Chromium, mobilny podgląd ekranu i komunikację z ChatGPT przez istniejące połączenie GitHub Issues.

## Uruchomienie (jednorazowo, telefon)

1. Otwórz **https://codespaces.new/Photofiver/gumtree-console-crawler** po zalogowaniu do swojego GitHuba.
2. Wybierz **Create codespace**. Jeśli GitHub proponuje płatne limity lub ustawienie płatności, przerwij i sprawdź dostępny darmowy limit.
3. W przeglądarce otworzy się Codespace. Pierwszy start instaluje Chromium i wymagane biblioteki. Otwórz zakładkę **PORTS** i przy porcie **8765** wybierz **Open in Browser**. Port ma pozostać **PRIVATE** — NIE zmieniaj widoczności na Public.
4. W mobilnym podglądzie kliknij przycisk logowania Blueprint i wybierz **CONTINUE WITH GITHUB**. Klikaj ekran zdalny; aby pisać w polu zaznaczonym na ekranie, używaj pola „Wpisz” i osobnego przycisku Enter. Kod weryfikacyjny lub hasło wprowadzaj tylko w tej prywatnej przeglądarce, nigdy w GitHub Issue ani czacie.
5. Gdy u góry pojawi się **Blueprint: zalogowany** oraz **GitHub: connected**, powiedz ChatGPT: „Zalogowałem się w Codespaces, zrób projekt lampki LED.”

## Jak ChatGPT zleca projekty

Po zalogowaniu ChatGPT może utworzyć Issue w repozytorium z tytułem zaczynającym się od `[blueprint-project]`, a w treści:

```json
{"prompt":"Build a basic 9V red LED lamp with a 470 ohm resistor and a push button. Include wiring diagram and parts list."}
```

Program w Codespace przegląda nowe polecenia GitHub co około 12 sekund, wykonuje tylko polecenie `prompt` autora repozytorium `Photofiver` i zamieszcza w Issue bezpieczny status (`login_required`, `prompt_submitted_unverified`, `submission_failed`).

**Status `prompt_submitted_unverified` nie gwarantuje, że Blueprint zapisał gotowy projekt.** Zweryfikuj wynik w mobilnym podglądzie. Projekt może wymagać potwierdzenia po stronie Blueprint albo dodatkowych kroków interfejsu.

## Ważne ograniczenia

- Potrzebny jest **uruchomiony Codespace**. Przy jego wyłączeniu nie można wysyłać nowych zadań; uruchom go ponownie z https://github.com/codespaces.
- GitHub Codespaces udostępnia miesięczną pulę bezpłatnego wykorzystania dla kont osobistych; poza nią mogą obowiązywać opłaty. Sprawdź komunikat GitHub przed utworzeniem.
- Sesja Blueprint zapisuje się w profilu Chromium w katalogu `~/.local/share/blueprint-bridge/chromium`, poza repozytorium, commitami i GitHub Issues. Nie eksportujemy żadnych cookies do plików publicznych.
- Projektowe polecenia w Issues są **publiczne** — nie wpisuj tam haseł ani poufnych pomysłów.
- Jeżeli GitHub zablokuje logowanie OAuth w zdalnej przeglądarce, trzeba będzie zgłosić ograniczenie. Ta konfiguracja nie omija zabezpieczeń logowania.
- Port 8765 jest domyślnie **prywatny** dzięki uwierzytelnianiu GitHub Codespaces. Jeżeli zmienisz go na publiczny, zamknij Codespace i usuń sesję.
- Autoryzacja nie jest przenoszona z Brave ani Chrome na telefonie. Trzeba zalogować się **raz w tym konkretnym oknie zdalnym**.
