# Clearance

Border-rejection risk for Indian food exports. A static website (`site/`) plus a data job (`pipeline/`) that refreshes the data every day and republishes the site on GitHub Pages. Free to run.

## Put it online (about 15 minutes, one time)

1. Make a free account at github.com.
2. Click **New repository**. Name it `clearance`. Choose **Public**. Create it.
3. Click **uploading an existing file**. Drag in everything from this folder, including the `site`, `pipeline`, `config` and `data` folders. Commit.
4. Check that `.github/workflows/update.yml` exists in the repository. Folders that start with a dot are sometimes skipped when you drag them in. If it is missing: **Add file > Create new file**, type `.github/workflows/update.yml` as the name, paste the text from `update-workflow.yml.txt`, and commit.
5. **Settings > Pages > Build and deployment > Source: GitHub Actions**.
6. Get a free FDA access key: open https://datadashboard.fda.gov/oii/api/index.htm and follow "request credentials". FDA emails you a key.
7. **Settings > Secrets and variables > Actions > New repository secret**. Add two: `FDA_API_USER` (the email you used) and `FDA_API_KEY` (the key). Without them, US data stays at the snapshot and the Sources tab says "Not set up".
8. **Actions** tab > **Update data and deploy** > **Run workflow**. After about 3 minutes the site is live. The address is shown under **Settings > Pages** (it looks like `https://YOURNAME.github.io/clearance/`).

After that it runs by itself every day at 08:00 India time. To use your own address, set **Custom domain** under **Settings > Pages**.

## Checking that it works

Open the **Sources** tab on the site. Each destination shows its latest record, when it was last checked, and a status: Updating, Update failed, or Not set up. If one says Update failed, copy the message under it and send it to Claude. Sites change their layout from time to time, and the downloader for that source needs a small fix. The site keeps showing the older data meanwhile.

The first run is the real test of the downloaders for the EU, UK, Australia and Japan, because they could not be run against the live sites while the code was written.

## Research paper

`paper/` holds the frozen data snapshot, analysis code and figures behind the research paper on this project, so every number in the paper can be reproduced. See `paper/README.md`. It is separate from the daily update.

## What is in here

- `site/` the website. `index.html` reads the JSON files in `site/data/`.
- `pipeline/` the downloaders (`fetch_*.py`), the product and reason sorting (`categorize.py`), and `build.py`.
- `config/` product list, legal limits, FDA import alerts, trade values, reported market actions (`events.json`), extra news feeds (`feeds.json`).
- `data/src/` every record downloaded so far, one file per source. Never delete these.
- `pipeline/tests/` self-tests that run before every update.

## Changing things

- **Product sorting:** edit the word lists in `pipeline/categorize.py`.
- **A new news feed:** add a line to `config/feeds.json`.
- **A market action you want pinned on the News tab:** add an entry to `config/events.json`.
- **Limits, trade values:** `config/limits.json`, `config/categories.json`. These change rarely and are updated by hand.
