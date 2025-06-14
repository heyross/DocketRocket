import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
import time
import logging
import random
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options

BASE_URL = "https://restructuring.ra.kroll.com" 
PAGE_URL = "https://restructuring.ra.kroll.com/bbby/Home-DocketInfo"
DOWNLOAD_DIR = r"C:\Users\Ross Brown\OneDrive\DocketRocketSource"
LINKS_FILE = "scraped_links.json"

# --- Selenium WebDriver Configuration ---
driver_path = r"D:\chromedriver-win64\chromedriver.exe" 

# --- Logging Setup ---
logger = logging.getLogger(__name__)

def setup_logging():
    """Configures logging to file and console."""
    log_file_name = 'scraper.log'
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_file_path = os.path.join(script_dir, log_file_name)

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s',
        filename=log_file_path,
        filemode='w'
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    
    logging.getLogger('').addHandler(console_handler)
    
    logger.info(f"Logging configured. DEBUG output to: {log_file_path}. INFO output to console.")
# --- End Logging Setup ---

def sanitize_filename(filename):
    """Removes or replaces characters that are invalid in Windows filenames."""
    if not filename:
        return "untitled_document"
    # Remove characters that are definitely invalid
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove control characters (ASCII 0-31)
    filename = re.sub(r'[\x00-\x1F]', '', filename)
    # Replace multiple underscores with a single one
    filename = re.sub(r'_+', '_', filename)
    # Remove leading/trailing whitespace, periods, and underscores
    filename = filename.strip().strip('._ ')
    # Limit length
    filename = filename[:180] 
    if not filename: 
        return "sanitized_document"
    return filename

def create_download_directory(directory):
    """Creates the download directory if it doesn't exist."""
    if not os.path.exists(directory):
        logger.info(f"Creating directory: {directory}")
        os.makedirs(directory)
    else:
        logger.info(f"Directory already exists: {directory}")

def load_scraped_links(filename):
    """Load previously scraped PDF info from a JSON file."""
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load existing link file {filename}: {e}")
    return []

def save_scraped_links(filename, links):
    """Persist scraped PDF info to a JSON file."""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(links, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save scraped links to {filename}: {e}")

# def fetch_api_page_data(session, page_num, rows_per_page):
#     """(Obsolete with Selenium) Fetches a single page of docket data from the Kroll API."""
#     params = {
#         'page': page_num,
#         'rows': rows_per_page,
#         # 'sidx': 'DocketNumberSort', # Temporarily removed for testing
#         # 'sord': 'asc' # Temporarily removed for testing
#     }
#     headers = {
#         'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
#         'Referer': PAGE_URL, # The main docket page
#         'Accept': 'application/json, text/javascript, */*; q=0.01', # Mimic browser accept header
#         'X-Requested-With': 'XMLHttpRequest' # Common for AJAX requests
#     }
#     try:
#         logger.info(f"Fetching API data: page {page_num}, rows {rows_per_page}, params: {params}")
# #         response = session.get(API_DOCKET_DATA_URL, params=params, headers=headers, timeout=30)
#         
#         logger.debug(f"API response for page {page_num}: Status Code: {response.status_code}, Headers: {response.headers}")
#         
#         # Check for non-200 status codes specifically before trying to parse JSON
#         if response.status_code != 200:
#             logger.error(f"API request for page {page_num} returned status {response.status_code}, not 200.")
#             logger.debug(f"Response text for status {response.status_code} (first 500 chars): {response.text[:500]}...")
#             # If it's 202, it might be an empty body, which is not a typical HTTPError caught by raise_for_status for 2xx codes
#             if response.status_code == 202 and not response.text.strip():
#                 logger.warning(f"API returned 202 with empty body for page {page_num}. Treating as no data.")
#                 return None # Or an empty dict/list structure if your main loop expects it
#             # For other non-200s, try to raise for status if it wasn't a 2xx that slipped through
#             response.raise_for_status() # This will raise an HTTPError for 4xx/5xx client/server errors
# 
#         if not response.text.strip():
#             logger.warning(f"API response for page {page_num} is empty. Status: {response.status_code}")
#             return None # Or an empty dict/list structure
#             
#         logger.debug(f"Successfully fetched API data for page {page_num}. Status: {response.status_code}. Attempting JSON parse.")
#         return response.json()
#     
#     except requests.exceptions.HTTPError as http_err:
#         logger.error(f"HTTP error occurred while fetching API data (page {page_num}): {http_err}")
#         if http_err.response is not None:
#             logger.error(f"Status Code: {http_err.response.status_code}")
#             logger.error(f"Response Headers: {http_err.response.headers}")
#             logger.debug(f"Full Response Text (first 500 chars): {http_err.response.text[:500]}...")
#         return None
#     except requests.exceptions.RequestException as req_err: # Catches other network errors like DNS, connection refused
#         logger.exception(f"Request error occurred while fetching API data (page {page_num}): {req_err}")
#         return None
#     except json.JSONDecodeError as json_err:
#         logger.error(f"JSON decode error for API response (page {page_num}): {json_err}")
#         logger.debug(f"Response text that failed to parse (first 500 chars): {response.text[:500]}...")
#         return None

# def extract_pdf_infos_from_api_response(json_data):
#     """(Obsolete with Selenium) Extracts PDF information from the Kroll API JSON response."""
#     pdf_infos = []
#     if not json_data or 'rows' not in json_data:
#         logger.warning("No 'rows' found in API JSON response or JSON data is empty.")
#         return pdf_infos
# 
#     for item in json_data['rows']:
#         description_html = item.get('Description', '')
#         docket_number = item.get('DocketNumber', 'UnknownDocket').strip()
#         date_filed_raw = item.get('DateFiled', 'UnknownDate').strip()
#         # Sanitize date_filed for filename (e.g. '01/25/2024' -> '01_25_2024')
#         date_filed_clean = date_filed_raw.replace('/', '_')
# 
#         if not description_html:
#             logger.debug(f"Skipping item with empty Description (Docket: {docket_number})")
#             continue
# 
#         soup = BeautifulSoup(description_html, 'html.parser')
#         link_tag = soup.find('a', class_='link', href=True)
# 
#         if link_tag:
#             href = link_tag['href']
#             onclick_attr = link_tag.get('onclick', '')
#             title_attr = link_tag.get('title', '').strip()
# 
#             if href.startswith('/bbby/Home-DownloadPDF') and 'OpenDialog_DocketCaptcha' not in onclick_attr:
#                 absolute_url = urljoin(BASE_URL, href)
#                 
#                 # Construct a descriptive filename base
#                 # Example: Docket_123_Exhibit_A_to_Declaration_01_25_2024
#                 filename_base_parts = []
#                 if docket_number and docket_number != 'UnknownDocket':
#                     filename_base_parts.append(f"Docket_{docket_number}")
#                 if title_attr:
#                     filename_base_parts.append(title_attr)
#                 if date_filed_clean and date_filed_clean != 'UnknownDate':
#                     filename_base_parts.append(date_filed_clean)
#                 
#                 if not filename_base_parts: # Fallback if all parts are empty
#                     filename_suggestion = f"Document_ID_{parse_qs(urlparse(href).query).get('id1',['unknown'])[0]}"
#                 else:
#                     filename_suggestion = "_".join(filename_base_parts)
#                 
#                 sanitized_filename_suggestion = sanitize_filename(filename_suggestion)
# 
#                 pdf_infos.append({
#                     'url': absolute_url,
#                     'filename_suggestion': sanitized_filename_suggestion, # This will be used by download_pdf
#                     'original_href': href,
#                     'docket_number': docket_number,
#                     'date_filed': date_filed_raw # Store original date for logging/metadata if needed
#                 })
#                 logger.debug(f"Found PDF: URL='{absolute_url}', Suggested Filename='{sanitized_filename_suggestion}.pdf', Docket='{docket_number}'")
#             elif href.startswith('/bbby/Home-DownloadPDF'):
#                 logger.info(f"Skipping CAPTCHA link: Docket='{docket_number}', Title='{title_attr}', Href='{href}'")
#         else:
#             logger.debug(f"No 'a.link' tag found in Description for Docket: {docket_number}")
#             
#     logger.info(f"Extracted {len(pdf_infos)} non-CAPTCHA PDF links from API response page.")
#     return pdf_infos

# Track whether we've already manually solved the CAPTCHA during this run
captcha_solved = False


def download_pdf(driver, pdf_info, directory):
    """Downloads a single PDF from the given pdf_info to the specified directory."""
    pdf_url = pdf_info['url']
    filename_suggestion_base = pdf_info.get('filename_suggestion', 'untitled_document')

    global captcha_solved
    try:
        logger.info(f"Attempting to navigate to PDF URL via Selenium: {pdf_url}")
        driver.get(pdf_url)
        time.sleep(random.uniform(1, 3))  # Allow page or captcha to render

        page_source = driver.page_source.lower()
        captcha_present = 'captcha' in page_source

        if captcha_present and not captcha_solved:
            print("\n--- HUMAN INTERVENTION REQUIRED ---")
            print(
                f"Navigated to: {pdf_url} (for docket item: {pdf_info.get('docket_number', 'N/A')}, title: {pdf_info.get('title', 'N/A')})"
            )
            print("Please solve the CAPTCHA in the Selenium browser window.")
            print(
                f"The PDF should then download automatically to: {directory} as {filename_suggestion_base}.pdf"
            )
            input("Press Enter here AFTER the CAPTCHA is solved and the PDF is saved...")
            captcha_solved = True
        else:
            if captcha_present and captcha_solved:
                logger.info("CAPTCHA text detected but already solved earlier; proceeding without prompt.")
            else:
                logger.info("No CAPTCHA detected. Waiting briefly for automatic download...")
            time.sleep(2)

        # Verify the file exists after either automatic download or manual step
        filepath = os.path.join(directory, filename_suggestion_base + ".pdf")
        wait_time = 0
        while wait_time < 30 and not os.path.exists(filepath):
            time.sleep(1)
            wait_time += 1

        if os.path.exists(filepath):
            logger.info(f"Confirmed download of {filename_suggestion_base}.pdf to {filepath}")
            return True
        else:
            logger.warning(
                f"Expected file {filename_suggestion_base}.pdf not found at {filepath}."
            )
            return False

    except Exception as e:
        logger.error(f"An unexpected error occurred while downloading {pdf_url}: {e}")
        return False

def extract_pdf_infos_from_selenium_page(driver):
    """Extracts PDF information from the current page loaded in Selenium WebDriver."""
    pdf_infos = []
    logger.info("Extracting PDF info from current Selenium page...")
    try:
        # !!! Placeholder: Update these selectors based on actual page structure !!!
        # Example: Find all rows in the docket table
        # docket_table_rows = driver.find_elements(By.XPATH, "//table[@id='results-table']/tbody/tr")
        # For a more robust wait:
        # Using the absolute XPath provided by the user for table rows
        docket_table_rows = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, "/html/body/main/div[3]/div[2]/div[3]/div[2]/div[3]/div[4]/div[1]/table/tbody/tr"))
        )

        if not docket_table_rows:
            logger.warning("No docket table rows found on the page with current selectors.")
            return []

        for row in docket_table_rows:
            try:
                # --- Extract elements from the row --- 
                # Using XPaths provided by the user, relative to the current row
                # The link_tag also serves as the title_element based on user description
                link_tag = row.find_element(By.XPATH, ".//td[2]/span/p/a") 
                docket_num_element = row.find_element(By.XPATH, ".//td[1]")
                # title_element is the same as link_tag for its text content
                date_element = row.find_element(By.XPATH, ".//td[3]")

                href = link_tag.get_attribute('href')
                # Ensure URL is absolute (CAPTCHA check moved to download_pdf)
                absolute_url = urljoin(driver.current_url, href)
                
                docket_number = docket_num_element.text.strip()
                title = link_tag.text.strip() # Title is the text of the link_tag
                date_str = date_element.text.strip()

                # Sanitize for filename
                filename_suggestion = sanitize_filename(f"{date_str} - DN {docket_number} - {title}.pdf")

                pdf_infos.append({
                    'url': absolute_url,
                    'docket_number': docket_number,
                    'title': title,
                    'date': date_str,
                    'filename_suggestion': filename_suggestion,
                    'original_href': href
                })
            except NoSuchElementException:
                logger.warning("Could not find all expected elements in a row. Skipping row.")
                continue # Skip this row if elements are missing
            except Exception as e:
                logger.error(f"Error processing a row: {e}")
                continue

    except TimeoutException:
        logger.warning("Timed out waiting for docket table rows to appear.")
    except Exception as e:
        logger.error(f"Error extracting PDF infos from Selenium page: {e}")
    
    logger.info(f"Extracted {len(pdf_infos)} non-CAPTCHA PDF links from Selenium page.")
    return pdf_infos

def main():
    """Main function to orchestrate the PDF downloading process using Selenium."""
    create_download_directory(DOWNLOAD_DIR)

    # Load any previously collected links so the scraper can resume work
    all_pdf_infos = load_scraped_links(LINKS_FILE)
    seen_download_urls = set(info.get('url') for info in all_pdf_infos)
    # current_page and total_pages were for API pagination, not directly used by Selenium in the same way
    # Selenium pagination is handled by clicking 'Next' until no more pages.

    logger.info(f"Starting PDF scraping from Kroll Docket Page: {PAGE_URL}")
    # create_download_directory is already called at the beginning of main.
    # all_pdf_infos is already initialized.
    
    # Initialize WebDriver
    driver = None
    try:
        chrome_options = Options()
        # Ensure DOWNLOAD_DIR is an absolute path for Chrome preferences
        abs_download_dir = os.path.abspath(DOWNLOAD_DIR)
        chrome_options.add_experimental_option("prefs", {
          "download.default_directory": abs_download_dir,
          "download.prompt_for_download": False,
          "download.directory_upgrade": True,
          "plugins.always_open_pdf_externally": True # Attempt to force download PDFs
        })

        if driver_path:
            service = ChromeService(executable_path=driver_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            # Assumes chromedriver is in PATH
            driver = webdriver.Chrome(options=chrome_options) 
        
        logger.info(f"Navigating to {PAGE_URL} with Selenium...")
        driver.get(PAGE_URL)
        time.sleep(random.uniform(2,5)) # Initial wait for page to potentially load dynamic content

        current_page_num = 1
        while True:
            logger.info(f"Processing page {current_page_num}...")
            page_pdf_infos = extract_pdf_infos_from_selenium_page(driver)

            new_infos = []
            for info in page_pdf_infos:
                if info['url'] not in seen_download_urls:
                    new_infos.append(info)
                    seen_download_urls.add(info['url'])

            if not new_infos:
                logger.info("No new PDF links found on this page. Assuming end of pagination.")
                break

            all_pdf_infos.extend(new_infos)
            save_scraped_links(LINKS_FILE, all_pdf_infos)

            logger.info(
                f"Found {len(new_infos)} new PDF links on page {current_page_num}. Total unique links so far: {len(all_pdf_infos)}"
            )

            # --- Pagination: Find and click 'Next' button --- 
            # !!! Placeholder: Update this selector for the 'Next Page' button !!!
            try:
                # Example: next_button = driver.find_element(By.LINK_TEXT, "Next")
                # Example: next_button = driver.find_element(By.XPATH, "//a[contains(@class, 'next-page-button')]")
                next_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "/html/body/main/div[3]/div[2]/div[2]/div[2]/div[1]/a[3]")) # User-provided XPath
                )
                logger.info("Found 'Next Page' button. Clicking...")
                driver.execute_script("arguments[0].scrollIntoView(true);", next_button) # Scroll to button
                time.sleep(0.5) # Brief pause before click
                driver.execute_script("arguments[0].click();", next_button) # JS click to bypass potential overlays
                current_page_num += 1
                # Wait for page to load after click
                page_load_delay = random.uniform(3, 7)
                logger.info(f"Waiting {page_load_delay:.2f} seconds for next page to load...")
                time.sleep(page_load_delay) 
            except (TimeoutException, NoSuchElementException):
                logger.info("No 'Next Page' button found or not clickable. Assuming end of pagination.")
                break # Exit loop if no next page button
            except Exception as e:
                logger.error(f"Error clicking 'Next Page' button: {e}")
                break

        # PDF download logic is now moved inside the main try block
        if not all_pdf_infos:
            logger.warning("No suitable PDF links found after Selenium scraping.")
            return  # Exit early if no PDFs found; finally block will still execute.
        else:
            logger.info(
                f"--- Collected a total of {len(all_pdf_infos)} PDF links. Starting downloads. ---"
            )
            downloaded_count = 0
            failed_count = 0

            # Deduplicate based on URL before downloading
            unique_pdf_infos_to_download = []
            seen_download_urls_download = set()
            for pdf_info_item in all_pdf_infos:
                if pdf_info_item['url'] not in seen_download_urls_download:
                    unique_pdf_infos_to_download.append(pdf_info_item)
                    seen_download_urls_download.add(pdf_info_item['url'])

            logger.info(
                f"After deduplication, {len(unique_pdf_infos_to_download)} unique PDFs to attempt downloading."
            )

            if driver:  # Ensure driver is still active for downloads
                for i, pdf_info_item in enumerate(unique_pdf_infos_to_download):
                    if i > 0:
                        download_delay = random.uniform(3, 8)
                        logger.info(
                            f"Waiting for {download_delay:.2f} seconds before next download..."
                        )
                        time.sleep(download_delay)

                    if download_pdf(driver, pdf_info_item, DOWNLOAD_DIR):
                        downloaded_count += 1
                    else:
                        failed_count += 1

                logger.info("--- Download Summary ---")
                logger.info(
                    f"Successfully downloaded/already existed: {downloaded_count} PDFs"
                )
                logger.info(f"Failed to download: {failed_count} PDFs")
                logger.info(f"All files are located in: {DOWNLOAD_DIR}")
            else:
                logger.error(
                    "WebDriver was not available for the download phase. Skipping downloads."
                )

    except Exception as e:
        logger.error(f"An error occurred during Selenium processing or downloads: {e}")
    finally:
        # Persist collected links even if an error occurred
        save_scraped_links(LINKS_FILE, all_pdf_infos)
        if driver:
            logger.info("Closing Selenium WebDriver.")
            driver.quit()

if __name__ == "__main__":
    setup_logging()
    main()
