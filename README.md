# Lexpat Opportunity Tracker

A no-build, static dashboard for open SAM.gov and World Bank procurement opportunities.

## GitHub Pages deployment

1. Create a new GitHub repository (for example `state-assistance-dashboard`).
2. Upload all files in this folder to the repository root.
3. In GitHub, open **Settings → Pages**.
4. Under **Build and deployment**, select **Deploy from a branch**.
5. Choose the `main` branch and `/ (root)` folder, then click **Save**.
6. GitHub will publish the dashboard at your repository's Pages URL.

No npm, build tooling, or server is required.

## Updating the data

The dashboard reads from `procurement.js`. A GitHub Actions workflow refreshes it daily and can also be run manually from **Actions → Daily dashboard update → Run workflow**.

The updater uses official procurement sources:

- SAM.gov supplies active federal contract opportunities posted within the last 90 days.
- World Bank's Procurement Notice dataset supplies current project procurement notices. Contract awards, procurement plans, and expired notices are excluded.

## SAM.gov API key

SAM.gov requires an API key. Add it to the repository as an Actions secret named exactly `SAM_API_KEY`:

1. Open **Settings → Secrets and variables → Actions**.
2. Select **New repository secret**.
3. Enter `SAM_API_KEY` as the name and paste the key as the value.
4. Save it, then run **Actions → Daily dashboard update → Run workflow**.

Never put the API key in a source file. If the secret is missing, the updater still refreshes World Bank and State assistance data and reports that SAM.gov is waiting for the secret.

## Files

- `index.html` — dashboard structure
- `styles.css` — responsive styling
- `app.js` — filters, sorting, KPI calculations, and charts
- `procurement.js` — generated SAM.gov and World Bank opportunities

## Data scope

The date shown in the dashboard header is written after each successful refresh. Every row links back to its official SAM.gov or World Bank procurement notice.
