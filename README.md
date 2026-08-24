# Kvoč

Appka, kde denní drobné za virtuální krmení slepičky promění pátek v den
čerstvých vajec doručených domů.

## V tomhle repozitáři

- **`frontend/index.html`** — funkční appka (adopce, denní přehled,
  aktivita, nastavení). Otevři přímo v prohlížeči — nic se nemusí
  instalovat. Stav si appka pamatuje v prohlížeči (localStorage). Zatím
  bez skutečných plateb a bez napojení na backend.
- **`kvoc-backend/`** — API server s **přihlašováním** (JWT, bcrypt),
  **skutečnou platební integrací pro Stripe** (otestováno, nikdy neběžela
  proti reálnému účtu — ten je na tobě) a skutečným denním cyklem. 21
  testů. Viz [`kvoc-backend/README.md`](kvoc-backend/README.md).
- **`mobile-app/`** — Capacitor/Android obal appky. Reálný Gradle projekt,
  rozjetý až na instalaci Android SDK (jeden krok, viz jeho README). iOS
  potřebuje Mac. Viz [`mobile-app/README.md`](mobile-app/README.md).

## Co v tom není (záměrně)

Skutečné peníze (bez tvého vlastního Stripe/GoPay účtu appka nikam neteče),
appka doopravdy publikovaná v App Store/Google Play, skuteční farmáři
a rozvoz. Checklist na dokončení je v
[`kvoc-backend/docs/BUSINESS_CHECKLIST.md`](kvoc-backend/docs/BUSINESS_CHECKLIST.md).

## Stav projektu

Koncept → klikací mockup → funkční appka → backend (auth, platby, denní
cyklus) → Android build **(jsi tady)** → skutečný Stripe účet → appka
v obchodech → pilot s reálnými farmáři.
