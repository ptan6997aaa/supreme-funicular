from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time

BASE_URL = "https://www.usnews.com/education/k12/elementary-schools/texas"
EXPECTED_TOTAL = 6603

def extract_schools_from_soup(soup):
    results_section = soup.find(id="results")
    if not results_section:
        results_section = soup

    schools = []
    # 增加容错：有时候 US News 的结构会微调
    links = results_section.find_all("a", href=True)
    
    for a in links:
        href = a['href']
        # 只要链接里包含特定结构，就认为是学校链接
        if "/education/k12/texas/" in href:
            name = a.get_text(strip=True)
            if not name or len(name) < 3:
                continue
            schools.append(name)
    return schools

def get_page_data(page_number):
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    
    # --- 关键修改 1: 页面加载策略设为 'eager' ---
    # 只要 DOM (HTML) 加载完就返回，不等图片和广告脚本
    options.page_load_strategy = 'eager' 
    
    # --- 关键修改 2: 禁用图片和不必要的组件 ---
    # 这能极大提升速度，并且让很多基于图片的广告直接挂掉
    prefs = {
        "profile.managed_default_content_settings.images": 2, # 禁止加载图片
        "profile.default_content_setting_values.notifications": 2 # 禁止弹窗通知
    }
    options.add_experimental_option("prefs", prefs)
    
    # 移除 uBlock 相关代码，因为不稳定
    
    driver = webdriver.Chrome(options=options)
    url = f"{BASE_URL}?page={page_number}#results"
    page_school_names = []

    try:
        print(f"--- Opening page {page_number} (Eager Mode)...")
        driver.get(url)

        # --- 关键修改 3: 只检查元素是否存在，不检查可见性 ---
        # EC.presence_of_element_located: 只要代码里有就行，哪怕被广告挡住也无所谓
        # EC.visibility_of_element_located: 必须肉眼看得到 (会被广告挡住导致失败)
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "results"))
            )
        except:
            print(f"Page {page_number}: Wait timeout, trying to parse anyway...")

        # 稍微等一下动态数据填充（React/JS渲染）
        # 因为是 eager 模式，这里稍微多给一点点时间通常更安全
        time.sleep(3) 

        # 直接暴力读取源码，不管上面有没有覆盖层
        soup = BeautifulSoup(driver.page_source, "html.parser")
        page_school_names = extract_schools_from_soup(soup)

    except Exception as e:
        print(f"Error on page {page_number}: {e}")
    finally:
        driver.quit()
        print(f"--- Closed page {page_number}")
    
    return page_school_names

def scrape_texas_elementary_schools():
    all_rows = []
    seen_names = set()
    
    # 你设定的参数
    current_page = 1
    max_pages = 3

    while current_page <= max_pages:
        names = get_page_data(current_page)

        if not names:
            print(f"Page {current_page}: No schools extracted. (Check if IP is blocked or structure changed)")
            # 这里不一定要 break，可能只是这一页加载失败，可以 continue 试下一页
            # 但如果连续失败，建议手动停止
        else:
            unique_this_page = []
            for name in names:
                if name not in seen_names:
                    seen_names.add(name)
                    unique_this_page.append(name)

            print(f"Page {current_page}: Found {len(names)} total, {len(unique_this_page)} new unique.")
            
            for name in unique_this_page:
                rank = len(all_rows) + 1
                all_rows.append({"rank": rank, "school_name": name})

        if len(all_rows) >= EXPECTED_TOTAL:
            break

        current_page += 1
        # 稍微缩短一点等待，因为 driver 关闭再开启本身就很耗时
        time.sleep(1) 

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    output_file = "texas_elementary_schools_rankings.csv"
    df.to_csv(output_file, index=False, encoding="utf-8")
    print(f"\nSaved {len(df)} schools to {output_file}")   
    return df

if __name__ == "__main__":
    scrape_texas_elementary_schools()