# Kvoč — mobilní obal (Capacitor)

Tohle je skutečný, funkční [Capacitor](https://capacitorjs.com/) projekt,
který appku z `frontend/index.html` zabalí do nativní Android appky.
**Otestováno až po jeden konkrétní chybějící krok** — viz níž.

## Co je hotové a odzkoušené

```bash
npm install                    # Capacitor CLI + core
npx cap init "Kvoč" "cz.kvoc.app" --web-dir www
npx cap add android            # vygeneruje android/ — reálný Gradle projekt
```

- `www/index.html` je **lokální kopie appky**, ne odkaz na artefakt —
  přesně jak radí `../kvoc-backend/docs/APP_STORE_GUIDE.md`.
- `android/` je kompletní, reálný Gradle projekt. `./gradlew tasks`
  proběhne **úspěšně** (ověřeno) — Gradle se s projektem srovná.
- `./gradlew assembleDebug` (skutečné sestavení instalovatelného .apk)
  selže na jedné konkrétní věci:

  ```
  SDK location not found. Define a valid SDK location with an
  ANDROID_HOME environment variable or by setting the sdk.dir path in
  your project's local properties file.
  ```

## Co chybí — jeden krok

**Android SDK.** Tenhle stroj nemá Android Studio a stažení celého SDK
(cca 1–2 GB) a odsouhlasení licenčních podmínek Google jsem záměrně
nechal na tobě — je to reálná licenční dohoda, kterou má schválit člověk,
ne appka za něj.

1. Nainstaluj [Android Studio](https://developer.android.com/studio)
   (obsahuje SDK manager) — nebo jen
   [command-line tools](https://developer.android.com/studio#command-tools),
   pokud nechceš celé IDE.
2. Nastav proměnnou prostředí `ANDROID_HOME` na cestu k SDK.
3. V `android/` spusť `./gradlew assembleDebug` — výstupní `.apk` najdeš
   v `android/app/build/outputs/apk/debug/`.
4. Nainstaluj si ho na telefon (nebo do emulátoru) a vyzkoušej.

Odtud dál pokračuje `../kvoc-backend/docs/APP_STORE_GUIDE.md` — podpis
appky, Google Play Console účet, store listing.

## iOS — tvrdá zeď

Sestavení a podpis iOS appky **vyžaduje Mac s Xcode** — to není softwarová
volba, je to podmínka Applu, kterou nejde na Windows obejít (ani cloudové
CI služby jako Codemagic/Bitrise nakonec běží na skutečném Macu, jen
pronajatém). Bez přístupu k Macu se k appce v App Store nedá dostat odsud.

## Lokální nástroje v `.tools/`

Node.js a JDK jsou v `.tools/` jen proto, že jejich instalátory na tomhle
stroji vyžadují admin oprávnění (UAC prompt), který nejde bez tebe
potvrdit — tak jsem použil přenosné verze bez instalace. Pokud máš
Node.js/JDK nainstalované normálně, `.tools/` nepotřebuješ (je v
`.gitignore`, není součástí repozitáře).
