import time
import argparse
from datetime import datetime
from config import ALLOWED_ELEMENT_TYPES, ICON_COLOR_MAP
from utils import save_csv
import config
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def init_driver(headless=True) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("window-size=1920x1080")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )

    print("Attempting to initialize WebDriver with ChromeDriverManager...")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    print("WebDriver initialized successfully using ChromeDriverManager.")
    return driver


def scroll_to_end(driver):
    previous_position = None
    while True:
        current_position = driver.execute_script("return window.pageYOffset;")
        driver.execute_script("window.scrollTo(0, window.pageYOffset + 500);")
        time.sleep(2)
        if current_position == previous_position:
            break
        previous_position = current_position


def apply_calendar_filters(driver):
    currencies = [
        code.upper() for code in getattr(config, "ALLOWED_CURRENCY_CODES", [])
    ]
    impact_levels = [
        level.lower() for level in getattr(config, "ALLOWED_IMPACT_LEVELS", [])
    ]
    event_types = [
        label.strip() for label in getattr(config, "ALLOWED_EVENT_TYPES", []) if label
    ]

    if not currencies and not impact_levels and not event_types:
        print("[INFO] No UI filters configured. Skipping calendar filter step.")
        return

    trigger_used = driver.execute_script(
        """
        const selectors = [
            'a.highlight.filters',
            '[data-calendar-filter]',
            '.calendar__filters',
            '.calendar__filter',
            '.calendar__icon--filters',
            '.calendar__button--filters',
            '.calendar__button--filter'
        ];
        for (const selector of selectors) {
            const el = document.querySelector(selector);
            if (el) {
                el.click();
                return selector;
            }
        }

        const textCandidates = Array.from(document.querySelectorAll('a,button,span')).filter(
            (el) => /filter/i.test(el.textContent || '')
        );
        if (textCandidates.length) {
            textCandidates[0].click();
            return 'text-match';
        }

        return null;
        """
    )

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".overlay--filters"))
        )
    except TimeoutException:
        print(
            f"[WARN] Calendar filter overlay not found after trigger: {trigger_used}. Skipping UI filters."
        )
        return

    result = driver.execute_script(
        """
        const currencies = arguments[0] || [];
        const impactLevels = arguments[1] || [];
        const eventTypes = arguments[2] || [];
        const overlay = document.querySelector('.overlay--filters');
        if (!overlay) {
            return { status: 'missing-overlay' };
        }

        const setChecked = (input, checked) => {
            if (!input) return;
            if (input.checked !== checked) {
                input.checked = checked;
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
        };

        const setSection = (sectionSelector, desiredLabels, labelSelector) => {
            const section = overlay.querySelector(sectionSelector);
            if (!section) return { found: false, applied: 0 };

            const items = section.querySelectorAll(labelSelector);
            const labelMap = new Map();
            items.forEach((label) => {
                const text = (label.textContent || '').trim();
                const forId = label.getAttribute('for');
                if (text && forId) {
                    labelMap.set(text.toUpperCase(), forId);
                }
            });

            const inputs = section.querySelectorAll('input[type="checkbox"]');
            inputs.forEach((input) => setChecked(input, false));

            let applied = 0;
            desiredLabels.forEach((label) => {
                const key = String(label || '').trim().toUpperCase();
                const inputId = labelMap.get(key);
                if (inputId) {
                    setChecked(document.getElementById(inputId), true);
                    applied += 1;
                }  
            });

            return { found: true, applied };
        };

        const impactMap = {
            'high': 'impact_high_1',
            'medium': 'impact_medium_1',
            'low': 'impact_low_1',
            'non-economic': 'impact_holiday_1'
        };
        const impactSection = overlay.querySelector('.flexcontrols__cell--impacts');
        let impactsApplied = 0;
        if (impactSection && impactLevels.length) {
            const impactInputs = impactSection.querySelectorAll('input[type="checkbox"]');
            impactInputs.forEach((input) => setChecked(input, false));
            impactLevels.forEach((level) => {
                const inputId = impactMap[String(level || '').toLowerCase()];
                if (inputId) {
                    setChecked(document.getElementById(inputId), true);
                    impactsApplied += 1;
                }
            });
        }

        const currenciesResult = currencies.length
            ? setSection('.flexcontrols__cell--calendarcurrency', currencies, '.flexcontrols__label--checkbox label')
            : { found: true, applied: 0 };

        const eventResult = eventTypes.length
            ? setSection('.flexcontrols__cell--eventtypes', eventTypes, '.flexcontrols__label--checkbox label')
            : { found: true, applied: 0 };

        const applyButton = overlay.querySelector('.overlay__button--submit');
        if (applyButton) {
            applyButton.click();
        }

        return {
            status: 'ok',
            impactsApplied,
            currenciesApplied: currenciesResult.applied,
            eventTypesApplied: eventResult.applied,
            currenciesFound: currenciesResult.found,
            eventTypesFound: eventResult.found
        };
        """,
        currencies,
        impact_levels,
        event_types,
    )

    if result.get("status") != "ok":
        print(f"[WARN] Calendar filter overlay not found: {result}")
        return

    if impact_levels:
        print(f"[INFO] UI impacts selected: {result.get('impactsApplied', 0)}")
    if currencies:
        print(f"[INFO] UI currencies selected: {result.get('currenciesApplied', 0)}")
    if event_types:
        print(f"[INFO] UI event types selected: {result.get('eventTypesApplied', 0)}")

    time.sleep(2)


def parse_table(driver, month, year):
    data = []
    table = driver.find_element(By.CLASS_NAME, "calendar__table")

    allowed_class_keys = sorted(ALLOWED_ELEMENT_TYPES.keys(), key=len, reverse=True)

    for row in table.find_elements(By.TAG_NAME, "tr"):
        row_data = {}
        event_id = row.get_attribute("data-event-id")

        for element in row.find_elements(By.TAG_NAME, "td"):
            class_name = element.get_attribute("class") or ""
            matched_class = next(
                (key for key in allowed_class_keys if key in class_name), None
            )

            if matched_class:
                class_name_key = ALLOWED_ELEMENT_TYPES.get(matched_class, "cell")

                if "calendar__impact" in class_name:
                    impact_elements = element.find_elements(By.TAG_NAME, "span")
                    color = None
                    for impact in impact_elements:
                        impact_class = impact.get_attribute("class")
                        color = ICON_COLOR_MAP.get(impact_class)
                    row_data[f"{class_name_key}"] = color if color else "impact"

                elif "calendar__detail" in class_name and event_id:
                    detail_url = f"https://www.forexfactory.com/calendar?month={month}#detail={event_id}"
                    row_data[f"{class_name_key}"] = detail_url

                elif element.text:
                    row_data[f"{class_name_key}"] = element.text
                else:
                    text_content = (element.get_attribute("textContent") or "").strip()
                    span_texts = [
                        span.text.strip()
                        for span in element.find_elements(By.TAG_NAME, "span")
                        if span.text and span.text.strip()
                    ]
                    row_data[f"{class_name_key}"] = (
                        text_content or " ".join(span_texts).strip() or "empty"
                    )

        if row_data:
            data.append(row_data)

    save_csv(data, month, year)

    return data, month


def get_target_month(arg_month=None):
    now = datetime.now()
    month = arg_month if arg_month else now.strftime("%B")
    year = now.strftime("%Y")
    return month, year


def main():
    parser = argparse.ArgumentParser(description="Scrape Forex Factory calendar.")
    parser.add_argument("--months", nargs="+", help="Target months: e.g., this next")

    args = parser.parse_args()
    month_params = args.months if args.months else ["this"]

    for param in month_params:
        param = param.lower()
        url = f"https://www.forexfactory.com/calendar?month={param}"
        print(f"\n[INFO] Navigating to {url}")

        driver = init_driver()
        driver.get(url)
        detected_tz = driver.execute_script(
            "return Intl.DateTimeFormat().resolvedOptions().timeZone"
        )
        print(f"[INFO] Browser timezone: {detected_tz}")
        config.SCRAPER_TIMEZONE = detected_tz
        apply_calendar_filters(driver)
        scroll_to_end(driver)

        # Determine readable month name and year
        if param == "this":
            now = datetime.now()
            month = now.strftime("%B")
            year = now.year
        elif param == "next":
            now = datetime.now()
            next_month = (now.month % 12) + 1
            year = now.year if now.month < 12 else now.year + 1
            month = datetime(year, next_month, 1).strftime("%B")
        else:
            month = param.capitalize()
            year = datetime.now().year

        print(f"[INFO] Scraping data for {month} {year}")
        try:
            parse_table(driver, month, str(year))
        except Exception as e:
            print(f"[ERROR] Failed to scrape {param} ({month} {year}): {e}")

        driver.quit()  #  Kill the driver cleanly after each scrape
        time.sleep(3)


if __name__ == "__main__":
    start_time = time.perf_counter()
    main()
    end_time = time.perf_counter()
    print(f"Execution time: {end_time - start_time:.6f} seconds")
