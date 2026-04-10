# AI_README

Quick context for AI assistants working on this repo.

## What this project does
Scrapes the Forex Factory economic calendar for a target month, normalizes rows, filters by currency and impact, converts times to a target timezone, and writes a CSV file under `news/`.

## Key entry points
- `scraper.py`: Main CLI. Uses Selenium + ChromeDriver to load the calendar, apply UI filters, scroll, parse rows, and save CSV.
- `utils.py`: Data cleanup, date parsing, timezone conversion, filtering, and CSV writing.
- `config.py`: Parsing mappings and filters (allowed currencies/impacts) plus target timezone.
- `simple_scrape.py`: Minimal, older scrape example (no CSV output).

## How it works (high level)
- `scraper.py` opens `https://www.forexfactory.com/calendar?month=...`, applies UI filters from `config.py`, scrolls to load all rows, parses table cells using class mappings in `config.py`, and collects row dictionaries.
- `utils.reformat_data` fills in date/time continuity rows, extracts day/date from text, converts timezones, and filters rows by currency/impact.
- `utils.save_csv` writes one CSV per currency+event to `news/{CURRENCY}_{EVENT}_{Month}_{Year}.csv`.

## Running
Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Run the scraper (default is this month):

```bash
python3 scraper.py
```

Scrape a historical range (YYYY-MM):

```bash
python3 scraper.py --start 2024-01 --end 2026-04
```

Scrape specific months:

```bash
python3 scraper.py --months this next
python3 scraper.py --months january
```

## Configuration
- `config.ALLOWED_ELEMENT_TYPES`: Maps CSS classes to semantic fields.
- `config.ICON_COLOR_MAP`: Maps impact icon classes to colors.
- `config.ALLOWED_CURRENCY_CODES`: Filters to currencies of interest (UI filter + row filter).
- `config.ALLOWED_IMPACT_COLORS`: Filters by impact severity during row filtering.
- `config.ALLOWED_IMPACT_LEVELS`: UI filter for impact (`high`, `medium`, `low`, `non-economic`).
- `config.ALLOWED_EVENT_TYPES`: UI filter event type labels.
- `config.TARGET_TIMEZONE`: Output timezone (set to `None` to keep source time).

## Output
- CSV files are written to `news/` as `CURRENCY_EVENT_Month_Year.csv`.
- Columns: day, date, time, currency, impact, event, detail, actual, forecast, previous (plus any row fields captured).

## Notes and gotchas
- Selenium launches Chrome; `webdriver_manager` installs a compatible driver if needed.
- The scraper sets `config.SCRAPER_TIMEZONE` from the browser, then converts times to `TARGET_TIMEZONE`.
- Forex Factory page structure changes can break class-based parsing.
- `simple_scrape.py` is not used by `scraper.py` and does not save output.
