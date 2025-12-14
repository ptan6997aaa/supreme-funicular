from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time


BASE_URL = "https://www.usnews.com/education/k12/elementary-schools/texas"
EXPECTED_TOTAL = 6603  # target number of schools (for an early stop)


def extract_schools_from_soup(soup):
    """
    Extract school names from the rankings results section (#results).
    Rank is implied by order; we do NOT try to parse text like
    'in Texas Elementary Schools' because that isn't present on this page.
    """
    schools = []

    # Focus only on the actual rankings container
    results_section = soup.find(id="results")
    if not results_section:
        # Fallback: in case ID changes, still try whole page
        results_section = soup

    # School result links should point to individual K-12 profiles in Texas,
    # which use URLs like /education/k12/texas/<slug>-<id>
    for a in results_section.find_all(
        "a", href=lambda x: x and "/education/k12/texas/" in x
    ):
        name = a.get_text(strip=True)
        if not name:
            continue
        # Skip very short or obviously non-school labels if any
        if len(name) < 3:
            continue
        schools.append(name)

    return schools


def scrape_texas_elementary_schools():
    """
    Scrape all Texas elementary school rankings from US News using simple
    ?page=N pagination and DOM parsing of the #results section.
    """
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    # options.add_argument("--headless")

    driver = webdriver.Chrome(options=options)

    all_rows = []
    seen_names = set()

    try:
        current_page = 1
        max_pages = 500  # hard safety limit

        while current_page <= max_pages:
            url = f"{BASE_URL}?page={current_page}#results"
            print(f"\n=== Loading page {current_page}: {url}")
            driver.get(url)

            # Wait for the results section or at least some headings to appear
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "#results, h2, h3")
                    )
                )
            except Exception:
                print(f"Page {current_page}: timeout waiting for content, stopping.")
                break

            time.sleep(1)  # give JS a bit more time

            soup = BeautifulSoup(driver.page_source, "html.parser")
            page_school_names = extract_schools_from_soup(soup)

            # De-duplicate by school name across all pages
            unique_this_page = []
            for name in page_school_names:
                if name not in seen_names:
                    seen_names.add(name)
                    unique_this_page.append(name)

            print(
                f"Page {current_page}: found {len(page_school_names)} names, "
                f"{len(unique_this_page)} new unique."
            )

            if not unique_this_page:
                # If a page has no new schools, we are very likely past the end
                print(f"Page {current_page}: no new schools; assuming end of list.")
                break

            # Assign ranks purely by order across all pages
            for name in unique_this_page:
                rank = len(all_rows) + 1
                all_rows.append({"rank": rank, "school_name": name})

            if len(all_rows) >= EXPECTED_TOTAL:
                print(f"Reached {EXPECTED_TOTAL} schools; stopping early.")
                break

            current_page += 1
            time.sleep(0.5)  # be polite

        print(f"\nTotal unique schools collected: {len(all_rows)}")

        if not all_rows:
            print("No data extracted at all.")
            return pd.DataFrame()

        df = pd.DataFrame(all_rows)
        df["rank_int"] = pd.to_numeric(df["rank"], errors="coerce")
        df = df.sort_values("rank_int").reset_index(drop=True)
        df = df[["rank", "school_name"]]

        output_file = "texas_elementary_schools_rankings.csv"
        df.to_csv(output_file, index=False, encoding="utf-8")
        print(f"\nSaved {len(df)} schools to {output_file}")

        print("\nFirst 20 schools:")
        print(df.head(20).to_string(index=False))
        if len(df) > 20:
            print("\nLast 10 schools:")
            print(df.tail(10).to_string(index=False))

        return df

    finally:
        input("\nPress Enter to close the browser...")
        driver.quit()
        print("Browser closed")


if __name__ == "__main__":
    print("=" * 60)
    print("US News Texas Elementary Schools Scraper (Rankings Pagination)")
    print("=" * 60)
    df = scrape_texas_elementary_schools()
    if len(df) > 0:
        print("\n" + "=" * 60)
        print(f"✓ Extraction complete! {len(df)} schools saved to CSV")
        print("=" * 60)
    else:
        print("\n⚠ No data was extracted. Please check the logs above.")
