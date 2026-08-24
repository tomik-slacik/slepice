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
- **Skutečný denní úkol** (APScheduler), který každé ráno spustí krmení
  a v pátek spočítá vejce — obdoba tlačítka "Posunout o den" z frontendového
  dema, ale doopravdy podle hodin, ne na kliknutí
- **Jasně oddělená místa** pro platební bránu a push notifikace
  (`app/integrations/`) — teď jen mockované, ať jde vidět přesně kam sáhnout
- **Testy**, které se dají spustit, ne jen přečíst

## Co v tom NENÍ (záměrně)

- **Žádné skutečné platby.** Peněženka a "denní strhávání" jsou jen záznamy
  v databázi. Napojení reálné platební brány je v
  [`docs/PAYMENT_INTEGRATION.md`](docs/PAYMENT_INTEGRATION.md).
- **Žádné přihlašování.** `Hen` (adopce) nese jen volné jméno vlastníka —
  není tu tabulka uživatelů, hesla ani OAuth. Přidat pořádnou autentizaci je
  nutný krok dřív, než se k tomu přiblíží skuteční zákazníci.
- **Žádné skutečné push notifikace.** Zatím se jen vypisují do konzole —
  napojení Firebase/APNs je popsané v `app/integrations/notifications.py`.
- **Žádná appka v App Store / Google Play.** Návod je v
  [`docs/APP_STORE_GUIDE.md`](docs/APP_STORE_GUIDE.md).
- **Žádné skutečné farmy ani rozvoz.** To je byznys/logistická stránka věci
  — checklist je v [`docs/BUSINESS_CHECKLIST.md`](docs/BUSINESS_CHECKLIST.md).

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

```bash
curl -X POST http://127.0.0.1:8000/admin/run-tick?days_offset=1
```

Zavolej to postupně s `days_offset=1,2,3...` a sleduj, jak přibývají
záznamy v `/hens/{id}/feed-log` a jak se v pátek objeví položka
v `/hens/{id}/deliveries`. Přesně totéž dělá tlačítko "Posunout o den"
ve frontendovém demu.

### Spustit testy

```bash
pytest -v
```

## Struktura projektu

```
app/
  main.py              — FastAPI aplikace, startup/shutdown
  models.py            — databázové tabulky (Farm, Hen, FeedLogEntry, Delivery, PausedDay)
  schemas.py            — validace vstupů/výstupů API
  tick.py                — denní byznys logika (krmení, bonus, páteční svoz, série)
  scheduler.py            — napojení tick.py na skutečný denní cron
  config.py                — ceny, časy, limity na jednom místě
  integrations/
    payments.py             — MockPaymentProvider + kam zapojit GoPay/Comgate/Stripe
    notifications.py         — ConsoleNotificationProvider + kam zapojit FCM/APNs
  routers/
    farms.py, hens.py, admin.py   — HTTP endpointy
docs/
  PAYMENT_INTEGRATION.md   — proč peněženka, ne denní karta; kam zapojit bránu
  APP_STORE_GUIDE.md        — jak se z webové appky stane appka v App Store/Google Play
  BUSINESS_CHECKLIST.md     — co je potřeba zařídit mimo kód (firma, farmáři, regulace)
tests/
  test_api.py                — smoke testy, které si tvůj vývojář (nebo Claude příště) spustí
```

## Další krok

Než se tohle přiblíží k reálnému provozu, přečti si
[`docs/BUSINESS_CHECKLIST.md`](docs/BUSINESS_CHECKLIST.md) — technická
kostra je hotová dřív, než byznys/právní stránka věci, a je lepší to vědět
teď než po měsíci vývoje.
