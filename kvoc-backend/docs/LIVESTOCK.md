# Ostatní hospodářská zvířata (koza/ovce/kráva) — co appka řeší a co ne

**Aktuální stav:** dvě nové, oddělené soustavy — `Animal` pro průběžný chov
(zatím jen mléko) a `MeatShare`/`ShareContribution` pro sdílený chov na
maso — jsou naprogramované a otestované (`tests/test_livestock.py`, včetně
poměrného rozpočítání výtěžku podle podílu). Slepičky/vejce (`Hen`,
`FeedLogEntry`, `Delivery`) zůstávají úplně beze změny — tohle je čistě
přídavek, ne přepis.

**Kdo dělá co (viz `config.ANIMAL_PRODUCTS` / `MEAT_SHARE_SPECIES`):**
koza a kráva dávají průběžně mléko (`Animal`) *a* obě jdou zároveň nabídnout
jako sdílený chov na maso (`MeatShare`). Ovce záměrně **nemá** žádný
průběžný produkt — v appce je jen na maso. Vlna byla z appky odebraná
schválně (bylo by potřeba samostatné zpracování - stříhání, praní,
spřádání - viz "co appka neřeší" níž), ne přehlédnutím.

## Proč dvě oddělené soustavy, ne jedna obecná

- **`Animal`**: stejný model jako slepička — jedno zvíře, jeden odběratel,
  denní krmné gesto, týdenní dodávka. Žádná porážka, zvíře žije dál.
- **`MeatShare`**: jedno zvíře na maso reálně stačí na desítky lidí, takže
  to nejde napasovat na "1 zvíře = 1 odběratel". Víc lidí se skládá na
  jedno konkrétní zvíře (real-world model "cow-share" — v některých zemích
  se používá zrovna proto, že prodej masa/syrového mléka přímo ze dvora má
  přísnější pravidla než prodej podílu na živém zvířeti). Po zpracování se
  reálný výtěžek rozdělí přesně podle podílu.

**Kůže** (`MeatShare.includes_hide`) je záměrně u masa, ne u mléka —
je to vždycky vedlejší produkt porážky, ne něco, co jde získat průběžně.

## Co appka poctivě NEřeší (a nemůže)

Stejná logika jako `LOGISTICS.md` u slepiček — jen tady je regulační
zátěž o dost vyšší a liší se produkt od produktu:

- **Mléko** — syrové mléko "ze dvora" má vlastní, přísnější pravidla než
  vejce (jiné požadavky na chlazení, značení, množstevní limity). Nejde to
  odbýt stejnou "vejce ze dvora" logikou.
- **Maso** — potřebuje schválená jatka, veterinární kontrolu, chladicí
  řetězec. Výrazně větší regulační krok než cokoliv jiného v appce.
- **Kůže** — po porážce potřebuje týdny až měsíce činění (tanning), než z
  ní je použitelný materiál — appka nijak nesleduje tenhle proces, jen
  zaznamená nárok ("tvůj podíl zahrnuje i kůži").
- **Vlna** — jediná z těchhle čtyř, co není potravina — jiný řetězec
  (střih, praní, spřádání), ne food-safety otázka, ale appka ani tohle
  zpracování nesleduje, jen objednávku a doručení.
- **Skuteční chovatelé** — farmy v `seed.py` jsou pořád vymyšlené (stejný
  disclaimer jako u slepiček). Žádná dohoda s žádným skutečným chovatelem
  neexistuje.
- **Nic z tohohle není právní rada.** "Cow-share" model výše je popis
  reálně existujícího vzoru, ne tvrzení, že takhle to jde provozovat v ČR
  bez dalšího ověření — to chce skutečnou konzultaci, ne kód.

## Co je hotové a odzkoušené

- `GET /animals/available-products` — seznam druh×produkt kombinací
  (`config.ANIMAL_PRODUCTS` — přidat novou kombinaci = přidat řádek, ne
  psát nový kód).
- `POST /animals`, `GET/PATCH/DELETE /animals/{id}`, `.../wallet`,
  `.../product-log`, `.../deliveries` — zrcadlí `routers/hens.py`.
- Kapacita na farmu **po jednotlivé kombinaci druh+produkt**
  (`FarmAnimalOffering`), ne sdílená se slepičkami — kdyby jedna farma
  nabízela třeba kozí i kravské mléko zároveň, každé má svůj vlastní strop.
- `GET/POST /meat-shares`, `POST /meat-shares/{id}/contribute` — koupě
  podílu skutečně strhne platbu (stejný mock/Stripe vzor jako peněženka u
  slepiček), odmítne přeplnění, odmítne příspěvek do už uzavřeného chovu.
- `DELETE /meat-shares/{id}/contribution` — zrušení vlastního podílu vrátí
  peníze (skutečný refund přes stejného payment providera, ne jen smazání
  záznamu) a uvolní místo pro někoho jiného, pokud tím chov přestal být
  plný. Jde to jen dokud chov ještě bere příspěvky (`open`/`full`) — jakmile
  farma zvíře reálně pošle na zpracování, appka refundovat přestane
  nabízet, protože to už by neodpovídalo realitě.
- `POST /admin/meat-shares` (založení), `POST /admin/meat-shares/{id}/mark-ready`
  (zápis skutečného výtěžku, rozpočítání a notifikace každému
  přispěvateli podle jeho podílu — ověřeno testem na přesných číslech, ne
  jen že "nespadne").
- Denní tik (`/admin/run-tick` i skutečný scheduler) běží pro zvířata
  stejně jako pro slepičky, ve stejném volání.
- `POST /animals/{id}/wallet/topup` (+ `.../setup-intent`, `.../topups`,
  `app/routers/animal_wallet.py`) — `Animal` má teď vlastní platební tok,
  stejný mock/Stripe vzor a stejné auto-pauza/obnovení chování při
  neúspěšné platbě jako slepičky (`routers/wallet.py`). Vlastní
  `setup-intent` endpoint navíc (ne jen sdílení toho hesního) — účet jen
  se zvířaty, bez jediné slepičky, by jinak neměl žádné `hen_id`, přes
  které by se ke kartě vůbec dostal.

## Co je poctivě nehotové

- **`app/webapp/index.html` (skutečná appka) nemá UI pro platbu za
  zvíře** — `animalsManageHtml()` umí jméno/pauzu/částku, ale žádnou
  sekci "Platba"/"Dobít peněženku" jako slepička v Nastavení
  (`renderPaymentSection()`, viz výš) — ta je zatím napevno navázaná jen
  na aktivní slepičku. Backend (viz výš) je hotový a otestovaný, jde
  zavolat z `/docs` nebo přímo z API - jen appka to zatím nenabízí
  klikací cestou.
- Žádné odznaky/doplňky/grafika pro kozy/ovce/krávy — jen backend.
