# Praćenje klikova — lokalno pokretanje u WSL-u

Python se pokreće izravno u WSL-u, primjerice kroz VS Code. Docker Desktop na
Windowsu preko WSL integracije pokreće Redis i PostgreSQL. Docker Compose
pokreće ta dva servisa, a API i consumer pokreću se zasebno u WSL terminalima.

FastAPI prihvaća klikove i šalje ih u Redis Stream. `app/storage_consumer.py`
sprema događaje u PostgreSQL, a stranica prikazuje broj pohranjenih klikova.

## Struktura projekta

```text
click-monitoring/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI, validacija i statistika
│   ├── storage_consumer.py     # Redis → PostgreSQL
│   └── static/
│       └── index.html          # Stranica s gumbima
├── scripts/
│   ├── __init__.py
│   └── init_db.py              # Prvo stvaranje tablice
├── examples/
│   ├── producer.py             # Slanje događaja bez API-ja
│   ├── consumer.py             # Čitanje i ispis Redis događaja
│   └── demo.py                 # JSON i UTF-8 primjer
├── tests/
│   ├── __init__.py
│   ├── test_main.py
│   └── test_storage_consumer.py
├── compose.yaml
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── .gitignore
└── README.md
```

`app/` sadrži aplikaciju, `scripts/` pomoćne naredbe, `examples/` primjere za
učenje, a `tests/` automatizirane testove. `.env` i `.venv/` ostaju u korijenu
projekta i ignorirani su u Gitu. Python module pokrećite s `python -m ...`
iz korijena projekta kako bi se importi ispravno razriješili.

## Preduvjeti i priprema

Potrebni su Python s podrškom za `venv` i Docker Desktop s uključenom WSL
integracijom za vašu distribuciju. Sve naredbe izvršavajte iz korijena projekta.

Ako `.env` još ne postoji, napravite ga iz predloška:

```bash
cp -n .env.example .env
```

U `.env` postavite stvarne pristupne podatke. Primjer za lokalni razvoj:

```dotenv
POSTGRES_DB=click_monitoring
POSTGRES_USER=learner
POSTGRES_PASSWORD=replace_with_a_local_password
POSTGRES_PORT=5434
REDIS_URL=redis://127.0.0.1:6379/0
DATABASE_URL=postgresql://learner:replace_with_a_local_password@127.0.0.1:5434/click_monitoring
CONSUMER_NAME=worker-1
```

Zamijenite lozinku u `POSTGRES_PASSWORD` i `DATABASE_URL`. Korisnik, baza i port
u `DATABASE_URL` moraju odgovarati ostalim postavkama. Posebne znakove u lozinci
unutar URL-a kodirajte kao URL, primjerice `@` kao `%40` i `#` kao `%23`;
`POSTGRES_PASSWORD` ostaje izvorna lozinka.

`.env.example` sadrži sve navedene postavke. Primjeri koriste PostgreSQL port
`5434`, na kojem je ovaj projekt provjeren. Ako je port zauzet, promijenite
`POSTGRES_PORT` i port u `DATABASE_URL` na istu slobodnu vrijednost.

Pripremite virtualno okruženje i instalirajte ovisnosti:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

`requirements.txt` uključuje i `python-dotenv` za učitavanje postavki iz `.env`.

## Pokretanje Redisa i PostgreSQL-a

Pokrenite Docker Desktop, zatim u WSL terminalu:

```bash
docker compose config --quiet
docker compose up -d
docker compose ps
```

Prvo pokretanje preuzima slike i inicijalizira PostgreSQL bazu i korisnika.
Tablica `click_events` nastaje zasebno, naredbom `python -m scripts.init_db`.
Status pokrenutog kontejnera ne znači da je baza već spremna za veze.
Provjerite servise i njihove zapise:

```bash
docker compose exec redis redis-cli ping
docker compose exec postgres sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose logs redis postgres
```

Redis treba vratiti `PONG`, a PostgreSQL poruku `accepting connections`.
Ako PostgreSQL još nije spreman, ponovite provjeru prije inicijalizacije tablice.

## Inicijalizacija tablice u bazi

Aktivirajte virtualno okruženje i izvezite postavke iz `.env` u trenutačni
terminal. Za prikazane Bash naredbe koristite vlastiti `.env` sa zapisima
`IME=vrijednost`; vrijednosti s razmacima ili posebnim znakovima za Bash stavite
u jednostruke navodnike. `source` izvršava sadržaj datoteke kao Bash naredbe.

```bash
source .venv/bin/activate
set -a
source .env
set +a
python -m scripts.init_db
```

Očekivana poruka je `click_events table initialized.` Naredba stvara tablicu
ako ne postoji; ponovno pokretanje ne briše podatke i ne mijenja strukturu
postojeće tablice. Ne stvara novu bazu niti provodi migracije.

Ovu naredbu zadržavamo za pripremu nove baze: Docker stvara bazu i korisnika,
a skripta stvara aplikacijsku tablicu. Ako tablica već postoji, inicijalizaciju
ne treba ponavljati pri svakom pokretanju. Za buduće promjene stupaca ili
ograničenja trebale bi migracije; `CREATE TABLE IF NOT EXISTS` ih ne provodi.

## Pokretanje API-ja — terminal 1

U terminalu iz korijena projekta:

```bash
source .venv/bin/activate
set -a
source .env
set +a
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Ostavite ovaj terminal otvoren. `--reload` ponovno pokreće API pri promjenama
koda i namijenjen je lokalnom razvoju.

- Stranica s gumbima i statistikom: <http://127.0.0.1:8000/>
- Interaktivna dokumentacija API-ja: <http://127.0.0.1:8000/docs>
- Statistika u JSON formatu: <http://127.0.0.1:8000/stats/clicks>

Stranicu otvorite preko API-ja; izravno otvaranje `app/static/index.html` ne pruža API rute.
`DATABASE_URL` potreban je API-ju za statistiku. Sam `POST /events/click`
koristi Redis i ne zapisuje izravno u PostgreSQL.

## Pokretanje storage consumera — terminal 2

Otvorite drugi WSL terminal u korijenu projekta:

```bash
source .venv/bin/activate
set -a
source .env
set +a
python -m app.storage_consumer
```

Consumer čeka događaje, pa prazan terminal bez poruka ne znači da ne radi.
`CONSUMER_NAME` zadano je `worker-1`. Zadržite isto ime pri ponovnom pokretanju
kako bi consumer obradio svoje nepotvrđene događaje. Ako istodobno pokrećete
više workera, svakome dodijelite drugo ime, primjerice:

```bash
CONSUMER_NAME=worker-2 python -m app.storage_consumer
```

Za cijeli tijek redoslijed je: **Docker servisi → inicijalizacija tablice →
API i storage consumer → otvaranje stranice ili slanje događaja**.

## Provjera slanja i pohrane klikova

Kliknite gumb na <http://127.0.0.1:8000/> ili u trećem terminalu pošaljite
primjer zahtjeva:

```bash
curl -i http://127.0.0.1:8000/events/click \
  -H 'Content-Type: application/json' \
  -d '{"event_id":"c46de8cb-9280-4db2-9b7e-d00e7c79cb68","schema_version":1,"occurred_at":"2026-10-06T12:00:00+02:00","session_id":"session-1","page":"/products","element_id":"gumb-č"}'
```

API vraća HTTP **202 Accepted** i oba identifikatora. Redis generira
`stream_entry_id`, pa će se njegova vrijednost razlikovati:

```json
{"event_id":"c46de8cb-9280-4db2-9b7e-d00e7c79cb68","stream_entry_id":"1791280800000-0"}
```

Provjerite statistiku i posljednje pohranjene događaje:

```bash
curl -i http://127.0.0.1:8000/stats/clicks
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT event_id, occurred_at, element_id FROM click_events ORDER BY occurred_at DESC LIMIT 10;"'
```

Za praznu tablicu statistika je `[]`; nakon pohrane primjer je
`[{"element_id":"gumb-č","count":1}]`. Statistika obuhvaća sve pohranjene
događaje, kroz sve sesije i stranice. Consumer obrađuje događaje zasebno, pa
provjera odmah nakon POST-a može još pokazivati prethodni broj klikova.

Ponovljeni zahtjev s istim `event_id` dodaje novi zapis u Redis, ali ne povećava
broj redaka u PostgreSQL-u. Za novi događaj koristite novi UUID. Preglednik ga
sam generira pri svakom kliku.

## Skripte za učenje

`examples/consumer.py` samo čita i ispisuje događaje iz Redisa. Za spremanje u bazu
pokrenite `python -m app.storage_consumer`. Izvornog consumera možete pokrenuti u zasebnom
terminalu nakon aktivacije okruženja i učitavanja postavki:

```bash
source .venv/bin/activate
set -a
source .env
set +a
python examples/consumer.py
```

U drugom pripremljenom terminalu pošaljite jedan događaj bez API-ja:

```bash
python examples/producer.py
```

`examples/consumer.py` koristi `XREAD`, kreće od `0-0` i nakon ponovnog pokretanja opet
čita sve zadržane događaje. Ne potvrđuje događaje storage grupe i ne ometa
njihovo spremanje. Odgovori Redisa su bajtovi: čita `fields[b"payload"]`,
dekodira UTF-8 i zatim poziva `json.loads`. `block=2000` čeka do dvije sekunde;
prazan odgovor znači da petlja nastavlja čekati.

`examples/demo.py` prikazuje pretvorbe Python objekt → JSON → UTF-8 bajtovi → JSON →
Python objekt. Ne treba Redis ni PostgreSQL:

```bash
python examples/demo.py
```

## Portovi i varijable okruženja

Mapiranje porta ima oblik `host_address:host_port:container_port`.
`127.0.0.1:5434:5432` prosljeđuje lokalni port 5434 na port 5432 u PostgreSQL
kontejneru. Oba Docker servisa objavljuju portove samo na lokalnoj adresi.

| Servis | Adresa iz WSL-a | Port | Postavke |
| --- | --- | --- | --- |
| Redis | `127.0.0.1` | `6379` | Baza `0`; `redis://127.0.0.1:6379/0` |
| PostgreSQL | `127.0.0.1` | Vrijednost `POSTGRES_PORT`, u primjeru `5434` | Baza, korisnik i lozinka iz `.env` |
| API | `127.0.0.1` | `8000` | Pokreće se Uvicornom u WSL-u |

Nazivi `redis` i `postgres` razrješavaju se između kontejnera na zadanoj
Compose mreži. Python u WSL-u koristi objavljene lokalne portove.
Ako je PostgreSQL port zauzet, promijenite `POSTGRES_PORT` i `DATABASE_URL`;
unutar kontejnera port ostaje 5432. Za promjenu Redis porta uredite mapiranje
u `compose.yaml` i uskladite `REDIS_URL`. Za API promijenite Uvicornov `--port`
i adresu koju otvarate u pregledniku.

Compose čita `.env` i koristi ove varijable:

- `POSTGRES_DB`: baza koja se stvara pri prvoj inicijalizaciji.
- `POSTGRES_USER`: početni PostgreSQL korisnik s ovlastima superkorisnika.
- `POSTGRES_PASSWORD`: njegova početna lozinka.
- `POSTGRES_PORT`: objavljeni port na računalu.

Varijable već izvezene u terminalu imaju prednost pred vrijednostima u `.env`.
Compose konfiguracija zahtijeva nepraznu bazu, korisnika i lozinku; postavite
i port prije pokretanja. Promjena inicijalizacijskih podataka u `.env` ne
mijenja bazu, korisnika ili lozinku u već inicijaliziranom podatkovnom volumenu.
Te promjene napravite kroz PostgreSQL.

Python procesi koriste:

- `REDIS_URL`: zadano `redis://localhost:6379/0`.
- `DATABASE_URL`: obvezan za inicijalizaciju, storage consumer i API statistiku.
- `CONSUMER_NAME`: zadano `worker-1`, koristi ga storage consumer.

Compose ne izvozi `.env` u Python procese u WSL-u. `app/main.py` izričito učitava
`.env` iz korijena projekta uz pomoć `python-dotenv`, a `app/storage_consumer.py` to čini posredno jer
uvozi `ClickEvent` iz `app.main`. Postojeće varijable okruženja imaju prednost.
`scripts/init_db.py`, `examples/producer.py` i `examples/consumer.py` sami ne učitavaju `.env`. Zato
prikazane naredbe eksplicitno izvoze postavke u svakom terminalu.

`.env`, `.venv/`, `.vscode/` i Python predmemorija ignorirani su u Gitu. `.env.example`
služi kao predložak bez stvarnih pristupnih podataka.

## Testovi

U aktiviranom virtualnom okruženju instalirajte razvojne ovisnosti i pokrenite
oba skupa testova (razvojne ovisnosti uključuju HTTP klijente za TestClient):

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Testovi koriste zamjenske Redis i PostgreSQL objekte, pa ne trebaju pokrenute
servise. Provjeravaju validaciju, UTF-8 podatke, HTTP odgovore, konfiguraciju,
životni ciklus veza, SQL parametre, redoslijed commit/ack, duplikate i oporavak
nepotvrđenih događaja. To nije provjera stvarne veze s Docker servisima;
za nju koristite gore navedene naredbe slanja i provjere pohrane.

## Zaustavljanje i trajnost podataka

API i consumer zaustavite s `Ctrl+C` u njihovim terminalima. Za zaustavljanje
i uklanjanje Docker kontejnera uz zadržavanje podataka:

```bash
docker compose down
```

Ponovni `docker compose up -d` koristi iste podatke. Za pregled zapisa ili
ponovno pokretanje servisa:

```bash
docker compose logs --tail=100 redis postgres
docker compose restart redis postgres
```

Podaci se čuvaju u imenovanim volumenima koje upravlja Docker Desktop:

- `redis_data` montiran je na `/data` i sadrži Redis datoteke trajne pohrane.
- `postgres_data` montiran je na `/var/lib/postgresql/data` i sadrži bazu,
  uključujući dnevnik transakcija za oporavak nakon pada.

Compose obično dodaje naziv projekta, primjerice
`click-monitoring_redis_data`. Koristite isti naziv projekta za iste volumene.
Redis koristi AOF i `appendfsync everysec`: zapisuje operacije i reproducira ih
pri ponovnom pokretanju, a pad može izgubiti približno posljednju sekundu
upisa. PostgreSQL čuva potvrđene transakcije u podatkovnom direktoriju.
Volumeni preživljavaju ponovno stvaranje kontejnera, ali nisu sigurnosne kopije.

Opcija `docker compose down --volumes` (`-v`) briše oba volumena i njihove
podatke; obični `docker compose down` ih zadržava.

## Česti problemi

- **`ModuleNotFoundError`**: aktivirajte `.venv`, instalirajte ovisnosti iz
  `requirements.txt` i pokrećite naredbe iz korijena projekta.
- **Nedostaje `DATABASE_URL`**: učitajte i izvezite `.env` u terminalu u kojem
  pokrećete `scripts/init_db.py`; API i consumer također trebaju tu postavku za bazu.
- **Port nije dostupan**: promijenite `POSTGRES_PORT` i port u `DATABASE_URL`,
  pa ponovno pokrenite `docker compose up -d`.
- **Veza s bazom odbijena**: provjerite `docker compose ps`, `pg_isready`,
  objavljeni port i pristupne podatke. Promjena `.env` ne mijenja postojeću
  lozinku u volumenu.
- **HTTP 503 pri slanju klika**: provjerite Redis i `REDIS_URL`.
- **HTTP 503 za statistiku**: provjerite `DATABASE_URL`, PostgreSQL i je li
  tablica inicijalizirana naredbom `python -m scripts.init_db`.
- **Klik je prihvaćen, ali broj ne raste**: pokrenite `python -m app.storage_consumer` i
  provjerite njegov terminal. `examples/consumer.py` samo ispisuje događaje.

## Kako rade API i validacija

`ClickEvent` je Pydantic model sa šest obveznih polja. Dodatna polja odbija.
`event_id` pretvara u Python `UUID` i prihvaća bilo koju UUID verziju.
`schema_version` mora biti cijeli broj `1`; odbija druge brojeve, booleane i
tekst. `occurred_at` koristi `AwareDatetime`, pa mora sadržavati vremensku zonu,
primjerice `Z` ili `+02:00`.

Tekstualnim poljima uklanja okolne bjeline i odbija prazne vrijednosti.
`session_id` i `element_id` dopuštaju 1–128 znakova, a `page` 1–2.048 znakova.
To su ograničenja broja znakova, a ne UTF-8 bajtova. `session_id` je tekst,
ne mora biti UUID.

`event.model_dump_json()` pretvara UUID i datum u JSON tekst.
Obični `json.dumps(event.model_dump())` ne bi znao kodirati Python UUID i datum
bez dodatnog kodera. `.encode("utf-8")` proizvodi bajtove, uz očuvanje znakova
poput `č`. Redis prima jedno polje `payload` u streamu `events:clicks:v1`.
Detalji su u [Pydantic dokumentaciji](https://docs.pydantic.dev/latest/api/standard_library_types/).

`lifespan(app)` stvara jedan redis-py klijent i skup veza po procesu, sprema ga
u `app.state.redis` i zatvara pri gašenju. Veze se otvaraju tek pri korištenju,
pa nedostupan Redis ne sprječava pokretanje API-ja. Životnim ciklusom upravlja
asinkroni kontekst, ali Redis klijent je sinkron.
Pogledajte [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/).

`post_click(event, request)` je sinkrona `def` funkcija koju FastAPI izvršava
u radnoj dretvi. Nakon validacije serijalizira događaj, poziva `XADD`, dekodira
Redis identifikator i vraća oba identifikatora.

- **202 Accepted**: Redis je potvrdio `XADD`; događaj je u redu za obradu.
- **422**: zahtjev nije valjan i događaj nije poslan u Redis.
- **503**: veza s Redisom nije uspjela ili je isteklo vrijeme čekanja.

Istek vremena može nastupiti nakon što je Redis primio zapis, pa 503 ne
jamči da događaj ne postoji. API sam ne uklanja duplikate `event_id`.

Redis klijent postavlja `socket_connect_timeout` i `socket_timeout` na dvije
sekunde i isključuje automatske pokušaje s `Retry(NoBackoff(), 0)` kako ne bi
ponovio nejasno potvrđen `XADD`. To su ograničenja pojedinih operacija,
ne ukupnog trajanja HTTP zahtjeva. Ne dodajte timeout opcije u `REDIS_URL`,
jer URL opcije imaju prednost pred argumentima klijenta.
Pogledajte [redis-py postavke veza](https://redis.readthedocs.io/en/stable/connections.html).

## Kako radi pohrana u PostgreSQL

`scripts.init_db.main()` stvara tablicu `click_events` ako ne postoji. Tablica ima
UUID primarni ključ, verziju sheme ograničenu na 1, `TIMESTAMPTZ` i neprazne
tekstualne stupce ograničene duljine. Kontekst Psycopg veze potvrđuje stvaranje
tablice na uspješnom izlasku, zatvara vezu i zatim se ispisuje poruka uspjeha.

`app/storage_consumer.py` koristi Psycopg 3 i isti `ClickEvent` model kao API:

- `create_group(client)` stvara grupu `click-storage` od ID-a `0` s `MKSTREAM`.
  Zato su svi zadržani događaji dostupni za obradu, a odsutan stream se stvara.
  Samo greška s točnim kodom `BUSYGROUP` znači da grupa već postoji; ostale
  greške prekidaju rad. Pozicija postojeće grupe ostaje sačuvana.
- `store_entry(...)` dekodira i validira `payload`, zapisuje ga u transakciji
  i potvrđuje Redis zapis tek nakon commita. SQL koristi šest `%s` mjesta i
  zasebne parametre; Psycopg prilagođava UUID i datum s vremenskom zonom.
  Podaci događaja ne umeću se izravno u SQL tekst.
- `consume(...)` prvo obrađuje nepotvrđene događaje tog consumera, zatim čita
  nove pojedinačno. Ako obrada ne uspije, zapisuje ID i grešku te prekida rad.
- `main()` otvara zajedničke sinkrone Redis i PostgreSQL veze. Pri grešci
  zapisuje detalje i završava statusom 1; `Ctrl+C` završava normalno. Konteksti
  zatvaraju obje veze. Redis nema automatske ponovne pokušaje, a socket timeout
  od pet sekundi veći je od blokirajućeg čitanja od dvije sekunde.

Pogledajte [Psycopg SQL parametre](https://www.psycopg.org/psycopg3/docs/basic/params.html).

### Transakcije i duplikati

Svaki valjani događaj prolazi slijed:

```text
validacija → BEGIN → INSERT ... ON CONFLICT DO NOTHING → COMMIT → XACK
```

Veza ima `autocommit=True` kako ne bi ostala otvorena implicitna transakcija
tijekom čekanja na Redis. `with connection.transaction():` ipak pokreće pravu
transakciju. **COMMIT se događa pri uspješnom izlasku iz tog bloka, prije
`client.xack(...)`; ne čeka gašenje consumera.**
Pogledajte [Psycopg transakcije](https://www.psycopg.org/psycopg3/docs/basic/transactions.html).

`event_id` je primarni ključ. `ON CONFLICT (event_id) DO NOTHING` zadržava prvi
redak nepromijenjen kada ponovno stigne isti ID. Duplikat je uspješna SQL
operacija, pa se Redis zapis potvrđuje iako novi redak nije dodan.

Greške validacije događaju se prije BEGIN-a i zapis se ne potvrđuje. Neuspješan
INSERT poništava transakciju, a neuspješan commit također sprječava XACK.
Ako commit uspije, ali XACK ne uspije ili proces padne, zapis ostaje nepotvrđen
i može ponovno stići. Ponovni INSERT istog događaja ne stvara duplikat.
Redis i PostgreSQL nemaju jednu zajedničku atomsku transakciju.

### Oporavak nepotvrđenih događaja

Pri svakom pokretanju `XREADGROUP` počinje s `{events:clicks:v1: "0"}`, bez
blokiranja. Time čita događaje već dostavljene **tom imenu consumera**, koji
još nisu potvrđeni. Nakon uspješne obrade pomiče kursor na ID zapisa.
Kad nepotvrđenih zapisa više nema, prelazi na `>` i čeka događaje još
nedostavljene grupi. Prazni odgovori nakon dvije sekunde nastavljaju petlju;
greške prekidaju proces.
Pogledajte [Redis XREADGROUP](https://redis.io/docs/latest/commands/xreadgroup/).

Nepotvrđeni zapisi drugih consumera ostaju njihovi. Nema `XAUTOCLAIM`, petlje
ponovnih pokušaja ili posebnog reda za neuspjele događaje. Nevaljani događaj
ponovno zaustavlja isti consumer pri pokretanju dok se ručno ne riješi.

## Kako rade preglednička stranica i statistika

`index()` poslužuje `app/static/index.html` kroz `FileResponse`. Stranica ima tri gumba
sa stalnim ID-jevima: `signup-button`, `products-button` i `contact-button`.
CSS i obični JavaScript nalaze se u HTML datoteci; nije potrebna zasebna
izgradnja frontenda ili dodatni framework.
Pogledajte [FastAPI datotečne odgovore](https://fastapi.tiangolo.com/advanced/custom-response/#fileresponse).

`initializeClicks()` čita `click-monitoring:session_id` iz `sessionStorage`
ili stvara i sprema UUID. Osvježavanje zadržava sesiju kartice. Pohrana je
vezana uz origin i karticu; dupliciranje kartice može početno kopirati pohranu.
Ako inicijalizacija ne uspije, gumbi se onemogućuju i prikazuje se greška.
Pogledajte [sessionStorage](https://developer.mozilla.org/en-US/docs/Web/API/Window/sessionStorage).

`sendClick(...)` pri svakom kliku generira novi `event_id` pomoću
`crypto.randomUUID()`. `new Date().toISOString()` daje UTC datum sa završnim
`Z`. Šalje i verziju 1, spremljeni ID sesije, `window.location.pathname` i ID
gumba na relativnu adresu `/events/click`. UUID generiranje zahtijeva siguran
kontekst; lokalne razvojne adrese `localhost` i loopback to podržavaju.
Pogledajte [randomUUID](https://developer.mozilla.org/en-US/docs/Web/API/Crypto/randomUUID).

`click_stats()` je sinkrona ruta `GET /stats/clicks`. Za svaki zahtjev otvara
Psycopg vezu s `DATABASE_URL`, `autocommit=True` i izvršava:

```sql
SELECT element_id, COUNT(*) FROM click_events
GROUP BY element_id ORDER BY element_id
```

Vraća HTTP 200 s popisom broja klikova po elementu. Veza se zatvara nakon
zahtjeva; istodobni zahtjevi ne dijele jednu Psycopg vezu. Nedostajuće postavke
ili greške baze vraćaju HTTP 503.

`refreshStats()` dohvaća statistiku odmah, a sljedeće osvježavanje zakazuje
dvije sekunde nakon dovršetka zahtjeva. Zaobilazi predmemoriju preglednika i
ispisuje tablicu pomoću `textContent`. Slanje klika i čitanje statistike imaju
ograničenje čekanja od pet sekundi. Pri grešci statistike ostaju vidljivi
posljednji brojevi s porukom da su zastarjeli; osvježavanje se nastavlja.
POST zahtjevi za klikove ne ponavljaju se automatski.

```text
gumb → JSON iz preglednika → POST /events/click → Redis Stream → HTTP 202
                                                    ↓
                                         consumer → PostgreSQL COMMIT
                                                    ↓
tablica u pregledniku ← GET /stats/clicks ← broj klikova iz PostgreSQL-a
```

Uspješan POST potvrđuje prihvat u Redis, a sljedeće osvježavanje nakon commita
prikazuje novi broj. Ako je storage consumer zaustavljen, POST zahtjevi mogu
uspijevati dok broj klikova ostaje nepromijenjen.

## Dodatna dokumentacija

- [Verzije službene Redis slike](https://github.com/docker-library/official-images/blob/master/library/redis)
- [Verzije službene PostgreSQL slike](https://github.com/docker-library/official-images/blob/master/library/postgres)
- [Inicijalizacija i pohrana PostgreSQL slike](https://hub.docker.com/_/postgres)
- [Compose interpolacija varijabli](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)
- [Compose servisi i portovi](https://docs.docker.com/reference/compose-file/services/)
- [Redis trajna pohrana](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)
