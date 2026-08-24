# Kvoč — skutečná appka (Capacitor)

Na rozdíl od [`mobile-app/`](../mobile-app/) (offline demo — žádné
přihlášení, žádný backend, funguje sama o sobě) je tohle appka, co obaluje
skutečnou appku s přihlášením, platbami, push notifikacemi a hledáním
farem podle polohy — [`kvoc-backend/app/webapp/index.html`](../kvoc-backend/app/webapp/index.html),
zkopírované do `www/index.html`.

## Jediná věc, co musíš nastavit

`www/index.html` byla vždycky navržená tak, aby běžela **na stejné
adrese jako backend** (relativní API cesty jako `/auth/login`) — v
nativní appce ale běží ze svého vlastního `capacitor://`/`https://`
originu, takže potřebuje vědět, kde backend doopravdy je.

Otevři **`www/config.js`** a nastav:

```js
window.KVOC_API_BASE = 'https://tvoje-skutecna-adresa-backendu.example.com';
```

Bez tohohle appka neví, kam se připojit. Výchozí hodnota
(`http://10.0.2.2:8000`) je jen pro testování proti backendu, co ti
běží lokálně na stejném počítači jako Android emulátor — nikomu jinému
appku takhle nesdílej, `10.0.2.2` mimo emulátor nikam nevede.

## Sestavení

Stejný postup jako `mobile-app/` (viz jeho README pro víc detailů o
`.tools/` a proč jsou přenosné nástroje potřeba):

```bash
npm install
npx cap sync android
cd android
./gradlew assembleDebug     # instalovatelné .apk na test
./gradlew bundleRelease     # .aab pro Google Play (potřebuje key.properties)
```

**Doopravdy vyzkoušené:** `./gradlew assembleDebug` i `bundleRelease` +
`assembleRelease` proběhly a appka byla naživo otestovaná (přes lokální
HTTP server simulující jiný origin) — registrace, výběr farmy podle
polohy, adopce slepičky, to všechno přes skutečné volání na běžící
backend, žádná chyba v konzoli.

## Co appka umí, co `mobile-app/` neumí

- Skutečné přihlášení a účty (`kvoc-backend`).
- Skutečné platby (Stripe, `KVOC_PAYMENT_PROVIDER=stripe` — viz
  `../kvoc-backend/docs/PAYMENT_INTEGRATION.md`).
- Skutečné push notifikace (`@capacitor/push-notifications` + Firebase —
  viz `../kvoc-backend/docs/NOTIFICATIONS.md`).
- Skutečné hledání farem podle polohy (`@capacitor/geolocation`).

## Co appka pořád nemá

- **Skutečný backend, kam by se appka mohla připojit** — nasazení
  (Render/jinam) jsme nikdy nedotáhli do konce, viz
  `../kvoc-backend/docs/DEPLOYMENT.md`. Appka je na to připravená
  (viz sekce výše), ale bez běžícího backendu na skutečné adrese
  appku nemá cenu nikomu dávat.
- iOS verze — viz `mobile-app/README.md`, stejné omezení (Xcode jen na
  macOS) platí i tady; `npx cap add ios` by fungoval stejně, jen nikdo
  nezkusil sestavit skutečný Xcode projekt pro tenhle konkrétní `www/`.
