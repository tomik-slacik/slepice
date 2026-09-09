# Mazlík API — technický základ pro reálný provoz

Backend appky Mazlík: přihlašování, adopce slepičky/kozy/ovce/krávy, denní
krmení, sdílené chovy na maso, peněženka a páteční svoz. Vedle
`frontend/index.html` (offline demo, `localStorage`,
umí fungovat bez backendu) teď existuje i **[`app/webapp/`](app/webapp/)**
— stejná appka, ale skutečně napojená na tohle API (přihlášení, reálná
data, reálné platby). Otevři `http://127.0.0.1:8000/app/` po spuštění
backendu níž.

**Bylo to opravdu spuštěné a otestované**, ne jen napsané — 105 testů
(`pytest`) a k tomu appka `app/webapp/` doopravdy proklikaná v prohlížeči
(registrace, adopce, všechny záložky, pauza, mock platba, posun dne).
Obojí odhalilo reálné chyby, které by psaní naslepo nechytilo:

- **Páteční součet** nezapočítával svůj vlastní den (chybějící flush
  databázové session před dotazem ve stejné transakci).
- **`/wallet` endpoint** počítal zůstatek a sérii vždy z reálného dnešního
  data, ne z data posunutého přes `/admin/run-tick` — takže po kliknutí
  na "Posunout o den" v appce zůstatek zůstal viditelně zaseklý, i když
  `/feed-log` už nový den měl. Objevilo se to teprve při klikání appkou,
  ne v testech — `effective_today_for_hen()` v `app/tick.py` to opravuje
  a `test_wallet_reflects_demo_advanced_days_not_just_real_today` to teď
  hlídá.

## Co v tom je

- **FastAPI** server s automatickou dokumentací (`/docs`)
- **SQLite** databáze (žádný samostatný databázový server není potřeba)
- **Přihlašování** — registrace, login, JWT tokeny, hesla přes bcrypt.
  Appka (`Hen`) patří vždy konkrétnímu uživateli; jeden uživatel nevidí
  ani neupraví appku druhého (ověřeno testem).
- **Skutečná platební integrace pro Stripe** (`app/integrations/payments.py`)
  — uložení karty (Setup Intent) a pozdější strhnutí bez přítomnosti
  zákazníka (off-session Payment Intent), ověřeno proti Stripe dokumentaci
  a otestováno. Nikdy neběžela proti skutečnému účtu — ten je na tobě, viz
  [`docs/PAYMENT_INTEGRATION.md`](docs/PAYMENT_INTEGRATION.md). Výchozí
  a bezpečný poskytovatel zůstává mock (appka jede i bez platebního účtu).
- **Skutečný denní úkol** (APScheduler), který každé ráno spustí krmení
  a v pátek spočítá vejce — obdoba tlačítka "Posunout o den" z frontendového
  dema, ale doopravdy podle hodin, ne na kliknutí
- **Rozjetý Android build** appky — viz [`../mobile-app/`](../mobile-app/)
- **Jasně oddělené místo** pro push notifikace (`app/integrations/notifications.py`)
  — teď jen mockované (loguje do konzole)
- **Ostatní hospodářská zvířata** (koza, ovce, kráva) — průběžné mléko
  stejným vzorem jako slepička, plus sdílené chovy na maso (`MeatShare`) s
  poměrným rozpočítáním výtěžku. Viz [`docs/LIVESTOCK.md`](docs/LIVESTOCK.md).
- **Skutečné DB migrace** (Alembic, `migrations/`) — ne jen
  `create_all()`. Nová verze appky s novým sloupcem v modelu se na
  existující databázi (i s reálnými daty) aplikuje bezpečně, ne
  "doufejme že to nikomu nerozbije produkci".
- **Request-id logování** — každý request dostane id (viz
  `app/middleware.py`), který jde dohledat napříč logem; obecný rate
  limit (vypnutý ve výchozím stavu, `KVOC_RATE_LIMIT_PER_MINUTE`).
- **Skutečná validace e-mailu** při registraci (`pydantic[email]`) —
  dřív appka klidně založila účet na "asdf".
- **Testy**, které se dají spustit, ne jen přečíst (105 testů: API, auth,
  platby, livestock)
- **`app/webapp/`** — appka opravdu napojená na tohle API (viz výš)

## Co v tom NENÍ (záměrně)

- **Skutečné peníze.** Platební kód je hotový a otestovaný proti mocku,
  ale bez tvého vlastního Stripe účtu (a bez skutečné firmy/živnosti pro
  ostrý provoz) nikam doopravdy neteče. Viz `PAYMENT_INTEGRATION.md`.
- **Skutečné push notifikace.** Zatím se jen vypisují do konzole —
  napojení Firebase/APNs je popsané v `app/integrations/notifications.py`.
- **Appka doopravdy v App Store / Google Play.** Android build (`.apk`/
  `.aab`) je technicky hotový a odzkoušený (`mobile-app/README.md`);
  iOS potřebuje Mac (nebo cloudové CI, `codemagic.yaml` je připravený).
  Chybí jen účty a store listing (App Store Connect/Play Console review)
  — návod v [`docs/APP_STORE_GUIDE.md`](docs/APP_STORE_GUIDE.md).
- **Appka běžící někde jinde než na tomhle počítači.** `127.0.0.1` vidí
  jen tenhle stroj — pro sdílení s kýmkoliv jiným je potřeba skutečné
  nasazení. `Dockerfile` a `render.yaml` na to jsou připravené a
  ověřené proti aktuální dokumentaci, ale založení účtu u poskytovatele
  je na tobě — viz [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).
- **Skutečné farmy ani rozvoz.** To je byznys/logistická stránka věci —
  checklist je v [`docs/BUSINESS_CHECKLIST.md`](docs/BUSINESS_CHECKLIST.md).

## Jak to spustit

Potřebuješ Python 3.11+ ([python.org](https://www.python.org/downloads/)
nebo `winget install Python.Python.3.12`).

```bash
cd kvoc-backend
python -m venv .venv
.venv\Scripts\activate          # na macOS/Linuxu: source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Appka poběží na `http://127.0.0.1:8000`.

- **`/app/`** — appka napojená na tohle API. Zaregistruj se, adoptuj
  slepičku, klikej.
- **`/docs`** — interaktivní dokumentace API (tlačítko **Authorize**
  přijme email/heslo přímo tam).

### Vyzkoušet bez čekání na skutečný pátek

Nejdřív účet a adopce (appka teď vyžaduje přihlášení):

```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"ja@example.com","password":"nejake silne heslo"}'
# -> zkopíruj access_token z odpovědi

curl -X POST http://127.0.0.1:8000/hens \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"hen_name":"Nuška","farm_key":"lipa","daily_amount":20}'
```

Pak posouvej dny:

```bash
curl -X POST http://127.0.0.1:8000/admin/run-tick?days_offset=1
```

Zavolej to postupně s `days_offset=1,2,3...` a sleduj, jak přibývají
záznamy v `/hens/{id}/feed-log` (s `Authorization` hlavičkou) a jak se
v pátek objeví položka v `/hens/{id}/deliveries`. Přesně totéž dělá
tlačítko "Posunout o den" ve frontendovém demu.

Nejpohodlnější je to celé proklikat na `/docs` — tlačítko **Authorize**
nahoře přijme email/heslo přímo tam.

### Spustit testy

```bash
pytest -v
```

S přehledem pokrytí (`pytest-cov`, viz `requirements.txt`) - kde přesně
ještě chybí test na reálnou větev kódu, ne jen "kolik testů prošlo":

```bash
pytest --cov=app --cov-report=term-missing
```

## Struktura projektu

```
app/
  main.py              — FastAPI aplikace, startup/shutdown, middleware, mount /static
  middleware.py         — request-id logování + obecný rate limit (viz config.py)
  auth.py                — hashování hesel (bcrypt), JWT tokeny, get_current_user
  models.py                — databázové tabulky (User, Farm, Hen, FeedLogEntry, Delivery, PausedDay, WalletTopUp, ...)
  database.py                — DB engine + init_db() (pouští migrace přes Alembic, viz níž)
  schemas.py                   — validace vstupů/výstupů API
  tick.py                        — denní byznys logika (krmení, bonus, páteční svoz, série)
  scheduler.py                    — napojení tick.py na skutečný denní cron
  config.py                         — ceny, časy, limity, JWT a platební nastavení na jednom místě
  geo.py                              — jediný vzorec (haversine_km) pro vzdálenost dvou bodů, sdílený mezi GET /farms a GET /admin/farms/{key}/delivery-route
  integrations/
    payments.py                        — MockPaymentProvider + funkční StripePaymentProvider
    notifications.py                    — ConsoleNotificationProvider + kam zapojit FCM/APNs
  routers/
    auth.py, farms.py, hens.py, wallet.py, animals.py, animal_wallet.py,
    meat_shares.py, admin.py                                             — HTTP endpointy
  static/
    card-setup.html                                        — holá testovací stránka pro uložení karty (Stripe.js)
    admin.html                                               — jednoduchý admin přehled (X-Admin-Token)
  webapp/
    index.html                                                — appka opravdu napojená na tohle API (viz "Jak to spustit")
migrations/            — Alembic - skutečné, verzované DB migrace (ne jen create_all()).
  versions/               Nová migrace po změně modelu: `alembic revision --autogenerate -m "popis"`,
                           zkontrolovat vygenerovaný soubor, `alembic upgrade head`. Boot appky (init_db())
                           tohle samo spustí, takže `python run.py` funguje bez ručního kroku i tak.
docs/
  PAYMENT_INTEGRATION.md   — jak Stripe integraci vyzkoušet, proč peněženka místo denní karty
  APP_STORE_GUIDE.md        — stav Android/iOS cesty, co zbývá
  BUSINESS_CHECKLIST.md     — co je potřeba zařídit mimo kód (firma, farmáři, regulace)
  LIVESTOCK.md               — koza/ovce/kráva a sdílené chovy na maso
tests/
  test_api.py                — API, auth, vlastnictví dat mezi uživateli
  test_livestock.py           — ostatní zvířata a sdílené chovy na maso
  test_payments.py             — že Stripe kód volá SDK správně (bez potřeby účtu)
  test_notifications.py         — výběr/chování notification provideru
```

Viz i [`../mobile-app/`](../mobile-app/) — Capacitor/Android obal appky.

## Další krok

Než se tohle přiblíží k reálnému provozu, přečti si
[`docs/BUSINESS_CHECKLIST.md`](docs/BUSINESS_CHECKLIST.md) — technická
kostra je hotová dřív, než byznys/právní stránka věci, a je lepší to vědět
teď než po měsíci vývoje.
