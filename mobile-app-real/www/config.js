// This file only exists here (mobile-app-real/www/), not in
// kvoc-backend/app/webapp/ - see the comment above the <script src="config.js">
// tag in index.html for why.
//
// index.html now runs inside its own native app shell, not served BY the
// backend anymore, so relative API paths like "/auth/login" no longer
// point anywhere real - they'd try to hit this app's own bundled files.
// This one line is what fixes that: point it at your real, deployed
// backend (see ../../kvoc-backend/docs/DEPLOYMENT.md) once you have one.
//
// http://10.0.2.2:8000 below is the special address the Android emulator
// uses to reach "localhost" on the machine running the emulator - useful
// for testing against a backend you're running locally on this same
// computer, USELESS to anyone installing the app on a real phone. Replace
// it with your real https:// backend URL before sharing this app with
// anyone else.
window.KVOC_API_BASE = 'http://10.0.2.2:8000';
