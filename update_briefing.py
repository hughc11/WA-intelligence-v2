name: Update Daily Brief
on:
  schedule:
    - cron: '17 6 * * *'
  workflow_dispatch:
permissions:
  contents: write
jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip
      - run: pip install -r requirements.txt
      - name: Gather and summarise news
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          OPENAI_MODEL: gpt-5-mini
        run: python scripts/update_briefing.py
      - name: Commit updated briefing
        run: |
          git config user.name "west-africa-brief-bot"
          git config user.email "actions@users.noreply.github.com"
          git add data/briefing.json data/archive
          git diff --cached --quiet || git commit -m "Update daily West Africa brief"
          git push
