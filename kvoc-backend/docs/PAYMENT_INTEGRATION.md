# Napojení skutečné platební brány

**Aktuální stav:** `app/integrations/payments.py` teď obsahuje skutečnou,
funkční implementaci pro Stripe (`StripePaymentProvider`), ne jen popis —
ověřenou proti aktuální Stripe dokumentaci (Setup Intents API) a otestovanou
(`tests/test_payments.py` kontroluje, že kód volá Stripe SDK správně).
**Nikdy ale neběžela proti skutečnému Stripe účtu** — jeho založení je na
tobě, viz níž. Výchozí a bezpečný poskytovatel zůstává `MockPaymentProvider`
(`KVOC_PAYMENT_PROVIDER=mock`, výchozí hodnota) — appka funguje kompletně
i bez jakéhokoli platebního účtu.

## Proč appka nestrhává kartu doopravdy každý den

Fixní poplatek za jednu kartovou transakci je u českých bran typicky
v řádu 2–3 Kč. Na dvacetikorunové platbě je to 10–15 % pryč jen na
poplatcích — ekonomicky to nedává smysl.

**Řešení: peněženka.** Uživatel skutečnou platbou dobíjí zůstatek jednou
týdně nebo měsíčně (jedna reálná transakce místo pěti až třiceti). Denní
"krmení" je jen interní odpočet z toho zůstatku — přesně to dělá
`app/tick.py` už teď, jen bez skutečných peněz za tím.

Tenhle backend tedy nikdy nemá volat platební bránu z `tick.py`. Platba
patří na dva jasně oddělená místa:

1. **Dobití peněženky** — pravidelná, hromadná platba (viz níže)
2. **`app/integrations/payments.py`** — jediné místo v kódu, které smí
   platební bránu volat

## Jak Stripe integraci doopravdy vyzkoušet

1. Založ si (sám — appka to za tebe udělat nemůže) účet na
   [dashboard.stripe.com/register](https://dashboard.stripe.com/register).
   Testovací klíče (začínají `sk_test_`/`pk_test_`) jdou hned bez ověřování
   firmy — ty stačí na vyzkoušení celého toku.
2. Spusť backend s:
   ```bash
   set KVOC_PAYMENT_PROVIDER=stripe
   set KVOC_STRIPE_SECRET_KEY=sk_test_...
   set KVOC_STRIPE_PUBLISHABLE_KEY=pk_test_...
   python run.py
   ```
3. Zaregistruj uživatele a přihlas se (`/auth/register`, `/auth/login`),
   adoptuj slepičku (`POST /hens`).
4. Otevři `http://127.0.0.1:8000/static/card-setup.html` — jednoduchá
   testovací stránka, kam vlož token a ID slepičky a ulož testovací kartu
   (Stripe testovací číslo `4242 4242 4242 4242`, libovolné datum/CVC).
5. Zavolej `POST /hens/{id}/wallet/topup` s částkou — appka strhne
   uloženou kartu doopravdy (v testovacím režimu, žádné skutečné peníze).

## Kam sáhnout pro jinou bránu (GoPay, Comgate)

`app/integrations/payments.py` definuje `PaymentProvider` — rozhraní se
třemi metodami (`ensure_customer`, `create_setup_intent`,
`charge_saved_method`). `StripePaymentProvider` je hotová referenční
implementace; `MockPaymentProvider` bezpečný výchozí stav. Pro jinou bránu:

1. Napiš novou třídu, např. `GoPayPaymentProvider(PaymentProvider)`,
   která implementuje všechny tři metody proti skutečnému SDK/API brány.
2. V `get_payment_provider()` na konci souboru přidej větev pro novou
   hodnotu `KVOC_PAYMENT_PROVIDER`.
3. Skutečné volání `charge_saved_method(...)` patří do pravidelného
   plánovače (analogicky k `app/scheduler.py`) — dobíjecí cyklus
   (týdně/měsíčně), ne denně.
4. API klíče vždy přes proměnné prostředí, nikdy natvrdo v kódu ani v gitu.

## Které brány zvážit (ČR)

| Brána | Poznámka |
|---|---|
| [GoPay](https://www.gopay.com/) | česká, dobrá podpora opakovaných plateb / tokenizace karty |
| [Comgate](https://www.comgate.cz/) | česká, podobné zaměření |
| [Stripe](https://stripe.com/) | mezinárodní, Payment Intents + uložená karta pro opakované strhávání |

Všechny tři umí "uložit kartu a strhávat opakovaně bez zásahu uživatele"
(tokenizace) — to je přesně vzor, který dobíjení peněženky potřebuje.
Automatické dobití při nízkém zůstatku (jako peněženka u Boltu/Uberu) je
rozšíření stejného vzoru — nejdřív ověř základní opakovanou platbu, pak
přidávej automatiku.

## Právní poznámka — nekonzultováno s právníkem

Peněženka, kam si uživatel předem uloží peníze na budoucí nákup vlastního
zboží appky, se v Česku obvykle řeší jako poukázka na zboží/službu, ne jako
elektronické peníze — ale tahle appka žádnou právní kvalifikaci nemá
a **tohle není právní rada**. Než appka začne přijímat skutečné peníze od
skutečných lidí, nech si formu peněženky (poukázka vs. e-peníze podle
zákona o platebním styku) potvrdit od advokáta se zaměřením na fintech/
platební služby. Viz i `docs/BUSINESS_CHECKLIST.md`.
