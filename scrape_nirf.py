# scrape_nirf.py

import os
import django
import sys
import time
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- Django Setup ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'college_directory_project.settings')
django.setup()

from colleges.models import College, NIRFRanking

# --- Configurations ---
URL = "https://www.nirfindia.org/Rankings/2024/EngineeringRanking.html"
RANKING_YEAR = 2024

def fetch_html_selenium(url):
    print(f"Using Selenium to fetch: {url}")

    chrome_options = ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--log-level=3")

    driver = None
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        driver.get(url)

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#tbl_overall tbody tr"))
        )

        time.sleep(2) 

        html_content = driver.page_source
        print(f"Successfully fetched content with Selenium from {url}")
        return html_content
    except Exception as e:
        print(f"Error fetching {url} with Selenium: {e}")
        return None
    finally:
        if driver:
            driver.quit()

def parse_nirf_rankings(html_content, year):
    print("Starting HTML parsing with BeautifulSoup...")
    soup = BeautifulSoup(html_content, 'html.parser')
    colleges_data = []

    ranking_table = soup.find('table', id='tbl_overall')

    if not ranking_table:
        print("DEBUG: Could not find the main ranking table with ID 'tbl_overall'.")
        return colleges_data

    print("DEBUG: Found table with ID 'tbl_overall'.")

    headers = []
    thead = ranking_table.find('thead')
    if thead:
        header_row = thead.find('tr')
        if header_row:
            headers = [th.get_text(strip=True) for th in header_row.find_all('th')]

    if not headers:
        print("DEBUG: Could not detect headers from the table's thead. This is unexpected.")
        headers = ['Institute ID', 'Name', 'City', 'State', 'Score', 'Rank']
        print(f"DEBUG: Falling back to assumed headers: {headers}")

    print(f"Detected headers: {headers}")

    # Map header names to their column indices (these are the indices from the THEAD)
    # We will use these as the expected indices for the TD elements.
    header_map = {
        'Institute ID': headers.index('Institute ID') if 'Institute ID' in headers else -1,
        'Name': headers.index('Name') if 'Name' in headers else -1,
        'City': headers.index('City') if 'City' in headers else -1,
        'State': headers.index('State') if 'State' in headers else -1,
        'Score': headers.index('Score') if 'Score' in headers else -1,
        'Rank': headers.index('Rank') if 'Rank' in headers else -1,
    }

    essential_headers_found = all(idx != -1 for idx in [
        header_map['Name'], header_map['City'], header_map['State'], header_map['Rank']
    ])
    if not essential_headers_found:
        print("DEBUG: Error: One or more essential headers (Name, City, State, Rank) not found in the table or header_map is incorrect.")
        return colleges_data

    tbody = ranking_table.find('tbody')
    if tbody:
        rows = tbody.find_all('tr')
        print(f"DEBUG: Found {len(rows)} rows in tbody.")
    else:
        rows = ranking_table.find_all('tr')
        print(f"DEBUG: Tbody not found. Found {len(rows)} rows directly under the table. (Will skip first row for header if headers were detected from thead)")
        if headers and len(rows) > 0 and 'Institute ID' in headers:
            rows = rows[1:]

    if not rows:
        print("DEBUG: No data rows found for parsing after all attempts.")
        return colleges_data

    print(f"DEBUG: Proceeding to parse {len(rows)} potential data rows.")

    for i, row in enumerate(rows):
        # Get direct TD children only, ignoring text nodes or other tags
        cols = [child for child in row.children if child.name == 'td']

        # Debugging: Print raw column count and content for first few rows
        if i < 5 or (len(colleges_data) < 5 and len(cols) == 6): # Print for first 5 processed rows
            print(f"\nDEBUG: --- Processing row {i+1} (has {len(cols)} direct TD columns) ---")
            # print(f"DEBUG: Raw row HTML: {row}") # Uncomment for extremely verbose debug

        # We now know that valid data rows have exactly 6 columns
        if len(cols) == 6:
            try:
                # --- CRITICAL FIXES FOR EXTRACTION ---
                # 1. Extract Name: Get text from index 1, then aggressively remove nested table content.
                #    The nested table is inside a div with class 'tbl_hidden'.
                #    We need to get the text *before* this div.
                name_td = cols[header_map['Name']]
                # Get all direct text nodes and join them, then strip.
                # This should get "Indian Institute of Technology Madras"
                name = ''.join(name_td.find_all(string=True, recursive=False)).strip()
                # Remove any remaining "More Details", "Close", pipe characters, or extra spaces
                name = re.sub(r'(More Details|Close)\s*\|*\s*|[\n\r\t]+', '', name, flags=re.IGNORECASE).strip()
                name = re.sub(r'\s+', ' ', name) # Replace multiple spaces with single space

                # 2. Extract City, State, Rank from their correct indices
                city = cols[header_map['City']].get_text(strip=True)
                state = cols[header_map['State']].get_text(strip=True)
                rank_str = cols[header_map['Rank']].get_text(strip=True) # This is the actual rank

                print(f"DEBUG: Raw TD contents (Name, City, State, Rank):")
                print(f"DEBUG:   Name TD: '{cols[header_map['Name']].get_text(strip=True, separator=' ')}'")
                print(f"DEBUG:   City TD: '{cols[header_map['City']].get_text(strip=True)}'")
                print(f"DEBUG:   State TD: '{cols[header_map['State']].get_text(strip=True)}'")
                print(f"DEBUG:   Rank TD: '{cols[header_map['Rank']].get_text(strip=True)}'")

                try:
                    engineering_rank = int(rank_str)
                except ValueError:
                    engineering_rank = None
                    print(f"DEBUG: Could not convert rank '{rank_str}' to int. Setting to None.")

                print(f"DEBUG: Cleaned Name: '{name}'")
                print(f"DEBUG: Processed City: '{city}'")
                print(f"DEBUG: Processed State: '{state}'")
                print(f"DEBUG: Processed Rank: '{engineering_rank}' (Type: {type(engineering_rank)})")

                if name and city and state and engineering_rank is not None:
                    colleges_data.append({
                        'official_name': name,
                        'city': city,
                        'state': state,
                        'engineering_rank': engineering_rank,
                        'year': year
                    })
                    print(f"DEBUG: Row {i+1} SUCCESSFULLY added to colleges_data.")
                else:
                    print(f"DEBUG: Row {i+1} SKIPPED: One or more processed values are None/empty (Name: '{name}', City: '{city}', State: '{state}', Rank: {engineering_rank}).")

            except IndexError:
                print(f"DEBUG: Row {i+1} SKIPPED (IndexError - column missing or unexpected structure). Raw row text: {row.get_text(strip=True)[:100]}...")
            except Exception as e:
                print(f"DEBUG: Row {i+1} SKIPPED (General Error): {e}. Raw row text: {row.get_text(strip=True)[:100]}...")
        else:
            print(f"DEBUG: Row {i+1} SKIPPED: Not a valid data row (has {len(cols)} direct TD columns, expected 6).")

    return colleges_data

def save_to_django_db(colleges_data):
    """
    Saves the extracted college data into Django's PostgreSQL database.
    Uses update_or_create to avoid duplicates and update existing records.
    """
    print(f"\nAttempting to save {len(colleges_data)} colleges to Django database...")
    saved_count = 0
    updated_count = 0

    for data in colleges_data:
        college_name = data['official_name']
        city = data['city']
        state = data['state']
        engineering_rank = data['engineering_rank']
        year = data['year']

        try:
            college, created = College.objects.update_or_create(
                official_name=college_name,
                city=city,
                state=state,
                defaults={}
            )

            if created:
                saved_count += 1
                print(f"Created new college: {college.official_name}")
            else:
                updated_count += 1
                print(f"Updated existing college: {college.official_name}")

            nirf_ranking, nirf_created = NIRFRanking.objects.update_or_create(
                college=college,
                year=year,
                defaults={
                    'engineering_rank': engineering_rank,
                }
            )
            if nirf_created:
                print(f"  -> Added NIRF ranking for {year}: #{engineering_rank}")
            else:
                print(f"  -> Updated NIRF ranking for {year}: #{engineering_rank}")

        except Exception as e:
            print(f"❌ Error saving {college_name} to DB: {e}")

    print(f"\n✅ Data saving complete. Created: {saved_count}, Updated: {updated_count}.")


if __name__ == "__main__":
    print(f"Starting NIRF Engineering Rankings scraping for year {RANKING_YEAR}...")
    html_content = fetch_html_selenium(URL)

    if html_content:
        colleges_data = parse_nirf_rankings(html_content, RANKING_YEAR)

        if colleges_data:
            save_to_django_db(colleges_data)
            # Optional: Verify by fetching from DB
            # print("\nVerifying a few colleges from DB:")
            # for col in College.objects.filter(official_name__icontains='Indian Institute of Technology')[:3]:
            #     latest_nirf = col.nirf_rankings.filter(year=RANKING_YEAR).first()
            #     print(f"- {col.official_name}, Latest NIRF ({RANKING_YEAR}): #{latest_nirf.engineering_rank if latest_nirf else 'N/A'}")
    else:
        print("Failed to retrieve HTML content. Cannot parse or save.")