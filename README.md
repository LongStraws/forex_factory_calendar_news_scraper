# Forex Factory News Event Scraper
This project is a Python-based web scraper designed to retrieve news events for the current month from Forex Factory. It utilizes the Selenium library to automate the process of collecting data from the Forex Factory page. Here, I provide a brief overview of the project's structure and how to use it.

## Project Structure
The project consists of several Python files and a configuration file:

***scraper.py***: This is the main script responsible for scraping data from the Forex Factory calendar page. It uses Selenium to interact with the website, applies calendar filters, scrolls through the page to load all events, and extracts relevant data.

***utils.py***: This file contains utility functions for reading JSON data and processing text to extract relevant information from the scraped data.

***config.py***: Here, you can configure constants related to allowed HTML element types, excluded element types, impact color mapping, allowed currency codes, allowed impact colors, calendar filter impact levels, and event types. These configurations help filter and categorize the scraped data.

## How to Use
Follow these steps to use the Forex Factory News Event Scraper:
Ensure you have Python installed on your system.
Install the necessary Python libraries by running the following command:

`python3 -m pip install -r requirements.txt`

## Webdriver Installation:
The script uses the Chrome WebDriver to interact with the website. Make sure you have Google Chrome installed.
If you don't have the Chrome WebDriver installed, the script will attempt to install it using webdriver_manager. However, it's recommended to install it manually for better control.

## Running the Scraper:
Execute the scraper.py script to initiate the scraping process, using the command:

`python3 scraper.py`

It will launch a Chrome browser, navigate to the Forex Factory calendar page for the current month, and collect data. The scraped data will be reformatted and saved as CSV files in the "news" directory. Output is split per currency+event using the format "CURRENCY_EVENT_MONTH_YEAR.csv".

## Calendar Filters (UI)
The scraper applies the Forex Factory calendar filters before scrolling. Configure these in `config.py`:

- `ALLOWED_CURRENCY_CODES`: Currency checkboxes to enable.
- `ALLOWED_IMPACT_LEVELS`: Impact checkboxes (`high`, `medium`, `low`, `non-economic`).
- `ALLOWED_EVENT_TYPES`: Event type labels (e.g., `Growth`, `Inflation`).

## Date Range (CLI)
You can scrape a historical range using year-month args (YYYY-MM). This uses the calendar range parameter per month.

```bash
python3 scraper.py --start 2024-01 --end 2026-04
```

If `--start` or `--end` is provided, the script ignores `--months` and iterates month-by-month from `--start` to `--end` (inclusive). The default start is `2024-01` and the default end is the current month.


### Notes
This scraper is designed for educational and informational purposes. Ensure you comply with the terms of use and policies of Forex Factory when using this tool. Keep in mind that web scraping may be subject to legal and ethical considerations. 
Always respect the website's terms of service and robots.txt file.
It's a good practice to schedule the scraper to run periodically if you need updated data regularly.

**Disclaimer**: The accuracy and functionality of this scraper may change over time due to updates on the Forex Factory website. Be prepared to make adjustments if necessary.

**Please use this tool responsibly and in accordance with applicable laws and regulations.**
