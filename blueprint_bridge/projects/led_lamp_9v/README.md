# Lampka LED 9 V — projekt elektryczny

Status: **gotowy schemat i lista elementów w GitHub; projekt NIE jest jeszcze zapisany na blueprint.io**.

## Obwód

```
BAT1 +9 V ── S1 (NO) ── R1 470 Ω / 0,25 W ── D1 LED czerwona (anoda) ▶| (katoda) ── BAT1 −
```

Włącznik przyciskowy S1 jest chwilowy, **normalnie otwarty (NO)**; LED świeci tylko w chwili przytrzymania przycisku.

Zobacz [schemat połączeń](./schematic.svg) i [listę elementów CSV](./bom.csv).

## Lista elementów

| Oznaczenie | Element | Liczba |
|---|---|---:|
| BAT1 | Bateria 9 V 6F22/6LR61 + klips | 1 |
| S1 | Przycisk monostabilny NO | 1 |
| R1 | Rezystor 470 Ω, 0,25 W lub więcej | 1 |
| D1 | LED czerwona 5 mm (typowe Vf ≈ 2 V) | 1 |
| — | Przewody połączeniowe | wg potrzeby |

## Obliczenia i kontrola

Przy napięciu baterii 9 V i spadku na czerwonej LED 2 V:

- Prąd LED: (9 − 2) / 470 ≈ **14,9 mA**.
- Moc rezystora: (9 − 2)² / 470 ≈ **0,104 W**, więc rezystor 0,25 W jest odpowiedni.
- **Zachowaj polaryzację LED**: anoda (zwykle dłuższa nóżka) do R1, katoda (zwykle krótsza, przy spłaszczeniu obudowy) do minusa baterii. Zweryfikuj oznaczenia dla użytej diody.

## Montaż

1. Podłącz czerwony przewód klipsa baterii do jednej końcówki S1.
2. Drugą końcówkę S1 połącz z R1.
3. R1 połącz z anodą D1.
4. Katodę D1 podłącz do czarnego przewodu klipsa baterii.
5. Sprawdź połączenia i dopiero wtedy podepnij baterię. Przy naciśniętym S1 dioda powinna świecić.

## Blueprint

Gotowe zlecenie wysłania opisu do Blueprint: [GitHub Issue #80](https://github.com/Photofiver/gumtree-console-crawler/issues/80). Aby utworzyć projekt **w koncie Blueprint**, trzeba zalogować się w prywatnej przeglądarce Codespace (port 8765), a następnie poczekać na wynik zlecenia. Samo istnienie tego folderu nie oznacza utworzenia projektu na stronie.
