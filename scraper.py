import time
import argparse
import calendar
from datetime import datetime, timedelta
from config import ACTUAL_COLOR_MAP, ALLOWED_ELEMENT_TYPES, ICON_COLOR_MAP
from utils import save_csv
import config
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
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


def wait_for_calendar_table(driver, timeout=20):
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CLASS_NAME, "calendar__table"))
    )


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

    trigger_used = None
    try:
        filter_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.highlight.filters"))
        )
        filter_button.click()
        trigger_used = "a.highlight.filters"
    except TimeoutException:
        trigger_used = driver.execute_script(
            """
            const selectors = ['a.highlight.filters'];
            for (const selector of selectors) {
                const el = document.querySelector(selector);
                if (el) {
                    el.click();
                    return selector;
                }
            }
            return null;
            """
        )

    try:
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script(
                """
                const overlay = document.querySelector('.overlay--filters');
                if (!overlay) return false;
                const style = window.getComputedStyle(overlay);
                return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
                """
            )
        )
        print(f"[INFO] Calendar filter overlay opened via {trigger_used}.")
    except TimeoutException:
        print(
            f"[WARN] Calendar filter overlay not visible after trigger: {trigger_used}."
        )
        return

    if currencies:
        try:
            currency_labels = driver.execute_script(
                """
                const overlay = document.querySelector('.overlay--filters');
                if (!overlay) return [];
                const labels = overlay.querySelectorAll('.flexcontrols__cell--calendarcurrency .flexcontrols__label--checkbox label');
                return Array.from(labels).map((label) => ({
                    text: (label.textContent || '').trim(),
                    forId: label.getAttribute('for')
                }));
                """
            )
            print(f"[INFO] Currency labels found: {currency_labels}")
        except Exception as exc:
            print(f"[WARN] Failed to read currency labels: {exc}")

    try:
        storage_snapshot = driver.execute_script(
            """
            const entries = [];
            for (let i = 0; i < localStorage.length; i += 1) {
                const key = localStorage.key(i);
                if (key && /calendar|filter/i.test(key)) {
                    entries.push({ key, value: localStorage.getItem(key) });
                }
            }
            return entries;
            """
        )
        if storage_snapshot:
            print(f"[INFO] LocalStorage filter keys: {storage_snapshot}")
    except Exception as exc:
        print(f"[WARN] Failed to read localStorage: {exc}")

    result = driver.execute_script(
        """
        const currencies = arguments[0] || [];
        const impactLevels = arguments[1] || [];
        const eventTypes = arguments[2] || [];
        const overlay = document.querySelector('.overlay--filters');
        if (!overlay) {
            return { status: 'missing-overlay' };
        }

        const setCheckedByClick = (input, checked) => {
            if (!input) return;
            if (input.checked !== checked) {
                input.click();
            }
        };

        const setSectionByLabels = (sectionSelector, desiredLabels, labelSelector) => {
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

            const desiredIds = new Set();
            desiredLabels.forEach((label) => {
                const key = String(label || '').trim().toUpperCase();
                const inputId = labelMap.get(key);
                if (inputId) {
                    desiredIds.add(inputId);
                }
            });

            const inputs = section.querySelectorAll('input[type="checkbox"]');
            inputs.forEach((input) => {
                const shouldBeChecked = desiredIds.has(input.id);
                setCheckedByClick(input, shouldBeChecked);
            });

            return { found: true, applied: desiredIds.size };
        };

        const impactMap = {
            'high': 'impact_high_1',
            'medium': 'impact_medium_1',
            'low': 'impact_low_1',
            'non-economic': 'impact_holiday_1'
        };
        const impactCodeMap = {
            'high': 3,
            'medium': 2,
            'low': 1,
            'non-economic': 0
        };
        const impactSection = overlay.querySelector('.flexcontrols__cell--impacts');
        let impactsApplied = 0;
        const impactCodes = [];
        if (impactSection && impactLevels.length) {
            const desiredImpactIds = impactLevels
                .map((level) => impactMap[String(level || '').toLowerCase()])
                .filter(Boolean);
            const impactInputs = impactSection.querySelectorAll('input[type="checkbox"]');
            impactInputs.forEach((input) => {
                const shouldBeChecked = desiredImpactIds.includes(input.id);
                setCheckedByClick(input, shouldBeChecked);
            });
            impactsApplied = desiredImpactIds.length;
            impactLevels.forEach((level) => {
                const code = impactCodeMap[String(level || '').toLowerCase()];
                if (typeof code === 'number') {
                    impactCodes.push(code);
                }
            });
        }

        const parseCode = (inputId, prefix) => {
            if (!inputId || !prefix) return null;
            const match = inputId.match(new RegExp(`^${prefix}_(\\d+)_`));
            return match ? Number(match[1]) : null;
        };

        const currenciesResult = currencies.length
            ? setSectionByLabels('.flexcontrols__cell--calendarcurrency', currencies, '.flexcontrols__label--checkbox label')
            : { found: true, applied: 0 };

        const eventResult = eventTypes.length
            ? setSectionByLabels('.flexcontrols__cell--eventtypes', eventTypes, '.flexcontrols__label--checkbox label')
            : { found: true, applied: 0 };

        const currencyCodes = [];
        if (currencies.length) {
            const currencyLabels = overlay.querySelectorAll('.flexcontrols__cell--calendarcurrency .flexcontrols__label--checkbox label');
            currencyLabels.forEach((label) => {
                const text = (label.textContent || '').trim().toUpperCase();
                if (currencies.map((c) => String(c || '').trim().toUpperCase()).includes(text)) {
                    const inputId = label.getAttribute('for');
                    const code = parseCode(inputId, 'currency');
                    if (typeof code === 'number') {
                        currencyCodes.push(code);
                    }
                }
            });
        }

        const eventTypeCodes = [];
        if (eventTypes.length) {
            const eventLabels = overlay.querySelectorAll('.flexcontrols__cell--eventtypes .flexcontrols__label--checkbox label');
            eventLabels.forEach((label) => {
                const text = (label.textContent || '').trim().toUpperCase();
                if (eventTypes.map((c) => String(c || '').trim().toUpperCase()).includes(text)) {
                    const inputId = label.getAttribute('for');
                    const code = parseCode(inputId, 'event_type');
                    if (typeof code === 'number') {
                        eventTypeCodes.push(code);
                    }
                }
            });
        }

        return {
            status: 'ok',
            impactsApplied,
            impactCodes,
            currenciesApplied: currenciesResult.applied,
            currencyCodes,
            eventTypesApplied: eventResult.applied,
            eventTypeCodes,
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

    try:
        apply_button = driver.find_element(
            By.CSS_SELECTOR, ".overlay--filters .overlay__button--submit"
        )
        ActionChains(driver).move_to_element(apply_button).pause(0.2).click().perform()
        print("[INFO] Calendar filter apply action chain clicked.")
    except Exception as exc:
        print(f"[WARN] Calendar filter apply action chain failed: {exc}")

    try:
        apply_button = driver.find_element(
            By.CSS_SELECTOR, ".overlay--filters .overlay__button--submit"
        )
        ActionChains(driver).move_to_element(apply_button).click_and_hold().pause(
            0.2
        ).release().perform()
        print("[INFO] Calendar filter apply click-and-hold released.")
    except Exception as exc:
        print(f"[WARN] Calendar filter apply click-and-hold failed: {exc}")

    try:
        apply_button = driver.find_element(
            By.CSS_SELECTOR, ".overlay--filters .overlay__button--submit"
        )
        apply_button.send_keys(Keys.ENTER)
        apply_button.send_keys(Keys.SPACE)
        print("[INFO] Calendar filter apply keypress sent.")
    except Exception as exc:
        print(f"[WARN] Calendar filter apply keypress failed: {exc}")

    try:
        apply_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, ".overlay--filters .overlay__button--submit")
            )
        )
        apply_button.click()
        driver.execute_script("arguments[0].click();", apply_button)
        print("[INFO] Calendar filter apply clicked.")
    except TimeoutException:
        print("[WARN] Calendar filter apply button not clickable.")
    except Exception as exc:
        print(f"[WARN] Calendar filter apply click failed: {exc}")

    driver.execute_script(
        """
        const overlay = document.querySelector('.overlay--filters');
        if (!overlay) return;
        const applyBtn = overlay.querySelector('.overlay__button--submit');
        if (applyBtn) {
            const pointerInit = { bubbles: true, pointerId: 1, pointerType: 'mouse' };
            applyBtn.dispatchEvent(new PointerEvent('pointerdown', pointerInit));
            applyBtn.dispatchEvent(new PointerEvent('pointerup', pointerInit));
            applyBtn.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
            applyBtn.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
            applyBtn.dispatchEvent(new MouseEvent('click', { bubbles: true }));
            if (typeof TouchEvent !== 'undefined') {
                const touchInit = { bubbles: true, cancelable: true };
                applyBtn.dispatchEvent(new TouchEvent('touchstart', touchInit));
                applyBtn.dispatchEvent(new TouchEvent('touchend', touchInit));
            }
        }
        const form = overlay.querySelector('form');
        if (form) {
            form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
            if (typeof form.submit === 'function') {
                form.submit();
            }
        }
        """
    )

    overlay_closed = False
    try:
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script(
                """
                const overlay = document.querySelector('.overlay--filters');
                if (!overlay) return true;
                const style = window.getComputedStyle(overlay);
                return style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0';
                """
            )
        )
        overlay_closed = True
    except TimeoutException:
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except Exception:
            pass
        print("[WARN] Calendar filter overlay did not close after applying.")
        try:
            driver.execute_script(
                """
                const overlay = document.querySelector('.overlay--filters');
                if (overlay) {
                    overlay.style.display = 'none';
                    overlay.style.visibility = 'hidden';
                    overlay.style.opacity = '0';
                }
                """
            )
            print("[INFO] Forced filter overlay closed.")
        except Exception as exc:
            print(f"[WARN] Failed to force-close overlay: {exc}")
        try:
            overlay_state = driver.execute_script(
                """
                const overlay = document.querySelector('.overlay--filters');
                if (!overlay) return null;
                const style = window.getComputedStyle(overlay);
                return {
                    className: overlay.className,
                    display: style.display,
                    visibility: style.visibility,
                    opacity: style.opacity,
                    hidden: overlay.hidden,
                    ariaHidden: overlay.getAttribute('aria-hidden')
                };
                """
            )
            print(f"[INFO] Overlay state after apply: {overlay_state}")
            component_state = driver.execute_script(
                """
                const statesRaw = window.calendarComponentStates || [];
                const states = Array.isArray(statesRaw) ? statesRaw : Object.values(statesRaw);
                const target = states.find((state) => state && state.settings) || states[1];
                if (!target) return null;
                const keys = Object.keys(target);
                const functionKeys = keys.filter((key) => typeof target[key] === 'function');
                return {
                    keys,
                    functionKeys,
                    settings: target.settings || null
                };
                """
            )
            print(f"[INFO] Calendar component state: {component_state}")
        except Exception as exc:
            print(f"[WARN] Failed to read overlay state: {exc}")


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

                elif "calendar__actual" in class_name:
                    color_elements = element.find_elements(By.TAG_NAME, "span")
                    print("Color Elements is: ", color_elements)
                    color = None
                    for impact in color_elements:
                        impact_class = impact.get_attribute("class")
                        color = ACTUAL_COLOR_MAP.get(impact_class)
                    row_data[f"{class_name_key}-Color"] = color if color else "neutral"
                    print("The color is: ", color)
                    text_content = (element.get_attribute("textContent") or "").strip()
                    span_texts = [
                        span.text.strip()
                        for span in element.find_elements(By.TAG_NAME, "span")
                        if span.text and span.text.strip()
                    ]
                    row_data[f"{class_name_key}"] = (
                        text_content or " ".join(span_texts).strip() or "empty"
                    )
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


def parse_year_month(value):
    try:
        parsed = datetime.strptime(value, "%Y-%m")
        return parsed.replace(day=1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}'. Use YYYY-MM (e.g., 2024-01)."
        ) from exc


def iter_months(start_dt, end_dt):
    current = start_dt.replace(day=1)
    end_dt = end_dt.replace(day=1)
    while current <= end_dt:
        yield current.year, current.month
        year = current.year + (current.month // 12)
        month = (current.month % 12) + 1
        current = current.replace(year=year, month=month)


def build_range_param(year, month):
    start_day = 1
    next_month = datetime(year, month, 1) + timedelta(days=32)
    last_day = (next_month.replace(day=1) - timedelta(days=1)).day
    month_abbr = calendar.month_abbr[month].lower()
    return f"{month_abbr}{start_day}.{year}-{month_abbr}{last_day}.{year}"


def build_filter_params():
    currency_map = {
        "AUD": 1,
        "CAD": 2,
        "CHF": 3,
        "CNY": 4,
        "EUR": 5,
        "GBP": 6,
        "JPY": 7,
        "NZD": 8,
        "USD": 9,
    }
    impact_map = {
        "high": 3,
        "medium": 2,
        "low": 1,
        "non-economic": 0,
    }

    currencies = [
        code.upper() for code in getattr(config, "ALLOWED_CURRENCY_CODES", [])
    ]
    impact_levels = [
        level.lower() for level in getattr(config, "ALLOWED_IMPACT_LEVELS", [])
    ]

    currency_codes = [currency_map[code] for code in currencies if code in currency_map]
    impact_codes = [impact_map[level] for level in impact_levels if level in impact_map]

    params = {}
    if currency_codes:
        params["currencies"] = ",".join(str(code) for code in currency_codes)
    if impact_codes:
        params["impacts"] = ",".join(str(code) for code in impact_codes)
    return params


def main():
    parser = argparse.ArgumentParser(description="Scrape Forex Factory calendar.")
    parser.add_argument("--months", nargs="+", help="Target months: e.g., this next")
    parser.add_argument(
        "--start",
        type=parse_year_month,
        help="Start month in YYYY-MM format (e.g., 2024-01)",
    )
    parser.add_argument(
        "--end",
        type=parse_year_month,
        help="End month in YYYY-MM format (defaults to current month)",
    )

    args = parser.parse_args()
    if args.start or args.end:
        start_dt = args.start or datetime(2024, 1, 1)
        end_dt = args.end or datetime.now().replace(day=1)
        if start_dt > end_dt:
            parser.error("--start must be earlier than or equal to --end")
        month_sequence = list(iter_months(start_dt, end_dt))
    else:
        month_params = args.months if args.months else ["this"]
        month_sequence = []
        for param in month_params:
            param = param.lower()
            if param == "this":
                now = datetime.now()
                month_sequence.append((now.year, now.month))
            elif param == "next":
                now = datetime.now()
                next_month = (now.month % 12) + 1
                year = now.year if now.month < 12 else now.year + 1
                month_sequence.append((year, next_month))
            else:
                try:
                    month_number = datetime.strptime(param.capitalize(), "%B").month
                except ValueError:
                    parser.error(f"Unknown month '{param}'. Use full month name.")
                month_sequence.append((datetime.now().year, month_number))

    for year, month in month_sequence:
        range_param = build_range_param(year, month)
        url = f"https://www.forexfactory.com/calendar?range={range_param}"
        print(f"\n[INFO] Navigating to {url}")

        driver = init_driver()
        driver.get(url)
        wait_for_calendar_table(driver)
        detected_tz = driver.execute_script(
            "return Intl.DateTimeFormat().resolvedOptions().timeZone"
        )
        print(f"[INFO] Browser timezone: {detected_tz}")
        config.SCRAPER_TIMEZONE = detected_tz
        scroll_to_end(driver)

        month_name = datetime(year, month, 1).strftime("%B")
        print(f"[INFO] Scraping data for {month_name} {year}")
        try:
            parse_table(driver, month_name, str(year))
        except Exception as e:
            print(f"[ERROR] Failed to scrape {month_name} {year}: {e}")

        driver.quit()  #  Kill the driver cleanly after each scrape
        time.sleep(3)


if __name__ == "__main__":
    start_time = time.perf_counter()
    main()
    end_time = time.perf_counter()
    print(f"Execution time: {end_time - start_time:.6f} seconds")
