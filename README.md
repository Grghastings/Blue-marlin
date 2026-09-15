# Lexpat Opportunity Tracker

A no-build, static dashboard for open SAM.gov and World Bank procurement opportunities, plus 2026 U.S. Department of State assistance and awards.

## GitHub Pages deployment

1. Create a new GitHub repository (for example `state-assistance-dashboard`).
2. Upload all files in this folder to the repository root.
3. In GitHub, open **Settings → Pages**.
4. Under **Build and deployment**, select **Deploy from a branch**.
5. Choose the `main` branch and `/ (root)` folder, then click **Save**.
6. GitHub will publish the dashboard at your repository's Pages URL.

No npm, build tooling, or server is required.

## Updating the data

The dashboard reads from `data.js` and `procurement.js`. A GitHub Actions workflow refreshes both daily and can also be run manually from **Actions → Daily dashboard update → Run workflow**.

The updater uses official public sources:

- Grants.gov refreshes the status, dates, ceiling, instrument, and other details for each tracked funding opportunity.
- USAspending.gov refreshes verified awards by exact federal award ID, including the current obligated amount and official recipient name.
- World Bank's Procurement Notice dataset supplies current project procurement notices. Contract awards, procurement plans, and expired notices are excluded.
- SAM.gov supplies active federal contract opportunities posted within the last 90 days.

The matching is intentionally conservative. A Grants.gov opportunity number is not necessarily the same as the eventual federal award ID, so the updater does not guess recipients. When a pending opportunity is awarded, add its USAspending award ID as `usaSpendingAwardId` on the record; the next run will verify and refresh it.

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
- `data.js` — current tracker data
- `procurement.js` — generated SAM.gov and World Bank opportunities

## Data scope

The date shown in the dashboard header is written after each successful refresh. Source URLs are replaced with the corresponding official Grants.gov or USAspending.gov record when available.
