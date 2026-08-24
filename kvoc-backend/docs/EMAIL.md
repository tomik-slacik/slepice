# Napojení skutečných e-mailů

**Aktuální stav:** `app/integrations/email.py` obsahuje skutečnou, funkční
implementaci přes obyčejné SMTP (`SMTPEmailProvider`) — funguje s jakýmkoliv
SMTP účtem (např. Gmail + heslo aplikace), ne jen s jedním konkrétním
placeným providerem. **Nikdy ale neposlala e-mail ze skutečného účtu** —
nastavení SMTP přihlašovacích údajů je na tobě. Výchozí a bezpečný stav
zůstává `ConsoleEmailProvider` (`KVOC_EMAIL_PROVIDER=console`, výchozí
hodnota) — appka funguje kompletně i bez e-mailu, jen ho vypisuje do
konzole místo posílání.

## Co appka teď posílá (nebo by posílala se skutečným SMTP)

- **Uvítací e-mail** po registraci.
- **Odkaz na obnovení hesla** (`POST /auth/forgot-password`) — platí
  30 minut (`config.PASSWORD_RESET_EXPIRE_MINUTES`), jednorázový.

## Jak to doopravdy vyzkoušet (na příkladu Gmailu)

1. Na svém Google účtu zapni dvoufázové ověření (nutná podmínka pro heslo
   aplikace) a vytvoř si **heslo aplikace**:
   [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Spusť backend s:
   ```bash
   set KVOC_EMAIL_PROVIDER=smtp
   set KVOC_SMTP_HOST=smtp.gmail.com
   set KVOC_SMTP_PORT=587
   set KVOC_SMTP_USERNAME=tvuj-email@gmail.com
   set KVOC_SMTP_PASSWORD=heslo-aplikace-bez-mezer
   set KVOC_EMAIL_FROM=Kvoč <tvuj-email@gmail.com>
   python run.py
   ```
3. Zaregistruj si testovací účet — uvítací e-mail by měl doopravdy dorazit.

Gmail SMTP má nízké denní limity (stovky zpráv) — v pořádku pro rozjezd,
ne pro appku se skutečně velkým počtem uživatelů. Až na to dojde, vyměň za
dedikovanou transakční e-mailovou službu (Postmark, SendGrid, Amazon SES) —
`SMTPEmailProvider` funguje i s nimi, většina nabízí SMTP přístup vedle
vlastního API.

## Co je za tebou, co za mnou

- **Za mnou:** kompletní kód — provider, uvítací e-mail, celý tok
  zapomenutého hesla (žádost → token s expirací → e-mail → nastavení
  nového hesla), testy.
- **Za tebou:** e-mailový účet/SMTP přístup — reálné pověření, které jsem
  neměl a neměl bych zakládat za tebe.
