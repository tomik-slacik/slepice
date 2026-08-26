# Mazlík

Appka, kde denní drobné za virtuální krmení slepičky (nebo kozy, ovce,
krávy) promění pátek v den čerstvých vajec, mléka nebo masa doručených
domů — dřív appka jen o slepicích ("Kvoč"), teď celý malý statek.

## V tomhle repozitáři

- **`frontend/index.html`** — appka offline: adopce, denní přehled,
  aktivita, statek (koza/ovce/kráva, sdílené chovy na maso), nastavení.
  Otevři přímo v prohlížeči, nic se nemusí instalovat ani spouštět. Stav
  v `localStorage`, žádný backend potřeba.
- **`kvoc-backend/`** — API server s **přihlašováním** (JWT, bcrypt),
  **skutečnou platební integrací pro Stripe** (otestováno, nikdy neběžela
  proti reálnému účtu — ten je na tobě) a skutečným denním cyklem. 66
  testů. Obsahuje i **[`app/webapp/`](kvoc-backend/app/webapp/)** —
  tatáž appka, ale doopravdy napojená na tohle API místo na
  `localStorage`; proklikaná a ověřená v prohlížeči, včetně chyb, které
  to živé klikání odhalilo (zůstatek peněženky se po demo posunu dne
  netvářil aktuálně — opraveno). Viz
  [`kvoc-backend/README.md`](kvoc-backend/README.md).
- **`mobile-app/`** — Capacitor/Android obal offline dema
  (`frontend/`). Reálný Gradle projekt, rozjetý až na instalaci Android
  SDK (jeden krok, viz jeho README). iOS potřebuje Mac. Viz
  [`mobile-app/README.md`](mobile-app/README.md).
- **`mobile-app-real/`** — stejný obal, ale kolem `app/webapp/` — tedy
  appka doopravdy napojená na `kvoc-backend`, ne na `localStorage`. Viz
  [`mobile-app-real/README.md`](mobile-app-real/README.md).

## Co v tom není (záměrně)

Skutečné peníze (bez tvého vlastního Stripe/GoPay účtu appka nikam neteče),
appka doopravdy publikovaná v App Store/Google Play, skuteční farmáři
a rozvoz. Checklist na dokončení je v
[`kvoc-backend/docs/BUSINESS_CHECKLIST.md`](kvoc-backend/docs/BUSINESS_CHECKLIST.md).

## Stav projektu

Koncept → klikací mockup → funkční appka → backend (auth, platby, denní
cyklus) → appka doopravdy napojená na backend **(jsi tady)** → nasazení
backendu někam na internet → skutečný Stripe účet → appka v obchodech →
pilot s reálnými farmáři.
