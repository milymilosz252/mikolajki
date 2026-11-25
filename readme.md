# Mikołajki 🎁

Prosta aplikacja webowa do losowania osób na Mikołajki. Każdy uczestnik loguje się swoim imieniem i hasłem, klika „Losuj" i widzi, komu kupuje prezent. Wynik jest widoczny tylko dla niego.

Backend napisany jest w Pythonie (Flask + SQLite), całość uruchamia się jedną komendą w Dockerze.

## Funkcje

- Logowanie imieniem i hasłem
- Hasła generowane automatycznie i wypisywane w konsoli przy starcie, więc można je od razu rozesłać uczestnikom
- Losowanie w jeden duży cykl: nikt nie wylosuje siebie, a każdy jest wylosowany dokładnie raz
- Wynik zapisany w bazie, więc po ponownym zalogowaniu uczestnik widzi to samo
- Jedno losowanie dla wszystkich, wykonywane przy pierwszym kliknięciu „Losuj" przez kogokolwiek
- Dane trzymane poza obrazem Dockera, więc przeżywają restart i przebudowę kontenera

## Jak to działa

Przy pierwszym kliknięciu „Losuj" backend miesza listę uczestników i ustawia ich w cykl. Każda osoba kupuje prezent następnej na liście, a ostatnia pierwszej:

```
Darek → Ania → Celina → Bartek → Darek
```

Przypisanie jest zapisywane w bazie `mikolajki.db`. Kolejne kliknięcia i logowania zawsze pokazują ten sam wynik.

## Struktura projektu

```
mikolajki/
├── app.py                 # backend (Flask)
├── Dockerfile
├── docker-compose.yml
├── static/
│   └── index.html         # frontend
└── data/                  # dane (poza gitem)
    ├── uczestnicy.txt     # lista imion, tworzysz ręcznie
    ├── hasla.txt          # generowane automatycznie
    ├── mikolajki.db       # baza z wynikami
    └── .secret_key        # klucz sesji
```

## Szybki start (Docker)

Wymagania: Docker z Docker Compose.

```bash
git clone https://github.com/TWOJ_LOGIN/mikolajki.git
cd mikolajki
mkdir -p data
nano data/uczestnicy.txt        # same imiona, jedno na linię
docker compose up -d --build
docker compose logs mikolajki   # hasła uczestników
```

Strona działa pod `http://localhost` (na serwerze: `http://IP_SERWERA`).

### Format `uczestnicy.txt`

Jedno imię w każdej linii. Puste linie i linie zaczynające się od `#` są pomijane:

```
Ania
Bartek
Celina
Darek
```

### Hasła

Przy każdym starcie kontenera hasła wypisują się w logach:

```
========================================
HASŁA UCZESTNIKÓW
========================================
Ania     k7m2xq9p
Bartek   r4tn8wc3
Celina   x9d2hf6e
========================================
```

Hasła są też zapisane w `data/hasla.txt` w formacie `Imię:hasło`. Każdemu uczestnikowi wyślij tylko jego własne hasło.

- **Własne hasło:** edytuj `data/hasla.txt` i zrób `docker compose restart`.
- **Nowe hasło dla jednej osoby:** usuń jej linijkę z `data/hasla.txt` i zrób `docker compose restart`.
- **Nowa osoba:** dopisz imię do `uczestnicy.txt` i zrób `docker compose restart`. Dostanie nowe hasło, reszta zachowa swoje.

## Przydatne komendy

```bash
docker compose logs -f mikolajki                           # logi na żywo
docker compose restart                                     # po zmianie uczestników lub haseł
docker compose run --rm mikolajki python app.py --reset    # reset wyników losowania
docker compose down                                        # zatrzymanie
```

Po `--reset` uruchom aplikację ponownie: `docker compose up -d`.

## Uruchomienie bez Dockera

```bash
pip install flask
mkdir -p data
echo -e "Ania\nBartek\nCelina" > data/uczestnicy.txt
DATA_DIR=./data python app.py
```

Aplikacja startuje na porcie 5000: `http://localhost:5000`. Bez ustawionego `DATA_DIR` pliki z danymi są szukane obok `app.py`.

## Zmiana listy uczestników po losowaniu

Jeśli lista w `uczestnicy.txt` zmieni się po przeprowadzeniu losowania, aplikacja nie wystartuje i wypisze komunikat w logach. Dzieje się tak, żeby nikt nie został bez pary. Wykonaj reset losowania (komenda wyżej), a potem uruchom aplikację ponownie.

## Aktualizacja

```bash
git pull && docker compose up -d --build
```

Folder `data/` jest poza gitem, więc aktualizacja nie rusza haseł, bazy ani wyników losowania.

## Bezpieczeństwo

- `data/hasla.txt` zawiera hasła jawnym tekstem. Folder `data/` jest w `.gitignore`, nie dodawaj go do repozytorium.
- Wyniki losowania leżą w `mikolajki.db` w jawnej postaci. Jeśli sam bierzesz udział w losowaniu, nie zaglądaj do bazy.
- Hasła trafiają do logów Dockera, więc ogranicz dostęp do serwera.
- Na publicznym serwerze postaw przed kontenerem reverse proxy z HTTPS (np. Caddy lub nginx) i odkomentuj `SESSION_COOKIE_SECURE=True` w `app.py`. W takiej konfiguracji w `docker-compose.yml` użyj `"127.0.0.1:5000:5000"`, żeby aplikacja nie była dostępna z zewnątrz bez proxy.
- Warto dodać limit prób logowania, np. przez Flask-Limiter.

## Zmiana portu

Domyślnie aplikacja jest wystawiona na porcie 80. Żeby to zmienić, edytuj `docker-compose.yml`:

```yaml
ports:
  - "8080:5000"
```

## Technologie

- Python 3.12, Flask, Gunicorn
- SQLite
- Czysty HTML, CSS i JavaScript (bez frameworków)
- Docker, Docker Compose

## Licencja

Dowolna, zależnie od Twoich potrzeb. Jeśli chcesz udostępnić projekt publicznie, dodaj plik `LICENSE` (np. MIT).
