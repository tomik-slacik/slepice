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

## Cesta A: Render (nejmíň kroků)

1. Nahraj tenhle repozitář na GitHub (pokud tam ještě není).
2. Na [render.com](https://render.com) si založ účet a propoj ho
   s GitHubem.
3. **New → Blueprint**, vyber tenhle repozitář. Render najde
   [`render.yaml`](../../render.yaml) v kořeni repozitáře a navrhne:
   - webovou službu `kvoc-api` (postavenou z `kvoc-backend/Dockerfile`)
   - databázi `kvoc-db` (Postgres, bezplatná úroveň)
4. Potvrď. Render appku sestaví a spustí; `KVOC_JWT_SECRET` se vygeneruje
   automaticky, `KVOC_DATABASE_URL` se propojí na databázi automaticky.
5. Až appka naběhne, dostaneš adresu typu `https://kvoc-api.onrender.com`.
   Appka na `/app/` a dokumentace na `/docs` fungují stejně jako lokálně.

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
| `KVOC_ADMIN_TOKEN` | Ne (ale bez něj a bez `is_admin` účtu je `/admin/*` úplně nedostupné) | Viz `ADMIN.md`. |

## Co si pohlídat

- **Bezplatné úrovně obvykle appku "uspávají"** po pár minutách bez
  provozu a znovu probouzí až na další požadavek. To znamená, že
  `app/scheduler.py` (denní úkol v 8:00) **nemusí spolehlivě naběhnout**,
  pokud appka zrovna spí. Pro skutečný provoz buď placená "always on"
  úroveň, nebo externí služba, která `POST /admin/run-tick` zavolá zvenku
  v daný čas (`/admin/run-tick` už teď vyžaduje admin přihlášení - viz
  `ADMIN.md` - tenhle TODO je vyřešený).
- **Jakmile appka běží na skutečné adrese**, otevři
  `mobile-app-real/www/config.js` a nastav `window.KVOC_API_BASE` na tu
  adresu (`https://...`) — to je jediná změna, co `mobile-app-real/`
  (skutečná appka s přihlášením/platbami/push notifikacemi, na rozdíl od
  `mobile-app/`, což je pořád jen offline demo) potřebuje, aby mluvila se
  skutečným backendem. Viz `mobile-app-real/README.md`.
- **`KVOC_CORS_ORIGINS=*`** je v pořádku, dokud appku volá jen
  `app/webapp/` ze stejné adresy. Přidáš-li samostatně hostovaný frontend
  jinde, zúž to na jeho konkrétní adresu.
