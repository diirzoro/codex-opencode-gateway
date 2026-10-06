# Live preview style and pricing verification

Date: 2026-10-05. Reference: `http://127.0.0.1:8765/`. Current Codex preview: `http://127.0.0.1:8766/`.

Fresh comparison verified that maintained `index.html`, `styles.css`, and `app.js` match OpenCode byte for byte. The only remaining frontend `enhancements.js` difference is Codex's profile-edit DOM fix. The newer theme, card styles, header/sidebar, gradients, shadows, professional control panel and price renderer are present in Codex.

The live reference and current previews were inspected in the in-app browser. Pricing cards match in text and computed styles: $2/30 days, $3/60 days, $5/90 days; 20px corners and matching backgrounds/shadows. Feature cards have matching 18px corners and shadows; both fixed headers measure 68.8px at the inspected viewport. Public plan catalogs agree. Screenshot evidence is saved outside the project in `.audit/reference-pricing-8765.jpg` and `.audit/current-pricing-8766.jpg`.

The old 8766 preview was not running during the first check. It was started against the current Codex source using a new isolated local preview database; existing databases and user workspaces were preserved. Test users and the standard plan catalog are confined to the local test preview. The reference project was not modified.

A pricing-test cleanup bug was found in the separate 8768 test database: a test could leave its temporary $7.77 price behind. The test now restores the original price of the exact edited plan in a `finally` block, independent of sorting or assertion failures. Both focused headed Chromium pricing tests passed against a fresh isolated 8769 test server. Neither the reference catalog nor the user-facing 8766 catalog was modified by those tests.

No VPS access, deployment or Git push was performed.
