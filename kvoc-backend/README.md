# Kvoč API — technický základ pro reálný provoz

Tohle je backend kostra appky Kvoč: adopce slepičky, denní krmení, peněženka
a páteční svoz. Navazuje na [frontendové demo](../) (appka v prohlížeči se
stavem v `localStorage`) — stejná byznys logika, stejná pravidla, ale teď
běží na skutečném serveru s databází, aby na ni šlo v budoucnu napojit
skutečné platby, push notifikace a víc zákazníků najednou.

**Bylo to opravdu spuštěné a otestované** na tomhle stroji (Python 3.12,
Windows), ne jen napsané — `pytest` prošel 7/7 a API bylo ručně ověřené
přes skutečné HTTP požadavky. Cestou se tak našla a opravila reálná chyba
(páteční součet nezapočítával svůj vlastní den kvůli chybějícímu flush
databázové session) — přesně to, co testování naslepo bez spuštění
neodhalí.

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
- **Testy**, které se dají spustit, ne jen přečíst (21 testů: API, auth,
  platby)

## Co v tom NENÍ (záměrně)

- **Skutečné peníze.** Platební kód je hotový a otestovaný proti mocku,
  ale bez tvého vlastního Stripe účtu (a bez skutečné firmy/živnosti pro
  ostrý provoz) nikam doopravdy neteče. Viz `PAYMENT_INTEGRATION.md`.
- **Skutečné push notifikace.** Zatím se jen vypisují do konzole —
  napojení Firebase/APNs je popsané v `app/integrations/notifications.py`.
- **Appka doopravdy v App Store / Google Play.** `mobile-app/` sestaví
  Android projekt až na jeden krok (Android SDK, viz jeho README); iOS
  potřebuje Mac. Návod na zbytek cesty (účty, review) je v
  [`docs/APP_STORE_GUIDE.md`](docs/APP_STORE_GUIDE.md).
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

Appka poběží na `http://127.0.0.1:8000`. Interaktivní dokumentace (a rovnou
místo, kde si to proklikat bez psaní kódu) je na
`http://127.0.0.1:8000/docs`.

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

## Struktura projektu

```
app/
  main.py              — FastAPI aplikace, startup/shutdown, mount /static
  auth.py               — hashování hesel (bcrypt), JWT tokeny, get_current_user
  models.py              — databázové tabulky (User, Farm, Hen, FeedLogEntry, Delivery, PausedDay, WalletTopUp)
  schemas.py               — validace vstupů/výstupů API
  tick.py                    — denní byznys logika (krmení, bonus, páteční svoz, série)
  scheduler.py                — napojení tick.py na skutečný denní cron
  config.py                     — ceny, časy, limity, JWT a platební nastavení na jednom místě
  integrations/
    payments.py                    — MockPaymentProvider + funkční StripePaymentProvider
    notifications.py                — ConsoleNotificationProvider + kam zapojit FCM/APNs
  routers/
    auth.py, farms.py, hens.py, wallet.py, admin.py   — HTTP endpointy
  static/
    card-setup.html                                    — testovací stránka pro uložení karty (Stripe.js)
docs/
  PAYMENT_INTEGRATION.md   — jak Stripe integraci vyzkoušet, proč peněženka místo denní karty
  APP_STORE_GUIDE.md        — stav Android/iOS cesty, co zbývá
  BUSINESS_CHECKLIST.md     — co je potřeba zařídit mimo kód (firma, farmáři, regulace)
tests/
  test_api.py                — API, auth, vlastnictví dat mezi uživateli
  test_payments.py            — že Stripe kód volá SDK správně (bez potřeby účtu)
```

Viz i [`../mobile-app/`](../mobile-app/) — Capacitor/Android obal appky.

## Další krok

Než se tohle přiblíží k reálnému provozu, přečti si
[`docs/BUSINESS_CHECKLIST.md`](docs/BUSINESS_CHECKLIST.md) — technická
kostra je hotová dřív, než byznys/právní stránka věci, a je lepší to vědět
teď než po měsíci vývoje.
