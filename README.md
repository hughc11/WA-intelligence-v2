# West Africa Intelligence Desk

A shareable, mobile-friendly political-risk learning dashboard that gathers West Africa news each morning and publishes a source-linked ten-point briefing.

## Included features

- Ten ranked daily developments covering politics, economics, security, society and climate.
- A concise “why it matters” note for every story.
- Country attention signals and a daily topic mix.
- An analyst overview, watchlist and study question.
- Duplicate-story, publisher-concentration and country-concentration controls.
- Original publisher links, publication times and confidence labels.
- A dated archive of successful editions.
- A visible ten-item demonstration edition, so the site is never blank before setup.

## Publish it free with GitHub Pages

1. Unzip the download.
2. Create a new **public GitHub repository**.
3. Upload the contents of the `west-africa-briefing` folder, preserving `.github`, `data` and `scripts`.
4. In **Settings → Actions → General**, ensure workflow permissions allow **Read and write permissions**.
5. In **Settings → Pages**, choose **Deploy from a branch**, then `main` and `/ (root)`.
6. Open **Actions → Update Daily Brief → Run workflow**.
7. Wait for a green tick, then refresh the Pages website.

The workflow runs daily at 06:17 UTC, which is 07:17 in the UK during British Summer Time.

## Optional AI analysis

The app works without an AI key using source text. To enable more polished synthesis, add an Actions repository secret named `OPENAI_API_KEY` under **Settings → Secrets and variables → Actions**. API usage may cost money and is separate from a ChatGPT subscription.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python scripts/update_briefing.py
python -m http.server 8000
```

Then open `http://localhost:8000`. Opening `index.html` directly can prevent the browser from loading the JSON file, so use the local server command.

## Code Sentinel safeguards

- No API keys are exposed in browser files.
- User-visible feed content is escaped before rendering.
- URLs are restricted to HTTP or HTTPS.
- Network calls use timeouts.
- A failed update does not overwrite the last successful briefing.
- Every development keeps its source link.
- Attention scores are explicitly descriptive, not forecasts of coups, conflict or investment outcomes.

## Limitations

RSS search can omit paywalled, local-language or poorly indexed reporting. Automated categorisation and summaries can misread context. This is an educational current-affairs tool, not verified intelligence, financial advice or a substitute for reading primary sources.
