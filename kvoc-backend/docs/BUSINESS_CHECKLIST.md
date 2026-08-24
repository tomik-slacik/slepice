# Byznys a právní checklist

Tohle **není právní ani daňové poradenství** — je to seznam věcí, které
stojí za to probrat s účetním/advokátem dřív, než appka začne obsluhovat
skutečné lidi a skutečné peníze. Technická kostra v tomhle repozitáři může
být hotová dřív, než tahle stránka věci — to je normální, ale neznamená to,
že se dá přeskočit.

## 1. Právní forma podnikání

- [ ] **Živnostenské oprávnění** — nejpravděpodobněji volná živnost
      "Výroba, obchod a služby neuvedené v přílohách 1 až 3 živnostenského
      zákona" (běžná pro e-commerce/předplatné). Ověř na místně příslušném
      živnostenském úřadě, jestli konkrétní kombinace (prodej potravin +
      zprostředkování + appka) nevyžaduje víc.
- [ ] Zvážit **s.r.o. vs. OSVČ** — s.r.o. omezuje osobní ručení, dává větší
      důvěryhodnost při jednání s farmáři/platební bránou/App Store
      (organizační účet), ale nese vyšší administrativní náklady. Konzultuj
      s účetním podle očekávaného objemu.
- [ ] **Název "Kvoč"** — než se stane oficiálním jménem firmy nebo appky,
      zkontrolovat střet s existující ochrannou známkou (rejstřík ÚPV) a
      s dostupností domény.

## 2. Prodej vajec je regulovaná potravinářská činnost

- [ ] **Registrace u Státní veterinární správy** — prodej/distribuce vajec
      podléhá veterinárnímu dozoru. Zjisti přesný režim registrace podle
      toho, jestli appka vejce jen zprostředkovává (farmář zůstává
      prodejcem) nebo je appka sama prodejcem.
- [ ] **Značení vajec** — EU pravidla vyžadují kód na skořápce (kód země,
      chovu, metody chovu 0–3) a třídění podle hmotnosti/jakosti. Tohle
      typicky řeší farma, ale appka by měla vědět, že to kontroluje a umí
      to zákazníkovi vysvětlit (ostatně to appka slibuje jako výhodu —
      "víš, odkud vejce jsou").
- [ ] **Hygienické požadavky na přepravu/skladování** potravin při
      posledním rozvozu (teplota, obal).

## 3. Peníze

- [ ] **Právní forma peněženky** — poukázka na vlastní zboží vs. elektronické
      peníze podle zákona o platebním styku. Viz `PAYMENT_INTEGRATION.md`.
      Špatná klasifikace může znamenat, že appka bez licence provozuje
      činnost, která licenci vyžaduje.
- [ ] **Smlouva s platební bránou** — KYC proces (ověření identity
      podnikatele), obchodní podmínky brány, výše poplatků.
- [ ] **DPH** — sledovat obrat vůči limitu pro povinnou registraci k DPH;
      u potravin navíc zvážit sazbu DPH (u vajec bývá snížená sazba, ověřit
      aktuální sazbu u účetního).

## 4. Osobní údaje (GDPR)

- [ ] Appka sbírá jméno, adresu, případně platební údaje — to je osobní
      údaj podle GDPR. Potřeba: zásady ochrany osobních údajů (i pro App
      Store/Google Play, viz `APP_STORE_GUIDE.md`), právní titul pro
      zpracování, řešení žádostí o výmaz.
- [ ] Backend teď nemá autentizaci ani šifrování hesel (žádná hesla
      zatím neexistují) — než přibudou skuteční uživatelé, tohle je
      priorita č. 1 z hlediska zabezpečení, ne jen "nice to have".

## 5. Farmáři a logistika

- [ ] **Písemná smlouva s každou farmou** — cena za vejce, objem, co se
      stane, když farma nestihne dodat (sezónnost snášky v zimě — appka to
      řeší i technicky, viz `README.md` frontendu, ale smluvně to potřeba
      ošetřit taky).
- [ ] **Poslední míle** — appka funguje ekonomicky jen s dostatečnou
      hustotou zákazníků v jednom regionu. Pilot v jedné čtvrti/městě než
      cokoliv jiného.
- [ ] **Pojištění odpovědnosti** za škodu (typicky u potravinářského
      podnikání i u doručovací služby).

## 6. Obchodní podmínky

- [ ] Standardní e-commerce náležitosti: obchodní podmínky, reklamační
      řád, právo na odstoupení od smlouvy (u předplatného potravin platí
      specifické výjimky — ověřit).

## Doporučené pořadí

1. Živnost/s.r.o. (bod 1) — bez tohohle nejde nic dalšího podepsat.
2. Veterinární registrace (bod 2) — může trvat, začít brzy.
3. Smlouva s 1–2 farmami v jednom regionu (bod 5) — pilotuj v malém.
4. Právní posouzení peněženky (bod 3) — dřív, než appka vezme první
   skutečnou korunu.
5. GDPR + obchodní podmínky (body 4, 6) — souběžně s vývojem, ne až na
   konci.

Tohle přesně odpovídá tomu, co navrhoval i původní koncept appky: pilot
v jedné čtvrti s ruční logistikou, ověřit ochotu platit dřív, než se
investuje do zbytku. Technická kostra v tomhle repozitáři na to už je
připravená.
