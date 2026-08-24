# Logistika rozvozu — co appka řeší, co neřeší a proč

**Aktuální stav:** appka teď umí spočítat vzdálenost k farmě z reálné
polohy zařízení a odmítne přiřadit slepičku farmě, která už nemá volnou
kapacitu (`GET /farms?lat=&lng=&radius_km=`, kapacita v
`routers/hens.py`'s `adopt_hen()`) — obojí naživo otestované, ne jen
navržené. To, kdo fyzicky doveze vejce ke dveřím, appka neřeší a řešit
nemůže — to je byznysová/operační otázka, ne softwarová. Tenhle dokument
je o tom druhém.

## Co je teď doopravdy hotové

- **Reálná vzdálenost.** `navigator.geolocation` (nebo nativní
  `@capacitor/geolocation` v appce) → Haversine vzorec → farmy seřazené
  od nejbližší, s možností filtrovat na okruh (10/25/50 km). Stejná logika
  na obou stranách — v offline demu i v `GET /farms`.
- **Kapacita farmy.** Každá farma má `weekly_capacity` (kolik zákazníků
  týdně reálně zvládne). Appka odmítne adopci, když je farma plná
  (`409`), a v seznamu farem ukazuje `spots_left`. Bez tohohle by appka
  klidně nechala tisíc lidí vybrat si stejnou malou farmu s deseti
  slepicemi — model, co by v realitě okamžitě spadl.

## Co appka nevyřeší, protože to není softwarový problém

**Kdo fyzicky doveze vejce.** Tři reálné modely, ne vzájemně se
vylučující:

1. **Farma si veze sama.** Funguje jen v malém okruhu (desítky km,
   ideálně jeden směr denně) — spousta menších farem už dnes takhle
   prodává vlastní "bedýnky". Nejjednodušší na rozjezd, ale škáluje jen
   tak, jak roste počet aut a řidičů na farmě.
2. **Externí kurýr.** Nutné až s větším okruhem/objemem. Problém: vejce
   jsou křehká a appka slibuje *čerstvá* vejce, ne "vejce co tři dny
   ležela v depu" — běžný balíkový kurýr (bez chlazení, bez šetrného
   zacházení) je pro tenhle produkt špatná shoda. Potřeba buď
   specializovaná služba na potraviny, nebo vlastní síť řidičů.
3. **Výdejní místa.** Zákazník si vyzvedne sám (stánek farmy, spřátelená
   prodejna, "vejce closet" v okolí). Nejnižší logistická zátěž, cenou je
   nižší pohodlí — běžný model u komunitou podporovaného zemědělství
   (CSA). Dobrá první volba pro pilot, než appka škáluje.

**Kde appka může pomoct, i když trasu nejede:** protože *všechna*
doručení jednoho farmáře padnou na stejný den (pátek), jde z adres
zákazníků v okruhu farmy sestavit **jedna rozvozová trasa místo
náhodných zastávek**. To by byla další reálná funkce (seřadit páteční
doručení dané farmy podle adresy/vzdálenosti do jedné trasy) — zatím
nepostavená, ale navazuje přímo na `Hen.address` + farm `lat`/`lng`, co
už appka má.

## Co appka nevyřeší, protože to je právní/byznysová otázka

- **Bezpečnost potravin.** Prodej a rozvoz čerstvých vajec domů
  pravděpodobně podléhá hygienickým předpisům (registrace prodejce,
  značení, sledovatelnost) — přesná pravidla se liší podle objemu a
  modelu prodeje a tohle není místo, kde bych měl hádat konkrétní
  paragrafy. Potřeba reálná konzultace s KVS/hygienickou stanicí, ne kód.
- **Skuteční farmáři.** Farmy v appce (i v databázi) jsou pořád vymyšlené
  — žádná smlouva s žádným farmářem neexistuje. Než appka doveze první
  reálné vejce, musí existovat aspoň jedna skutečná dohoda.
- **Pojištění a odpovědnost.** Kdo nese odpovědnost, když doručení
  nedorazí, dorazí rozbité, nebo někomu udělá špatně? Běžná součást
  smlouvy s dopravcem/farmářem, ne appky.

## Doporučené pořadí, kdyby se do tohohle šlo dál

1. Jedna skutečná farma, výdejní místo (ne rozvoz) — ověřit poptávku bez
   řešení logistiky vůbec.
2. Ta samá farma, rozvoz vlastním autem v malém okruhu (viz kapacita —
   proto appka teď farmám dovoluje nastavit realistický strop).
3. Až tohle funguje a roste poptávka mimo dojezd jedné farmy: druhá
   farma jinde (appka na to je připravená - najít farmy podle polohy je
   přesně pro tenhle moment), případně trasování/kurýr.
