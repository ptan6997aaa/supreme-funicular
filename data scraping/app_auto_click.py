from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import pandas as pd
from bs4 import BeautifulSoup

class SchoolRankingScraper:
    def __init__(self, url, num_clicks=5):
        """
        Initialize the scraper
        
        Args:
            url: The URL to scrape
            num_clicks: Number of times to click "Load More" button
        """
        self.url = url
        self.num_clicks = num_clicks
        self.driver = None
        self.schools_data = []
        
    def setup_driver(self):
        """Setup Chrome WebDriver with options"""
        options = webdriver.ChromeOptions()
        options.add_argument('--start-maximized')
        options.add_argument('--disable-blink-features=AutomationControlled')
        # Uncomment below to run headless
        # options.add_argument('--headless')
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.get(self.url)
        time.sleep(3)  # Initial page load wait
        
    def click_load_more(self):
        """
        Click the 'Load More' button multiple times with 2-second delays
        """
        print(f"Starting to click 'Load More' button {self.num_clicks} times...")
        
        for i in range(self.num_clicks):
            try:
                # Wait for the Load More button to be clickable
                load_more_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "load-more-button"))
                )
                
                # Scroll to button to ensure it's in view
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)
                time.sleep(0.5)
                
                # Click the button
                load_more_button.click()
                print(f"Click {i+1}/{self.num_clicks} completed")
                
                # Wait 2 seconds to avoid ban
                time.sleep(2)
                
            except TimeoutException:
                print(f"Load More button not found after {i} clicks. May have reached the end.")
                break
            except Exception as e:
                print(f"Error clicking Load More button: {e}")
                break
        
        print("Finished clicking Load More button")
        time.sleep(2)  # Final wait for content to load
        
    def scrape_schools(self):
        """
        Scrape school data from the loaded page
        """
        print("Starting to scrape school data...")
        
        # Get page source and parse with BeautifulSoup
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        
        # Find all school entries - they're typically in article or div elements
        # Based on the page structure, schools are in a specific container
        school_elements = soup.find_all('article') or soup.find_all('div', class_=lambda x: x and 'school' in x.lower())
        
        # Alternative: Find by links that contain school names
        school_links = soup.find_all('a', href=lambda x: x and '/education/k12/texas/' in x if x else False)
        
        # Extract unique schools
        seen_schools = set()
        
        for link in school_links:
            # Get the school container (parent elements)
            school_container = link.find_parent('li') or link.find_parent('article') or link.find_parent('div')
            
            if school_container:
                school_data = {}
                
                # School name
                school_name_elem = school_container.find('h3')
                if school_name_elem:
                    school_name = school_name_elem.get_text(strip=True)
                    
                    # Skip if already processed
                    if school_name in seen_schools:
                        continue
                    seen_schools.add(school_name)
                    
                    school_data['School Name'] = school_name
                    
                    # Location and District
                    location_text = school_container.get_text()
                    
                    # Rank
                    rank_elem = school_container.find(text=lambda x: x and 'in Texas Elementary Schools' in x if isinstance(x, str) else False)
                    if rank_elem:
                        rank = rank_elem.strip().split('#')[1].split('in')[0].strip() if '#' in rank_elem else 'N/A'
                        school_data['Rank'] = rank
                    else:
                        school_data['Rank'] = 'N/A'
                    
                    # Extract location
                    location_parts = school_container.find_all(text=True)
                    for idx, part in enumerate(location_parts):
                        if ', TX' in str(part):
                            school_data['Location'] = part.strip()
                            # District is usually right after location with pipe separator
                            if idx + 1 < len(location_parts):
                                district = location_parts[idx + 1].strip()
                                if district and district != '|':
                                    school_data['District'] = district
                            break
                    
                    # Grade Level
                    grade_elem = school_container.find(text='Grade Level')
                    if grade_elem:
                        grade_value = grade_elem.find_next()
                        if grade_value:
                            school_data['Grade Level'] = grade_value.get_text(strip=True)
                    else:
                        # Alternative search
                        if 'Grade Level' in location_text:
                            grade_match = location_text.split('Grade Level')[1].split('Enrollment')[0].strip() if 'Enrollment' in location_text else 'N/A'
                            school_data['Grade Level'] = grade_match
                    
                    # Enrollment
                    enrollment_elem = school_container.find(text='Enrollment')
                    if enrollment_elem:
                        enrollment_value = enrollment_elem.find_next()
                        if enrollment_value:
                            school_data['Enrollment'] = enrollment_value.get_text(strip=True)
                    else:
                        # Alternative search
                        if 'Enrollment' in location_text:
                            enrollment_match = location_text.split('Enrollment')[1].split('Student-Teacher Ratio')[0].strip() if 'Student-Teacher Ratio' in location_text else 'N/A'
                            school_data['Enrollment'] = enrollment_match
                    
                    # Student-Teacher Ratio
                    ratio_elem = school_container.find(text='Student-Teacher Ratio')
                    if ratio_elem:
                        ratio_value = ratio_elem.find_next()
                        if ratio_value:
                            school_data['Student-Teacher Ratio'] = ratio_value.get_text(strip=True)
                    else:
                        # Alternative search
                        if 'Student-Teacher Ratio' in location_text:
                            ratio_match = location_text.split('Student-Teacher Ratio')[1].strip().split()[0] if 'Student-Teacher Ratio' in location_text else 'N/A'
                            school_data['Student-Teacher Ratio'] = ratio_match
                    
                    # Only add if we have at least school name and rank
                    if 'School Name' in school_data and school_data.get('Rank') != 'N/A':
                        self.schools_data.append(school_data)
        
        print(f"Scraped {len(self.schools_data)} schools")
        
    def save_to_csv(self, filename='texas_elementary_schools.csv'):
        """
        Save scraped data to CSV file
        """
        if self.schools_data:
            df = pd.DataFrame(self.schools_data)
            df.to_csv(filename, index=False, encoding='utf-8')
            print(f"Data saved to {filename}")
            return df
        else:
            print("No data to save")
            return None
    
    def run(self):
        """
        Main execution method
        """
        try:
            self.setup_driver()
            self.click_load_more()
            self.scrape_schools()
            df = self.save_to_csv()
            
            # Display summary
            if df is not None:
                print("\n" + "="*50)
                print("SCRAPING SUMMARY")
                print("="*50)
                print(f"Total schools scraped: {len(df)}")
                print("\nFirst 5 schools:")
                print(df.head().to_string())
                print("\n" + "="*50)
            
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            if self.driver:
                self.driver.quit()
                print("Browser closed")


# Usage example
if __name__ == "__main__":
    # Configuration
    URL = "https://www.usnews.com/education/k12/elementary-schools/texas"
    NUM_CLICKS = 3  # User can set how many times to click Load More
    
    # Create scraper and run
    scraper = SchoolRankingScraper(url=URL, num_clicks=NUM_CLICKS)
    scraper.run()
