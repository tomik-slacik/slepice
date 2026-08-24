# Napojení skutečných push notifikací (Firebase Cloud Messaging)

**Aktuální stav:** `app/integrations/notifications.py` teď obsahuje
skutečnou, funkční implementaci pro Firebase Cloud Messaging
(`FCMNotificationProvider`), ne jen popis — otestovanou
(`tests/test_notifications.py` kontroluje, že kód volá Firebase Admin SDK
správně) a ověřenou naživo end-to-end (registrace zařízení, denní tik,
`/auth/device-token`) proti běžícímu backendu. **Nikdy ale neběžela proti
skutečnému Firebase projektu** — jeho založení je na tobě, viz níž. Výchozí
a bezpečný poskytovatel zůstává `ConsoleNotificationProvider`
(`KVOC_NOTIFICATION_PROVIDER=console`, výchozí hodnota) — appka funguje
kompletně i bez jakéhokoli Firebase účtu, notifikace se jen vypisují do
konzole místo na telefon.

## Proč appka dřív neposílala doopravdy

Appka (offline demo i webappka) uměla ukázat notifikaci jen když byla
appka zrovna otevřená — ne skutečnou zprávu, co přijde sama, kdykoliv,
i se zavřenou appkou. To je přesně to, co FCM řeší: server appce pošle
push, telefon ho ukáže, appka běžet nemusí.

**Offline demo appka (`frontend/index.html`) tohle mít nemůže** — nemá
žádný server, který by v reálném čase věděl, kdy poslat push. Skutečné
notifikace patří jen k appce napojené na skutečný backend
(`app/webapp/index.html`), protože push vyžaduje vztah appka ↔ účet ↔
zařízení, který offline demo záměrně nemá.

## Jak to funguje

1. Appka (v nativním Capacitor obalu, ne v obyčejném prohlížeči) si po
   přihlášení vyžádá oprávnění a zaregistruje se u FCM
   (`registerPushIfNative()` v `app/webapp/index.html`).
2. Dostane zpátky token zařízení a pošle ho na `POST /auth/device-token`
   — uloží se do `User.fcm_token`.
3. Denní tik (`app/tick.py`) při každé události (nakrmení, bonus, pátek,
   doručeno) zavolá `notifier.send(hen_id, device_token, title, body)`.
4. `FCMNotificationProvider` pošle skutečný push přes Firebase Admin SDK.
5. Odhlášení appku ze zařízení zase odregistruje (prázdný token) — jinak
   by nové notifikace mohly chodit i po odhlášení, komukoliv, kdo se na
   stejném zařízení přihlásí pod jiným účtem.

## Jak to doopravdy vyzkoušet

1. Založ si (sám — appka to za tebe udělat nemůže) projekt na
   [console.firebase.google.com](https://console.firebase.google.com/) —
   zdarma, bez karty (Spark plán stačí na FCM).
2. V projektu přidej **Android appku** s package name přesně
   `cz.kvoc.app` (najdeš ho i v `mobile-app/android/app/build.gradle`).
   Stáhni `google-services.json` a ulož ho do
   `mobile-app/android/app/google-services.json` — `build.gradle` už na
   tenhle soubor čeká (dokud tam není, appka se pořád normálně sestaví,
   jen bez fungujícího FCM — viz komentář v `app/build.gradle`).
3. V projektu jdi na **Project settings → Service accounts → Generate new
   private key** — stáhne se JSON. To je pověření pro *backend* (odlišné
   od `google-services.json`, což je pověření pro *appku*).
4. Spusť backend s:
   ```bash
   set KVOC_NOTIFICATION_PROVIDER=fcm
   set KVOC_FIREBASE_CREDENTIALS_JSON={"type":"service_account", ...celý obsah stazeneho JSON na jeden radek...}
   python run.py
   ```
5. Přesynchronizuj a znovu sestav appku (`npx cap sync android` v
   `mobile-app/`, pak `./gradlew assembleDebug` v `mobile-app/android/`),
   ať se do ní dostane `google-services.json`.
6. Nainstaluj appku na reálný telefon, přihlas se, počkej na denní tik
   (nebo si ho postrč přes `POST /admin/run-tick`) — notifikace by měla
   dorazit i se zavřenou appkou.

## Co je za tebou, co za mnou

- **Za mnou (hotové a odzkoušené):** kompletní kód — provider, registrace
  zařízení, endpoint, propojení s denním tikem, testy, native plugin
  (`@capacitor/push-notifications`) přidaný a appka s ním prokazatelně
  jde sestavit i bez Firebase configu.
- **Za tebou:** založení Firebase projektu (účet, i když zdarma, je tvoje
  rozhodnutí) a nasazení backendu někam, kde skutečně běží 24/7 (viz
  `docs/DEPLOYMENT.md`) — bez toho denní tik nemá kdy spustit.
