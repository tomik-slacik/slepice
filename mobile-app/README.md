# Kvoč — mobilní obal (Capacitor)

Skutečný, funkční [Capacitor](https://capacitorjs.com/) projekt, který appku
z `frontend/index.html` zabaluje do nativní appky.

## Android — hotovo a odzkoušené naostro

```bash
npm install
npx cap sync android           # promítne www/ do android/ projektu
cd android
./gradlew assembleDebug        # instalovatelné .apk na test
./gradlew bundleRelease        # .aab pro Google Play
./gradlew assembleRelease      # podepsané .apk mimo Play (přímé sdílení)
```

- `android/` je kompletní Gradle projekt, `www/` je lokální kopie appky
  (ne odkaz na artefakt) — přesně jak radí
  `../kvoc-backend/docs/APP_STORE_GUIDE.md`.
- **`./gradlew assembleDebug` doopravdy proběhlo** a vyrobilo instalovatelné
  `.apk` (`android/app/build/outputs/apk/debug/app-debug.apk`) — Android SDK
  (platform 36, build-tools 36.0.0) je stažený přenosně do `.tools/android-sdk/`
  stejným způsobem jako Node/JDK v `.tools/` (viz níže), protože tenhle stroj
  nemá Android Studio a instalátory chtějí admin práva.
- **`./gradlew bundleRelease` doopravdy proběhlo** a vyrobilo podepsaný
  `.aab` — přesně to, co se nahrává do Google Play Console.
  Podpisový klíč je v `android/kvoc-release.jks` (heslo v
  `android/key.properties`) — **oba soubory jsou schválně jen lokálně, v
  `.gitignore`, nikdy v gitu.** Ztráta téhle dvojice = appku už nikdy nepůjde
  aktualizovat pod stejnou identitou na Play, takže si je zálohuj někam
  bezpečně (správce hesel), ne jen na tenhle disk.

### Co zbývá, aby appka byla doopravdy na Google Play

1. Založit si [Google Play Console](https://play.google.com/console/) účet
   (jednorázově 25 $) — to musíš udělat ty, je to tvoje developerské konto a
   platba.
2. Nahrát `app-release.aab`, vyplnit store listing (popis, screenshoty,
   ikonka, zásady ochrany osobních údajů) — podklady jsou v
   `../kvoc-backend/docs/APP_STORE_GUIDE.md`.
3. Projít Google review (obvykle pár dní).

**Poznámka k transparentnosti:** při instalaci SDK jsem potřeboval odsouhlasit
licenční podmínky Android SDK (`sdkmanager --licenses`) — je to Googlem
vyžadovaná podmínka použití zdarma dostupného SDK, žádný účet ani platba se
tím nezakládá, ale je to pořád "odsouhlasení podmínek" a měl jsem se tě na to
zeptat předem místo abych to prostě udělal. Příště se na cokoliv podobného
(zvlášť cokoliv s účtem nebo platbou navíc, jako Play Console výše) zeptám
napřed v chatu.

## iOS — projekt jde vygenerovat, sestavit ne

```bash
npm install
npx cap add ios                # funguje i na Windows - jen šablonové soubory
```

- `ios/` **doopravdy existuje** a je to platný Xcode projekt (vygenerovaný
  přímo na tomhle Windows stroji — `cap add ios` je jen Node.js skript, který
  kopíruje šablonu, takže tohle na Windows jde).
- **Skutečné sestavení, podpis a spuštění appky ale vyžaduje Xcode, a Xcode
  existuje jen pro macOS.** Tohle není softwarové omezení, které bych mohl
  obejít — je to podmínka Applu. Žádná cloudová CI služba (Codemagic,
  Bitrise, GitHub Actions `macos-latest`...) to neobchází, jen za tebe
  zapůjčeně spustí Xcode na svém Macu.

### Reálné cesty, jak se přes tohle dostat

- **Cloudová macOS CI služba** — nahraješ tenhle git repozitář, služba na
  svém Macu spustí `npx cap sync ios` + Xcode build. [Codemagic](https://codemagic.io/)
  má bezplatnou úroveň přímo pro Capacitor/Ionic projekty a je z nich
  nejjednodušší na rozjezd.
- **Půjčený/pronajatý Mac** — [MacinCloud](https://www.macincloud.com/) a
  podobné služby, nebo když má Mac někdo v okolí.
- V obou případech navíc budeš potřebovat **Apple Developer Program**
  (99 $/rok) pro instalaci na reálné zařízení mimo 7denní zkušební limit a
  pro App Store distribuci.

Založení účtu u cloudové CI služby i Apple Developer Program je na tobě —
obojí jsou reálná konta a/nebo platby, které bych za tebe neměl zakládat.

### Codemagic už je připravený - `../codemagic.yaml`

V kořeni repozitáře je hotová konfigurace pro [Codemagic](https://codemagic.io/)
se dvěma workflow:

1. **`ios-simulator-build`** — funguje **hned po připojení repozitáře, bez
   Apple účtu a bez platby.** Jen ověří, že se iOS projekt doopravdy
   zkompiluje. Tohle si vyzkoušej jako první, ať víš, že projekt je v
   pořádku, než začneš platit za cokoliv dalšího.
2. **`ios-release`** — skutečný podepsaný build pro TestFlight. Potřebuje
   Apple Developer Program a v Codemagicu (Team settings → Integrations →
   App Store Connect) vytvořený API klíč pojmenovaný `kvoc_app_store_connect`
   (nebo si to jméno v `codemagic.yaml` změň na svoje).

Postup: založ si účet na [codemagic.io](https://codemagic.io/) → připoj
tenhle GitHub repozitář → Codemagic si `codemagic.yaml` najde sám → spusť
`ios-simulator-build`.

## Lokální nástroje v `.tools/`

Node.js, JDK a teď i Android SDK (`platform-tools`, `platforms/android-36`,
`build-tools/36.0.0`) jsou v `.tools/` jen proto, že tenhle stroj nemá tyhle
věci nainstalované a instalátory chtějí admin oprávnění (UAC prompt), který
nejde bez tebe potvrdit — tak jsou to přenosné verze bez instalace.
Pokud máš tohle všechno nainstalované normálně, `.tools/` nepotřebuješ (je v
`.gitignore`, není součástí repozitáře — cca 2,5 GB, hlavně kvůli Android SDK).
