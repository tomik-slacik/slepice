# Cesta appky do App Store a Google Play

**Aktuální stav (odzkoušeno, ne jen naplánováno):** varianta A níže je už
rozjetá v [`../../mobile-app/`](../../mobile-app/) — skutečný Capacitor
projekt s vygenerovaným Android Gradle projektem, který úspěšně proběhne
přes `./gradlew tasks`. Chybí jediná věc: Android SDK (viz
[`mobile-app/README.md`](../../mobile-app/README.md) pro přesný další
krok). iOS jde odsud dál jen po instalaci na Macu — víc v tom README.

Ceny a přesná pravidla obchodů se v čase mění — než začneš platit, ověř si
aktuální podmínky přímo na developer.apple.com a play.google.com/console.

## Dvě reálné cesty

### A) Obal kolem webové appky (rychlejší start)

Nástroj jako [Capacitor](https://capacitorjs.com/) vezme existující
HTML/CSS/JS a zabalí ho do skutečného nativního projektu (Xcode pro iOS,
Android Studio pro Android), který pak jde poslat do obchodů. Appka uvnitř
běží prakticky beze změny.

- **Důležité:** appka dnes žije jako publikovaný Claude artefakt (cizí
  doména). Do nativního obalu se **nemá** vkládat odkaz na tuhle URL —
  místo toho se soubor appky zkopíruje přímo do Capacitor projektu
  (`www/index.html`) jako lokální, appce vlastní soubor. Jinak appka
  přestane fungovat ve chvíli, kdy se artefakt smaže nebo přestane být
  dostupný.
- Tahle cesta ti dá skutečné nativní ikony, splash screen, a hlavně
  **skutečné push notifikace přes Capacitor Push Notifications plugin**,
  napojené na `app/integrations/notifications.py` (FCM/APNs).
- Nevýhoda: appka bude technicky pořád "web ve WebView" — pro jednoduchou
  appku typu Mazlík to ale často nikdo nepozná.

### B) Nativní přepis (React Native / Flutter)

Víc práce, ale plynulejší pocit, lepší výkon a přirozenější přístup
k systémovým věcem (notifikace, widgety na ploše, Apple Wallet apod.).
Dává smysl až ve chvíli, kdy appka má reálné uživatele a stojí za to do ní
investovat víc. Datový model a API v `app/` zůstávají stejné bez ohledu na
to, jaký frontend na ně mluví.

**Doporučení:** začni variantou A. Je to otázka dnů, ne týdnů, a ověří to,
jestli appka vůbec stojí za nativní investici.

## Účty, které budeš potřebovat

| | Apple | Google |
|---|---|---|
| Program | Apple Developer Program | Google Play Console |
| Cena (orientačně) | ~99 USD/rok | jednorázový poplatek při registraci |
| Pro firmu | Organization účet — potřebuje D-U-N-S číslo (identifikace firmy, zdarma, ale zabere čas) | firemní i osobní účet jde, firemní důvěryhodněji |
| Vazba na firmu | Doporučeno založit až po registraci firmy (viz `BUSINESS_CHECKLIST.md`) — appka pak vystupuje pod jménem firmy, ne osoby | stejně |

## Jedna věc, na kterou si dát pozor: Apple a fyzické zboží

Mazlík prodává **fyzické zboží (vejce, mléko, podíl na mase) doručované mimo appku** — ne digitální obsah
uvnitř appky. Podle Apple App Store Review Guidelines (sekce o fyzickém
zboží a službách) appky tohoto typu **nemusí** používat Applein interní
nákupní systém (In-App Purchase) a mohou platbu řešit vlastní platební
bránou (viz `PAYMENT_INTEGRATION.md`) — podobně jako appky na rozvoz jídla
nebo taxi. Kdyby appka místo toho musela projít přes Applein IAP, znamenalo
by to jeho provizi (typicky 15–30 %) navíc k nákladům appky. Před podáním
appky do review si tohle přesto ověř v aktuální verzi guidelines — bývají
to jemné, občas měněné hranice.

## Než appku pošleš do review

- **Zásady ochrany osobních údajů** — obě appky vyžadují veřejnou URL
  s privacy policy (appka sbírá adresu, jméno, případně platební údaje).
- **Popis appky, screenshoty, ikona** — standardní materiály obchodu.
- **Testovací účet pro review tým**, pokud appka vyžaduje přihlášení
  (tenhle backend zatím přihlašování nemá — viz README).
- Google Play v posledních letech vyžaduje u nových účtů před ostrým
  spuštěním určité období uzavřeného/otevřeného testování — ověř aktuální
  požadavek v Play Console při zakládání účtu.
