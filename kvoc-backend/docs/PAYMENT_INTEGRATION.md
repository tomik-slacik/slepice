# Napojení skutečné platební brány

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

## Kam přesně sáhnout

`app/integrations/payments.py` definuje `PaymentProvider` — rozhraní se
dvěma metodami (`charge_topup`) a jednu bezpečnou výchozí implementaci
(`MockPaymentProvider`), která nikdy nehne se skutečnými penězi, jen loguje.
Až budeš mít účet u brány:

1. Napiš novou třídu, např. `GoPayPaymentProvider(PaymentProvider)`,
   která implementuje `charge_topup` proti skutečnému SDK/API.
2. V `get_payment_provider()` na konci souboru vrať novou třídu místo
   `MockPaymentProvider` — podle proměnné prostředí (`KVOC_PAYMENT_PROVIDER`),
   ne natvrdo, ať jde snadno přepínat mezi sandboxem brány a produkcí.
3. Přidej skutečné volání `charge_topup(...)` do plánovače (analogicky
   k `app/scheduler.py`) — dobíjecí cyklus (týdně/měsíčně), ne denně.
4. API klíče vždy přes proměnné prostředí (`os.environ`), nikdy natvrdo
   v kódu ani v gitu. `.gitignore` už počítá se souborem `.env`.

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
