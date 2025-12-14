from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import random
import json
import os


BASE_URL = "https://www.usnews.com/education/k12/elementary-schools/texas"
START_PAGE = 1  # 例如从 200 开始
MAX_PAGES = 661


OUT_DEBUG_JSONL = "debug_raw_card_text.jsonl"


def build_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.page_load_strategy = "eager"

    prefs = {
        "profile.managed_default_content_settings.images": 2,
    }
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver


def write_jsonl_line(fp, obj):
    # 一行一个 JSON 对象
    fp.write(json.dumps(obj, ensure_ascii=False) + "\n")


def extract_schools_from_soup(soup, page_number, debug_fp=None):
    """
    从页面 soup 中提取学校信息；
    同时把每张卡片的原始文本（raw_text_list）直接写入 debug JSONL（如果提供 debug_fp）。
    """
    results_section = soup.find(id="results") or soup
    schools = []

    for a in results_section.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)

        # 过滤
        if (
            "/education/k12/texas/" in href
            and "/districts/" not in href
            and text
            and len(text) > 3
            and text != "Read More"
        ):
            # 往上爬几层，找卡片容器
            card = a
            for _ in range(4):
                if card.parent:
                    card = card.parent
                else:
                    break

            card_texts = list(card.stripped_strings)

            # debug：边抓边写，不在内存累计
            if debug_fp is not None:
                write_jsonl_line(
                    debug_fp,
                    {
                        "page": page_number,
                        "school_name": text,
                        "href": href,
                        "raw_text_list": card_texts,
                    },
                )

            # 1) Rank
            rank_text = None
            rank = None
            for el in card.find_all(string=True):
                s = el.strip()
                if s.startswith("#") and "Texas Elementary Schools" in s:
                    rank_text = s
                    break
            if rank_text:
                try:
                    rank = int(rank_text.split()[0].lstrip("#"))
                except Exception:
                    rank = None

            # 2) Location & District（从卡片文本里尽量推断）
            location = None
            district = None
            for t in card_texts:
                if location is None and "," in t and "Elementary Schools" not in t and "Ratio" not in t:
                    location = t
                if district is None and "Independent School District" in t:
                    district = t

            # 3) Grade Level, Enrollment, Student-Teacher Ratio
            grade_level = None
            enrollment = None
            st_ratio = None
            for i, t in enumerate(card_texts):
                if "Grade Level" in t and i + 1 < len(card_texts):
                    grade_level = card_texts[i + 1]
                elif "Enrollment" in t and i + 1 < len(card_texts):
                    enrollment = card_texts[i + 1]
                elif "Student-Teacher Ratio" in t and i + 1 < len(card_texts):
                    st_ratio = card_texts[i + 1]

            schools.append(
                {
                    "page": page_number,
                    "rank": rank,
                    "school_name": text,
                    "location": location,
                    "district": district,
                    "grade_level": grade_level,
                    "enrollment": enrollment,
                    "student_teacher_ratio": st_ratio,
                    "school_url": "https://www.usnews.com" + href,
                }
            )

    # 当前页内按 school_url 去重
    unique = {}
    for s in schools:
        key = s["school_url"]
        if key not in unique:
            unique[key] = s
    return list(unique.values())


def get_page_data(page_number, driver, debug_fp=None):
    url = f"{BASE_URL}?page={page_number}#results"
    print(f"--- [Headless] Opening page {page_number} -> {url}")

    try:
        driver.get(url)
        time.sleep(random.uniform(3, 5))

        if "Access Denied" in driver.title or "Just a moment" in driver.title:
            print(f"⚠️ Blocked on page {page_number} (Title: {driver.title})")
            return []

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.ID, "results"))
            )
        except Exception:
            print(f"   Wait timeout on page {page_number}.")

        soup = BeautifulSoup(driver.page_source, "html.parser")
        rows = extract_schools_from_soup(soup, page_number, debug_fp=debug_fp)

        print(f"--- Page {page_number}: extracted {len(rows)} rows")
        return rows

    except Exception as e:
        print(f"Error on page {page_number}: {e}")
        return []


def scrape_texas_elementary_schools():
    driver = build_driver()

    try:
        with open(OUT_DEBUG_JSONL, "a", encoding="utf-8") as debug_fp:
            for page in range(START_PAGE, MAX_PAGES + 1):
                _rows = get_page_data(page, driver, debug_fp=debug_fp)

                debug_fp.flush()
                print(f"Page {page}: debug lines written (see {OUT_DEBUG_JSONL}).")

                time.sleep(random.uniform(3, 5))
    finally:
        driver.quit()


if __name__ == "__main__":
    scrape_texas_elementary_schools()
