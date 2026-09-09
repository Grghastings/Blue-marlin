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

The dashboard reads from `data.js`. Replace or edit the records there and commit the change. The site will update automatically after GitHub Pages redeploys.

## Files

- `index.html` — dashboard structure
- `styles.css` — responsive styling
- `app.js` — filters, sorting, KPI calculations, and charts
- `data.js` — current tracker data

## Data scope

Current snapshot: September 9, 2026. Source URLs are retained on each record.
