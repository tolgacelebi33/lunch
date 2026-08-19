# Dagens lunch — GitHub-ready

## Upload
Upload **the contents of this folder** to the root of `tolgacelebi33/lunch`.
Do not upload the ZIP itself into the repository.

The repository root should contain:
- `index.html`
- `data/`
- `scripts/`
- `.github/`
- `README.md`

## First test
After committing the files:
1. Open **Actions**
2. Open **Test Glasets Hus source**
3. Click **Run workflow**
4. Wait for the run to finish
5. Open `data/glasets-hus-probe.json`

A successful result has `"ok": true` for `/lunch/`, `/nasta-vecka/`, or both.

The probe deliberately uses no secret/API key. It tests whether GitHub's runner can read the two official Glasets Hus pages directly.

## Safety
No menu is promoted to "today's lunch" merely because a page loads. The next parser step will validate week number and weekday before writing restaurant data.
