# Nasazení backendu na skutečný server

Tenhle dokument předpokládá, že chceš, aby appka fungovala pro někoho
jiného než tebe na tomhle počítači — `http://127.0.0.1:8000` totiž vždycky
znamená "tenhle počítač", ať ho otevře kdokoliv odkudkoliv. Pro sdílení
appka potřebuje běžet na serveru, který má skutečnou, veřejně dostupnou
adresu.

**Nebylo to nasazené odsud** — založení účtu u poskytovatele je krok, který
musíš udělat ty (viz proč v `README.md` hlavního repozitáře). Tenhle
dokument a přiložené soubory (`Dockerfile`, `render.yaml`) tě k tomu
dostanou co nejblíž.

## Proč SQLite samo o sobě v cloudu nestačí

Appka teď ukládá data do souboru (`kvoc.db`) vedle sebe. Na většině
cloudových platforem (Render, Railway, Fly.io — na jejich bezplatných
úrovních) se souborový systém kontejneru **při každém restartu nebo
novém nasazení vymaže**. Bez řešení navíc by to znamenalo, že se všechna
data (účty, slepičky, historie) občas ztratí.

Řešení: skutečná databáze (Postgres) běžící odděleně od appky samotné.
Kód na to je už připravený — `app/database.py` čte `KVOC_DATABASE_URL`
a chová se jinak jen podle toho, jestli adresa začíná na `sqlite` nebo ne.
Změna databáze = změna jedné proměnné prostředí, žádný zásah do kódu.

## Schéma databáze a migrace

Appka při každém startu sama spustí skutečné, verzované DB migrace
(Alembic, `migrations/`) — žádný ruční krok navíc, `python run.py`
(nebo start kontejneru) to udělá samo. Nová verze kódu s novým sloupcem
v modelu se na existující databázi (klidně s reálnými daty) aplikuje
bezpečně, ne přepsáním nebo tichým selháním.

Přidání nové migrace při vývoji (po změně `app/models.py`):

```bash
alembic revision --autogenerate -m "co se změnilo"
```

Zkontroluj vygenerovaný soubor v `migrations/versions/` (autogenerace je
dobrý první návrh, ne vždycky přesně to, co chceš) a commitni ho spolu se
změnou modelu — je to normální zdrojový soubor, ne generovaný artefakt.
Appka ho při dalším startu sama použije; není potřeba nic spouštět ručně
ani na produkčním serveru.

## Cesta A: Render (nejmíň kroků)

**O peněz jde reálně u databáze, ne appky.** Bezplatná úroveň webové
služby je skutečně trvalá (appka po 15 minutách bez provozu "usne" a
další request ji o pár vteřin déle probudí — jinak zdarma napořád).
Bezplatný Postgres je ale jen **30denní zkouška na účet, jednorázově** —
účet, co ji už jednou využil (nebo mu vypršela), dostane při zakládání
nové databáze rovnou nabídku placeného tarilu. `render.yaml` proto
počítá s nejlevnějším placeným tarifem pro databázi
(`0.1c-256mb`, řádově 6 $/měsíc při psaní tohohle dokumentu — ověř
skutečnou cenu v Renderově rozhraní, než potvrdíš, ceny se mění).

1. Nahraj tenhle repozitář na GitHub (pokud tam ještě není).
2. Na [render.com](https://render.com) si založ účet a propoj ho
   s GitHubem.
3. **New → Blueprint**, vyber tenhle repozitář (nebo rovnou
   `https://dashboard.render.com/blueprint/new?repo=<adresa GitHub repa>`
   — přeskočí ruční hledání repa). Render najde
   [`render.yaml`](../../render.yaml) v kořeni repozitáře a navrhne:
   - webovou službu `kvoc-api` (postavenou z `kvoc-backend/Dockerfile`,
     bezplatná úroveň)
   - databázi `kvoc-db` (Postgres, placený tarif — viz výš)
4. Potvrď (**Apply**) — tohle je krok, který stojí peníze (měsíční
   předplatné databáze), zkontroluj cenu, než klikneš. `KVOC_JWT_SECRET`
   a `KVOC_ADMIN_TOKEN` se vygenerují automaticky, `KVOC_DATABASE_URL`
   se propojí na databázi automaticky.
5. Až appka naběhne, dostaneš adresu typu `https://kvoc-api.onrender.com`.
   Appka na `/app/` a dokumentace na `/docs` fungují stejně jako lokálně.
6. Vygenerovaný `KVOC_ADMIN_TOKEN` najdeš v Renderově dashboardu u
   `kvoc-api` služby → záložka **Environment**. Budeš ho potřebovat na
   dvou místech: přihlášení do `/static/admin.html`, a jako
   `KVOC_ADMIN_TOKEN` GitHub secret pro
   [`daily-tick.yml`](../../.github/workflows/daily-tick.yml) (spolu s
   `KVOC_API_URL` = adresou appky z kroku 5) — viz "Co si pohlídat" níž.

## Cesta B: Railway / Fly.io / cokoliv jiného s Dockerem

Stejný [`Dockerfile`](../Dockerfile) funguje kdekoliv, co umí spustit
Docker image. Obecný postup:

1. Založ účet, propoj repozitář (nebo nahraj image přímo).
2. Přidej Postgres databázi (obě platformy to nabízí jedním klikem).
3. Nastav proměnné prostředí (viz tabulka níže) — hlavně
   `KVOC_DATABASE_URL` na connection string té databáze.
4. Nasaď. Platforma typicky sama nastaví `PORT` — `run.py` už ho čte
   automaticky (`os.environ.get("PORT", "8000")`).

## Proměnné prostředí

| Proměnná | Povinná | Co dělá |
|---|---|---|
| `KVOC_DATABASE_URL` | Ano (v produkci) | Connection string databáze. Bez ní appka spadne zpátky na lokální SQLite soubor. |
| `KVOC_JWT_SECRET` | Ano | Podepisuje přihlašovací tokeny. Bez pevné hodnoty appka vygeneruje náhodný klíč při každém startu a všichni se odhlásí. |
| `KVOC_CORS_ORIGINS` | Ne | Kdo smí volat API z prohlížeče odjinud. `app/webapp/` to nepotřebuje (běží ze stejné adresy) — nastav, jen pokud appku budeš volat z jiné domény. |
| `KVOC_PAYMENT_PROVIDER` | Ne | `mock` (výchozí) nebo `stripe`. |
| `KVOC_STRIPE_SECRET_KEY`, `KVOC_STRIPE_PUBLISHABLE_KEY` | Jen pro `stripe` | Viz `PAYMENT_INTEGRATION.md`. |
| `KVOC_NOTIFICATION_PROVIDER` | Ne | `console` (výchozí) nebo `fcm`. Viz `NOTIFICATIONS.md`. |
| `KVOC_FIREBASE_CREDENTIALS_JSON` | Jen pro `fcm` | Viz `NOTIFICATIONS.md`. |
| `KVOC_EMAIL_PROVIDER` | Ne | `console` (výchozí) nebo `smtp`. Viz `EMAIL.md`. |
| `KVOC_SMTP_HOST/PORT/USERNAME/PASSWORD`, `KVOC_EMAIL_FROM` | Jen pro `smtp` | Viz `EMAIL.md`. |
| `KVOC_ADMIN_TOKEN` | Ne (ale bez něj a bez `is_admin` účtu je `/admin/*` úplně nedostupné) | Viz `ADMIN.md`. Na Renderu `render.yaml` tohle vygeneruje automaticky - viz krok 6 výš. |

## Co si pohlídat

- **Bezplatné úrovně obvykle appku "uspávají"** po pár minutách bez
  provozu a znovu probouzí až na další požadavek. To znamená, že
  `app/scheduler.py` (denní úkol v 8:00) **nemusí spolehlivě naběhnout**,
  pokud appka zrovna spí. Řešeno: [`.github/workflows/daily-tick.yml`](../../.github/workflows/daily-tick.yml)
  volá `POST /admin/run-tick` zvenku, dvakrát denně (ráno + záložně
  odpoledne, pro případ že první pokus selže) - probudí appku i spustí
  tik napřímo, bezpečně i souběžně s interním schedulerem (tik je
  idempotentní na kalendářní den, viz `app/tick.py`). Potřebuje dva
  repozitářové secrets v GitHubu (`KVOC_API_URL`, `KVOC_ADMIN_TOKEN`) -
  bez nich workflow běží, ale rovnou selže s jasnou chybou, viz
  komentář v tom souboru. Placená "always on" úroveň zůstává alternativa,
  pokud radši nic navíc nastavovat nechceš.
- **Jakmile appka běží na skutečné adrese**, otevři
  `mobile-app-real/www/config.js` a nastav `window.KVOC_API_BASE` na tu
  adresu (`https://...`) — to je jediná změna, co `mobile-app-real/`
  (skutečná appka s přihlášením/platbami/push notifikacemi, na rozdíl od
  `mobile-app/`, což je pořád jen offline demo) potřebuje, aby mluvila se
  skutečným backendem. Viz `mobile-app-real/README.md`.
- **`KVOC_CORS_ORIGINS=*`** je v pořádku, dokud appku volá jen
  `app/webapp/` ze stejné adresy. Přidáš-li samostatně hostovaný frontend
  jinde, zúž to na jeho konkrétní adresu.
