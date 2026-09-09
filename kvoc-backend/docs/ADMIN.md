# Admin přehled

**Aktuální stav:** skutečný, funkční admin přehled — `app/static/admin.html`
volá `/admin/*` endpointy (`app/routers/admin.py`). Otestováno naživo v
prohlížeči proti běžícímu backendu (přidání reálné farmy přes formulář,
zobrazení uživatelů/tržeb), ne jen navrženo.

## Jak se dostat dovnitř

Dvě nezávislé cesty, obě v `auth.py`'s `require_admin`:

1. **Sdílený token** — nastav `KVOC_ADMIN_TOKEN` (libovolný dlouhý
   náhodný řetězec) jako proměnnou prostředí backendu, pak ho zadej do
   pole na `/static/admin.html`. Nejjednodušší pro jednoho/dva lidi.
2. **Účet s `is_admin=True`** — pro víc lidí s vlastním přihlášením.
   Appka nemá "povýšit na admina" endpoint schválně (admin, co si sám
   sobě přidá práva přes API, je přesně ten typ díry, co nechceš) —
   nastavuje se přímo v databázi:
   ```bash
   python -c "from app.database import SessionLocal; from app import models; db=SessionLocal(); u=db.query(models.User).filter(models.User.email=='tvuj@email.cz').first(); u.is_admin=True; db.commit()"
   ```

**Bez ani jednoho z těchto dvou kroků je `/admin/*` úplně nedostupné** —
ne "otevřené, dokud něco nenastavíš", jak to bylo předtím (viz TODO, co
bývalo v `app/routers/admin.py` a teď je vyřešené).

## Co admin přehled umí

- **Přehled** — počet účtů, slepiček, aktivní/pozastavené, celkové tržby,
  počet neúspěšných plateb, a totéž pro ostatní zvířata a sdílené chovy
  na maso (`docs/LIVESTOCK.md`), plus **trend za posledních 14 dní**
  (nových účtů a tržeb za den, `GET /admin/stats/timeseries?days=`) —
  malý sloupcový graf pod dlaždicemi, ne jen aktuální čísla.
- **Farmy** — seznam s obsazeností, formulář na přidání skutečné farmy
  (klíč, název, poloha, kapacita) — jakmile ji přidáš, appka ji hned
  nabízí při adopci, včetně hledání podle vzdálenosti. Tlačítko
  **Trasa** u každé farmy spočítá a ukáže páteční rozvozovou trasu (viz
  `docs/LOGISTICS.md`) — kdo je activ na řadě, v jakém pořadí, kolik km
  mezi zastávkami, a kdo nemá uloženou polohu (nedá se zařadit).
- **Uživatelé** — e-mail, počet slepiček, jestli má uloženou platební
  metodu, kdy se zaregistroval. `GET /admin/users` je stránkované
  (`?limit=&offset=`, výchozí 100/stránka) — přehled zatím zobrazuje jen
  první stránku, viz "Co (zatím) neumí" níž. Tlačítko **Detail** u
  každého uživatele (`GET /admin/users/{id}`) ukáže jeho slepičky i
  ostatní zvířata se jmény/farmou/částkou — a přímo odsud jde:
  - **pozastavit/obnovit** jednotlivou slepičku nebo zvíře
    (`PATCH /admin/hens/{id}`, `PATCH /admin/animals/{id}`) — stejná pole,
    co může měnit sám zákazník, jen bez kontroly vlastnictví, takže
    support požadavek ("můžeš mi prosím pozastavit slepičku, jsem na
    dovolené") jde rovnou vyřídit místo jen přeposlat zpátky uživateli;
  - **smazat celý účet** (`DELETE /admin/users/{id}`) — skutečné smazání
    v kaskádě (slepičky, zvířata, podíly na mase, historie), stejný
    mechanismus jako `DELETE /auth/me`, jen spouštěný adminem za
    uživatele. Skutečná potřeba kvůli GDPR výmazu
    (`docs/BUSINESS_CHECKLIST.md`), ne jen "moderace" — odmítne smazat
    účet s `is_admin=True` touhle cestou schválně (nechceš si omylem
    smazat jediný admin účet).
- **Denní tik ručně** (`POST /admin/run-tick`) — stejná appka jako dřív,
  teď jen zamčená za přihlášením. V produkci navíc běží automaticky
  přes GitHub Actions (`.github/workflows/daily-tick.yml`) — řeší
  přesně tohle, viz `docs/DEPLOYMENT.md`'s "Co si pohlídat".

## Co (zatím) neumí

Přehled si zatím nenačítá druhou stránku uživatelů sám (API to podporuje,
`admin.html` ještě ne). `PATCH /admin/hens/{id}`/`.../animals/{id}` už
podporují stejná pole jako zákaznická verze (jméno, adresa, denní
částka, pauza) — `admin.html`'s Detail panel z toho zatím ve svém UI
nabízí jen pozastavit/obnovit, ne úpravu jména/adresy/částky natvrdo
(chybí tam formulář, ne backend). Žádné hromadné akce (jedna
slepička/účet najednou) — základ, co odpovídá reálnému provozu appky
teď, ne kompletní back-office nástroj.
