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
  počet neúspěšných plateb.
- **Farmy** — seznam s obsazeností, formulář na přidání skutečné farmy
  (klíč, název, poloha, kapacita) — jakmile ji přidáš, appka ji hned
  nabízí při adopci, včetně hledání podle vzdálenosti.
- **Uživatelé** — e-mail, počet slepiček, jestli má uloženou platební
  metodu, kdy se zaregistroval.
- **Denní tik ručně** (`POST /admin/run-tick`) — stejná appka jako dřív,
  teď jen zamčená za přihlášením.

## Co (zatím) neumí

Žádné mazání/blokování uživatele, žádná editace slepičky za uživatele,
žádný graf v čase (jen aktuální čísla) — základ, co odpovídá reálnému
provozu appky teď, ne kompletní back-office nástroj.
