# 2026 State Assistance Tracker

A no-build, static dashboard for 2026 U.S. Department of State grants, cooperative agreements, and pending NOFOs relevant to Lexpat business development.

## GitHub Pages deployment

1. Create a new GitHub repository (for example `state-assistance-dashboard`).
2. Upload all files in this folder to the repository root.
3. In GitHub, open **Settings → Pages**.
4. Under **Build and deployment**, select **Deploy from a branch**.
5. Choose the `main` branch and `/ (root)` folder, then click **Save**.
6. GitHub will publish the dashboard at your repository's Pages URL.

No npm, build tooling, or server is required.

## Updating the data

The dashboard reads from `data.js`. A GitHub Actions workflow refreshes it daily and can also be run manually from **Actions → Daily dashboard update → Run workflow**.

The updater uses official public sources:

- Grants.gov refreshes the status, dates, ceiling, instrument, and other details for each tracked funding opportunity.
- USAspending.gov refreshes verified awards by exact federal award ID, including the current obligated amount and official recipient name.

The matching is intentionally conservative. A Grants.gov opportunity number is not necessarily the same as the eventual federal award ID, so the updater does not guess recipients. When a pending opportunity is awarded, add its USAspending award ID as `usaSpendingAwardId` on the record; the next run will verify and refresh it. No API keys or repository secrets are required.

## Files

- `index.html` — dashboard structure
- `styles.css` — responsive styling
- `app.js` — filters, sorting, KPI calculations, and charts
- `data.js` — current tracker data

## Data scope

The date shown in the dashboard header is written after each successful refresh. Source URLs are replaced with the corresponding official Grants.gov or USAspending.gov record when available.
