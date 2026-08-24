# Kvoč

Appka, kde denní drobné za virtuální krmení slepičky promění pátek v den
čerstvých vajec doručených domů.

## V tomhle repozitáři

- **`frontend/index.html`** — funkční appka (adopce, denní přehled,
  aktivita, nastavení). Otevři přímo v prohlížeči — nic se nemusí
  instalovat. Stav si appka pamatuje v prohlížeči (localStorage). Zatím
  bez skutečných plateb a bez napojení na backend.
- **`kvoc-backend/`** — technický základ pro reálný provoz: API server,
  databáze, skutečný denní cyklus, jasně vyznačená místa pro platební
  bránu a push notifikace, návod na App Store/Google Play a byznys/právní
  checklist. Viz [`kvoc-backend/README.md`](kvoc-backend/README.md).

## Stav projektu

Koncept → klikací mockup → funkční frontendová appka → technický základ
backendu (**jsi tady**) → napojení frontendu na backend → reálné platby →
pilot. Podrobný další krok je v
[`kvoc-backend/docs/BUSINESS_CHECKLIST.md`](kvoc-backend/docs/BUSINESS_CHECKLIST.md).
