# <<< Start of updated code >>>

from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from datetime import datetime
import re
import os
from werkzeug.security import generate_password_hash, check_password_hash
from bs4 import BeautifulSoup # Added for Amazon reviews
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from flask_caching import Cache
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from flask_compress import Compress
import logging
from logging.handlers import RotatingFileHandler
import os
from werkzeug.middleware.proxy_fix import ProxyFix
from datetime import timedelta

app = Flask(__name__)
app.secret_key = os.urandom(24) # Remember to use a static key for production
DATABASE = 'product_comparison.db'

compress = Compress()

# Configure Flask app with optimizations
def configure_app(app):
    # Enable compression
    compress.init_app(app)
    
    # Fix for proper IP address handling behind proxies
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    
    # Configure logging
    if not os.path.exists('logs'):
        os.mkdir('logs')
    
    file_handler = RotatingFileHandler('logs/price_comparison.log', maxBytes=10240000, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Price Comparison startup')
    
    # Configure session
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
    app.config['SESSION_FILE_DIR'] = os.path.join(os.getcwd(), 'flask_session')
    app.config['SESSION_FILE_THRESHOLD'] = 100  # Number of sessions in session dir
    
    # Configure template caching
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 86400  # 1 day
    app.config['TEMPLATES_AUTO_RELOAD'] = False  # Disable in production
    
    # Additional configurations
    app.config['JSON_SORT_KEYS'] = False  # Preserve JSON order
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

# Update the main execution block



# --- Database initialization (No changes needed here) ---
class WebDriverManager:
    _instance = None
    _driver_pool = []
    _max_drivers = 2  # Maximum number of drivers to keep in the pool
    
    @classmethod
    def get_driver(cls):
        """Get a driver from the pool or create a new one"""
        if cls._driver_pool:
            return cls._driver_pool.pop()
        return cls._create_driver()
    
    @classmethod
    def return_driver(cls, driver):
        """Return a driver to the pool or quit it"""
        if driver:
            try:
                # Clear cookies to prevent session issues
                driver.delete_all_cookies()
                # Navigate to blank page to stop any processes
                driver.get("about:blank")
                # Add to pool if not at max capacity
                if len(cls._driver_pool) < cls._max_drivers:
                    cls._driver_pool.append(driver)
                else:
                    driver.quit()
            except Exception:
                # If any error, just quit the driver
                try:
                    driver.quit()
                except:
                    pass
    
    @classmethod
    def _create_driver(cls):
        """Create a new optimized WebDriver instance"""
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-notifications")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--log-level=3")  # Minimal logging
        options.add_argument("--window-size=1920,1080")  # Standard resolution
        
        # Set page load strategy to eager to load faster
        options.page_load_strategy = 'eager'
        
        # Random user agent
        USER_AGENTS = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
        ]
        options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
        
        # Initialize driver with ChromeDriverManager for automatic driver management
        try:
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            # Set page load timeout
            driver.set_page_load_timeout(30)
            driver.set_script_timeout(20)
            return driver
        except Exception as e:
            print(f"Failed to create WebDriver with ChromeDriverManager: {e}")
            # Fallback to regular Chrome driver
            return webdriver.Chrome(options=options)
    
    @classmethod
    def cleanup(cls):
        """Close all drivers in the pool"""
        for driver in cls._driver_pool:
            try:
                driver.quit()
            except:
                pass
        cls._driver_pool = []

# Register cleanup function to run at Flask app shutdown
@app.teardown_appcontext
def shutdown_driver_pool(exception=None):
    WebDriverManager.cleanup()

# Replace your setup_driver function with this
def setup_driver():
    return WebDriverManager.get_driver()

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    # USER Table
    c.execute('''
    CREATE TABLE IF NOT EXISTS USER (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username VARCHAR(255) UNIQUE,
        email VARCHAR(255) UNIQUE,
        password_hash VARCHAR(255),
        created_at DATETIME
    )
    ''')
    # PLATFORM Table
    c.execute('''
    CREATE TABLE IF NOT EXISTS PLATFORM (
        platform_id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform_name VARCHAR(255),
        platform_url VARCHAR(255)
    )
    ''')
    # PRODUCT Table
    c.execute('''
    CREATE TABLE IF NOT EXISTS PRODUCT (
        product_id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name VARCHAR(255),
        product_description TEXT,
        category VARCHAR(255)
    )
    ''')
    # PRODUCT_LISTING Table
    c.execute('''
    CREATE TABLE IF NOT EXISTS PRODUCT_LISTING (
        listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        platform_id INTEGER,
        product_link VARCHAR(255),
        FOREIGN KEY (product_id) REFERENCES PRODUCT(product_id),
        FOREIGN KEY (platform_id) REFERENCES PLATFORM(platform_id)
    )
    ''')
    # PRICE_HISTORY Table
    c.execute('''
    CREATE TABLE IF NOT EXISTS PRICE_HISTORY (
        price_id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_id INTEGER,
        price_value DECIMAL(10,2),
        timestamp DATETIME,
        FOREIGN KEY (listing_id) REFERENCES PRODUCT_LISTING(listing_id)
    )
    ''')
    # REVIEW Table
    c.execute('''
    CREATE TABLE IF NOT EXISTS REVIEW (
        review_id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_id INTEGER,
        review_text TEXT,
        rating INTEGER, -- Consider storing float if needed, or link to product rating
        review_date DATETIME,
        FOREIGN KEY (listing_id) REFERENCES PRODUCT_LISTING(listing_id)
    )
    ''')
    # PRICE_TRACKING Table
    c.execute('''
    CREATE TABLE IF NOT EXISTS PRICE_TRACKING (
        tracking_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        listing_id INTEGER,
        created_at DATETIME,
        is_active BOOLEAN,
        notification_threshold DECIMAL(10,2),
        FOREIGN KEY (user_id) REFERENCES USER(user_id),
        FOREIGN KEY (listing_id) REFERENCES PRODUCT_LISTING(listing_id)
    )
    ''')
    # Insert default platforms
    c.execute("INSERT OR IGNORE INTO PLATFORM (platform_name, platform_url) VALUES (?, ?)",
              ("Flipkart", "https://www.flipkart.com"))
    c.execute("INSERT OR IGNORE INTO PLATFORM (platform_name, platform_url) VALUES (?, ?)",
              ("Amazon", "https://www.amazon.in"))
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

cache = Cache(config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 3600})
cache.init_app(app)

def save_to_cache(key, value, timeout):
    cache.set(key, value, timeout=timeout)

def get_from_cache(key):
    return cache.get(key)

# --- Setup WebDriver for scraping (No changes needed here) ---
def setup_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
    ]
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    # Consider adding path to chromedriver if not in PATH
    # driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver = webdriver.Chrome(options=options)
    return driver

# --- Find product on Flipkart (Updated selectors) ---
def find_flipkart_product(product_name):
    driver = setup_driver()
    try:
        driver.get(f'https://www.flipkart.com/search?q={product_name.replace(" ", "+")}')
        # Handle login popup
        try:
            close_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(text(),"✕")] | //button[contains(text(),"x")] | //span[contains(text(),"✕")]'))
            )
            close_button.click()
            print("Closed Flipkart login popup.")
        except:
            print("Flipkart login popup not found or could not be closed.")
            pass

        # Using a more comprehensive selector from the second file
        link_selector = 'a.CGtC98, a.VJA3rP, a._1fQZEK, a.s1Q9rs'
        print(f"Waiting for Flipkart link element with selector: {link_selector}")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, link_selector))
        )
        print("Flipkart link element found.")

        first_product = driver.find_element(By.CSS_SELECTOR, link_selector)
        flipkart_url = first_product.get_attribute("href")
        print(f"Found Flipkart URL: {flipkart_url}")
        return flipkart_url

    except Exception as e:
        print(f"Error finding Flipkart product link: {e}")
        return None
    finally:
        if driver:
            driver.quit()

# --- Get Flipkart Product Details (Updated selectors based on second file) ---
def get_flipkart_product_details(url):
    driver = setup_driver()
    product_name = "Product name not found"
    price = "0"
    rating = "0"
    reviews_count = "0"
    description = "No description available"
    image_url = ""
    category = "Unknown"
    reviews = []

    try:
        print(f"Navigating to Flipkart URL: {url}")
        driver.get(url)
        try:
            close_button = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(text(),"✕")] | //button[contains(text(),"x")] | //span[contains(text(),"✕")]'))
            )
            close_button.click()
            print("Closed Flipkart popup on product page.")
        except:
            pass

        # Using the more specific name selector from the second file
        name_selector = 'span.VU-ZEz'
        print(f"Waiting for Flipkart name element: {name_selector}")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, name_selector))
        )
        print("Flipkart name element found.")

        # Extract product name
        try:
            product_name = driver.find_element(By.CSS_SELECTOR, name_selector).text.strip()
        except Exception as e_name:
            print(f"Could not extract Flipkart product name: {e_name}")
            try:
                product_name = driver.find_element(By.CSS_SELECTOR, 'span.B_NuCI').text.strip()
            except:
                product_name = "Product name not found"

        # --- Price Extraction Logic --- 
        price_found = False
        price_selectors_to_try = [
            'div.Nx9bqj._4b5DiR',  # Added from second file
            'div.Nx9bqj',          # Added from second file
            'div._30jeq3._16Jk6d', # From original file
            'div._30jeq3'          # From original file
        ]
        for selector in price_selectors_to_try:
            try:
                price_element = driver.find_element(By.CSS_SELECTOR, selector)
                price_text = price_element.text.strip()
                cleaned_price = re.sub(r'[^\d.]', '', price_text)
                if cleaned_price and float(cleaned_price) > 0:
                    price = cleaned_price
                    price_found = True
                    print(f"Found Flipkart price using selector '{selector}': {price}")
                    break
            except Exception as e_price_loop:
                continue
        if not price_found:
            print("Could not extract Flipkart price using any known selector.")
            price = "0"

        # Extract rating
        rating_selector = 'div.ipqd2A'  # From both files
        try:
            rating_element = driver.find_element(By.CSS_SELECTOR, rating_selector)
            rating_text = rating_element.text.strip()
            rating_match = re.match(r'(\d+(?:\.\d+)?)', rating_text)
            rating = rating_match.group(1) if rating_match else "0"
        except Exception as e_rating:
            print(f"Could not extract Flipkart rating using {rating_selector}: {e_rating}")
            try:
                rating_element = driver.find_element(By.CSS_SELECTOR, 'div._3LWZlK')
                rating = rating_element.text.strip()
            except:
                rating = "0"

        # Extract reviews count - Updated selectors
        reviews_count_selectors = [
            'span.Wphh3N',  # New selector from the example
            'span._2_R_DZ'  # Original selector
        ]
        
        reviews_count = "0"
        for selector in reviews_count_selectors:
            try:
                reviews_count_element = driver.find_element(By.CSS_SELECTOR, selector)
                reviews_count_text = reviews_count_element.text.strip()
                
                # Try to extract both ratings and reviews
                ratings_match = re.search(r'(\d+(?:,\d+)*)\s+Ratings', reviews_count_text, re.IGNORECASE)
                reviews_match = re.search(r'(\d+(?:,\d+)*)\s+Reviews', reviews_count_text, re.IGNORECASE)
                
                if reviews_match:
                    reviews_count = reviews_match.group(1).replace(',', '')
                    print(f"Found {reviews_count} reviews")
                    break
                elif ratings_match:
                    # If we only find ratings, keep looking for reviews in other elements
                    continue
                
            except Exception as e_rev_count:
                print(f"Could not extract Flipkart reviews count using {selector}: {e_rev_count}")
                continue
                
        if reviews_count == "0":
            print("Could not extract Flipkart reviews count using any known selector.")

        # Extract description
        description_selector = 'div._1mXcCf.RmoJUa'
        try:
            description_element = driver.find_element(By.CSS_SELECTOR, description_selector)
            description = description_element.text.strip()
            if not description:
                description_element = driver.find_element(By.CSS_SELECTOR, 'div._2418kt')
                description = description_element.text.strip()
        except Exception as e_desc:
            print(f"Could not extract Flipkart description: {e_desc}")
            description = "No description available"

        # Extract image - Updated selectors
        image_selectors_to_try = [
            'img.DByuf4.IZexXJ.jLEJ7H',  # New selector from the example
            'img._396cs4._2amPTt._3qGmMb',  # Original selector
            'img._396cs4'  # Original fallback
        ]
        
        image_url = ""
        for selector in image_selectors_to_try:
            try:
                image_element = driver.find_element(By.CSS_SELECTOR, selector)
                image_url = image_element.get_attribute('src')
                if image_url:
                    print(f"Found Flipkart image using selector '{selector}': {image_url}")
                    break
            except Exception as e_img:
                continue
                
        if not image_url:
            print("Could not extract Flipkart image using any known selector.")

        # Extract category
        category = "Unknown"

        # Get reviews - Using selector from second file
        reviews_selector = "div.ZmyHeo"
        try:
            driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(0.5)
            WebDriverWait(driver, 5).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, reviews_selector)))
            review_elements = driver.find_elements(By.CSS_SELECTOR, reviews_selector)[:3]
            reviews = [review.text.strip() for review in review_elements if review and review.text.strip()]
        except Exception as e_reviews:
            print(f"Could not extract Flipkart reviews: {e_reviews}")
            reviews = []

        print(f"Finished scraping Flipkart: Name='{product_name}', Price='{price}', Rating='{rating}'")

        final_price = float(price) if isinstance(price, str) and price.replace('.', '', 1).isdigit() else 0.0
        final_rating = float(rating) if isinstance(rating, str) and rating.replace('.', '', 1).isdigit() else 0.0
        final_reviews_count = int(reviews_count) if isinstance(reviews_count, str) and reviews_count.isdigit() else 0

        return {
            'platform': 'Flipkart', 'name': product_name, 'price': final_price, 'rating': final_rating,
            'reviews_count': final_reviews_count, 'description': description, 'image_url': image_url,
            'category': category, 'url': url, 'reviews': reviews
        }
    except Exception as e:
        print(f"General Error scraping Flipkart product details: {e}")
        return {
            'platform': 'Flipkart','name': "Error fetching product", 'price': 0.0, 'rating': 0.0,
            'reviews_count': 0, 'description': "Error fetching product details", 'image_url': "",
            'category': "", 'url': url, 'reviews': []
        }
    finally:
        if driver:
            driver.quit()

# --- Find product on Amazon (Updated based on second file approach) ---
def find_amazon_product(product_name):
    driver = setup_driver()
    product_url = None
    
    try:
        # Construct and navigate to search URL
        search_url = f'https://www.amazon.in/s?k={product_name.replace(" ", "+")}'
        print(f"Navigating to Amazon Search URL: {search_url}")
        driver.get(search_url)

        # Wait for search results with consistent timeout
        wait_selector = 'div[data-component-type="s-search-result"]'
        print(f"Waiting for Amazon search results: {wait_selector}")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
        )
        print("Amazon search results found.")
        
        # Use a waiting strategy instead of sleep
        WebDriverWait(driver, 5).until(
            EC.visibility_of_all_elements_located((By.CSS_SELECTOR, wait_selector))
        )
        
        # First attempt: BeautifulSoup approach
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        product_containers = soup.select('div[data-component-type="s-search-result"]')
        
        for product in product_containers:
            link_element = product.select_one('a.a-link-normal.s-no-outline')
            if link_element and link_element.get('href'):
                href = link_element.get('href')
                if href and 'slredirect' not in href:
                    product_url = href
                    if not product_url.startswith('https://'):
                        product_url = f'https://www.amazon.in{product_url}'
                    print(f"Found valid Amazon product link: {product_url}")
                    break
        
        # Fallback: Selenium approach if BeautifulSoup didn't find anything
        if not product_url:
            results = driver.find_elements(By.CSS_SELECTOR, wait_selector)
            for product in results:
                try:
                    link_element = product.find_element(By.CSS_SELECTOR, 'a.a-link-normal.s-no-outline')
                    href = link_element.get_attribute('href')
                    if href and 'slredirect' not in href and href.startswith('https://www.amazon.in'):
                        product_url = href
                        print(f"Found valid Amazon product link: {product_url}")
                        break
                except Exception as e:
                    # Skip this product if link cannot be found
                    continue

        return product_url

    except Exception as e:
        print(f"Error finding Amazon product link: {e}")
        return None
    finally:
        if driver:
            driver.quit()


def get_amazon_product_details(url):
    driver = setup_driver()
    
    # Initialize with default values
    product_data = {
        'platform': 'Amazon',
        'name': "Product name not found",
        'price': 0.0,
        'rating': 0.0,
        'reviews_count': 0,
        'description': "No description available",
        'image_url': "",
        'category': "Unknown",
        'url': url,
        'reviews': []
    }
    
    try:
        print(f"Navigating to Amazon URL: {url}")
        driver.get(url)
        
        # Use wait instead of sleep
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Create a WebDriverWait object with a consistent timeout
        wait = WebDriverWait(driver, 10)
        short_wait = WebDriverWait(driver, 5)
        
        # Extract product name
        try:
            name_element = wait.until(EC.presence_of_element_located((By.ID, 'productTitle')))
            product_data['name'] = name_element.text.strip()
            print(f"Found product name: {product_data['name']}")
        except Exception as e:
            print(f"Could not extract Amazon product name: {e}")
        
        # Extract price with multiple selectors
        price_selectors = [
            '.a-price .a-offscreen',
            'span.a-price-whole',
            '.priceToPay .a-offscreen',
            'span[data-a-color="price"] span.a-offscreen',
            '#priceblock_ourprice',
            '#priceblock_dealprice',
            '#price'
        ]
        
        for selector in price_selectors:
            try:
                price_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for price_element in price_elements:
                    price_text = price_element.get_attribute('textContent') or price_element.text
                    if price_text:
                        price_text = price_text.strip()
                        cleaned_price = re.sub(r'[^\d.]', '', price_text)
                        if cleaned_price and cleaned_price.replace('.', '', 1).isdigit() and float(cleaned_price) > 0:
                            product_data['price'] = float(cleaned_price)
                            print(f"Found price using selector '{selector}': {product_data['price']}")
                            break
                if product_data['price'] > 0:
                    break
            except Exception:
                continue
        
        # Extract rating
        try:
            rating_elements = short_wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'span.a-icon-alt'))
            )
            if rating_elements:
                rating_text = rating_elements[0].get_attribute('textContent')
                if rating_text:
                    rating_match = re.search(r'(\d+(?:\.\d+)?)\s+out\s+of\s+5', rating_text)
                    if rating_match:
                        product_data['rating'] = float(rating_match.group(1))
                        print(f"Found rating: {product_data['rating']}")
        except Exception as e:
            print(f"Could not extract Amazon rating: {e}")
        
        # Extract reviews count
        try:
            reviews_count_element = driver.find_element(By.ID, 'acrCustomerReviewText')
            reviews_count_text = reviews_count_element.text.strip()
            reviews_count_match = re.search(r'(\d+(?:,\d+)*)', reviews_count_text)
            if reviews_count_match:
                product_data['reviews_count'] = int(reviews_count_match.group(1).replace(',', ''))
                print(f"Found reviews count: {product_data['reviews_count']}")
        except Exception as e:
            print(f"Could not extract Amazon reviews count: {e}")
        
        # Extract description - try multiple approaches
        try:
            # First try: Product description
            try:
                description_element = driver.find_element(By.ID, 'productDescription')
                product_data['description'] = description_element.text.strip()
            except:
                # Second try: Feature bullets
                try:
                    bullets_element = driver.find_element(By.CSS_SELECTOR, '#feature-bullets')
                    items = bullets_element.find_elements(By.CSS_SELECTOR, 'li span.a-list-item')
                    bullet_points = [item.text.strip() for item in items if item.text.strip()]
                    if bullet_points:
                        product_data['description'] = "\n".join(bullet_points)
                    else:
                        product_data['description'] = bullets_element.text.strip()
                except Exception as e:
                    print(f"Could not extract Amazon description: {e}")
        except Exception as e:
            print(f"Error in description extraction: {e}")
        
        # Extract image URL
        try:
            # Try main image first
            try:
                image_element = driver.find_element(By.ID, 'landingImage')
                image_url = image_element.get_attribute('src') or image_element.get_attribute('data-old-hires')
                if image_url and 'grey-pixel' not in image_url and 'spinner' not in image_url:
                    product_data['image_url'] = image_url
            except:
                # Try alternative image
                try:
                    image_element = driver.find_element(By.ID, 'imgBlkFront')
                    product_data['image_url'] = image_element.get_attribute('src')
                except Exception as e:
                    print(f"Could not extract Amazon image: {e}")
        except Exception as e:
            print(f"Error in image extraction: {e}")
        
        # Extract category
        try:
            # Try breadcrumb navigation first
            try:
                category_element = driver.find_element(By.CSS_SELECTOR, '#wayfinding-breadcrumbs_feature_div ul li:last-of-type a')
                product_data['category'] = category_element.text.strip()
            except:
                # Try alternative category links
                try:
                    category_elements = driver.find_elements(By.CSS_SELECTOR, 'a.a-link-normal.a-color-tertiary')
                    valid_categories = [el.text.strip() for el in category_elements if len(el.text.strip()) > 3]
                    if valid_categories:
                        product_data['category'] = valid_categories[0]
                except Exception as e:
                    print(f"Could not extract Amazon category: {e}")
        except Exception as e:
            print(f"Error in category extraction: {e}")
        
        # Extract reviews
        try:
            # Wait for reviews section to load
            short_wait.until(EC.presence_of_element_located((By.ID, "reviewsMedley")))
            
            # Use BeautifulSoup for more reliable parsing
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            review_elements = soup.select("div[data-hook='review-collapsed'] span")[:3]
            product_data['reviews'] = [review.text.strip() for review in review_elements if review and review.text.strip()]
            print(f"Found {len(product_data['reviews'])} reviews")
        except Exception as e:
            print(f"Could not extract Amazon reviews: {e}")
        
        print(f"Finished scraping Amazon: Name='{product_data['name']}', Price='{product_data['price']}', Rating='{product_data['rating']}'")
        return product_data
        
    except Exception as e:
        print(f"General error scraping Amazon product details: {e}")
        return product_data
    finally:
        if driver:
            driver.quit()

# --- Comparison Logic (No changes needed) ---
def compare_products(flipkart_data, amazon_data):
    comparison = {}
    f_price = flipkart_data.get('price', 0.0)
    a_price = amazon_data.get('price', 0.0)
    f_rating = flipkart_data.get('rating', 0.0)
    a_rating = amazon_data.get('rating', 0.0)
    f_rev_count = flipkart_data.get('reviews_count', 0)
    a_rev_count = amazon_data.get('reviews_count', 0)

    # Price comparison
    if f_price < a_price and f_price > 0:
        comparison['price_winner'] = 'Flipkart'
        comparison['price_diff'] = a_price - f_price
        comparison['price_diff_percent'] = (comparison['price_diff'] / a_price) * 100 if a_price > 0 else 0
    elif a_price < f_price and a_price > 0:
        comparison['price_winner'] = 'Amazon'
        comparison['price_diff'] = f_price - a_price
        comparison['price_diff_percent'] = (comparison['price_diff'] / f_price) * 100 if f_price > 0 else 0
    else:
        comparison['price_winner'] = 'Equal' if f_price > 0 and a_price > 0 else 'Unavailable'
        comparison['price_diff'] = 0
        comparison['price_diff_percent'] = 0

    # Rating comparison
    if f_rating > a_rating:
        comparison['rating_winner'] = 'Flipkart'
    elif a_rating > f_rating:
        comparison['rating_winner'] = 'Amazon'
    else:
        comparison['rating_winner'] = 'Equal' if f_rating > 0 and a_rating > 0 else 'Unavailable'

    # Reviews count comparison
    if f_rev_count > a_rev_count:
        comparison['reviews_count_winner'] = 'Flipkart'
    elif a_rev_count > f_rev_count:
        comparison['reviews_count_winner'] = 'Amazon'
    else:
        comparison['reviews_count_winner'] = 'Equal' if f_rev_count > 0 and a_rev_count > 0 else 'Unavailable'

    # Overall recommendation
    score_flipkart = 0
    score_amazon = 0
    if comparison.get('price_winner') == 'Flipkart': score_flipkart += 3
    elif comparison.get('price_winner') == 'Amazon': score_amazon += 3
    if comparison.get('rating_winner') == 'Flipkart': score_flipkart += 2
    elif comparison.get('rating_winner') == 'Amazon': score_amazon += 2
    if comparison.get('reviews_count_winner') == 'Flipkart': score_flipkart += 1
    elif comparison.get('reviews_count_winner') == 'Amazon': score_amazon += 1

    if score_flipkart > score_amazon: comparison['overall_winner'] = 'Flipkart'
    elif score_amazon > score_flipkart: comparison['overall_winner'] = 'Amazon'
    else: comparison['overall_winner'] = 'Similar'

    return comparison

# --- Data Saving Logic (No changes needed, but ensure data types match DB) ---
def save_product_data(product_data):
    # Ensure data exists and has minimum requirements
    if not product_data or 'name' not in product_data or product_data['name'] == "Error fetching product":
         print("Skipping save for invalid product data.")
         return None, None # Indicate failure

    conn = get_db_connection()
    c = conn.cursor()
    product_id = None
    listing_id = None

    try:
        # Get platform ID
        c.execute("SELECT platform_id FROM PLATFORM WHERE platform_name = ?", (product_data['platform'],))
        platform_result = c.fetchone()
        if not platform_result:
             print(f"Error: Platform '{product_data['platform']}' not found in database.")
             conn.close()
             return None, None
        platform_id = platform_result['platform_id']

        # Prepare data, ensuring types are correct
        p_name = product_data.get('name', 'Unknown Product')
        p_desc = product_data.get('description', '')
        p_cat = product_data.get('category', 'Unknown')
        p_link = product_data.get('url', '')
        p_price = product_data.get('price', 0.0) # Already float from getter
        p_rating_float = product_data.get('rating', 0.0) # Already float from getter
        # Storing overall rating in REVIEW table might be redundant, maybe store 0 or link to product?
        p_rating_int = int(p_rating_float) # Assuming REVIEW.rating is INTEGER

        # Check if product exists (using case-insensitive search might be better)
        c.execute("SELECT product_id FROM PRODUCT WHERE lower(product_name) = lower(?)", (p_name,))
        product = c.fetchone()

        if product:
            product_id = product['product_id']
            # Optionally update product details if they are more complete now
            # For simplicity, we'll just use the existing product ID
            # print(f"Found existing product ID: {product_id} for '{p_name}'")
        else:
            # Insert new product
            c.execute("""
                INSERT INTO PRODUCT (product_name, product_description, category)
                VALUES (?, ?, ?)
            """, (p_name, p_desc, p_cat))
            product_id = c.lastrowid
            # print(f"Inserted new product ID: {product_id} for '{p_name}'")

        # Check if listing exists
        c.execute("""
            SELECT listing_id FROM PRODUCT_LISTING
            WHERE product_id = ? AND platform_id = ?
        """, (product_id, platform_id))
        listing = c.fetchone()

        if listing:
            listing_id = listing['listing_id']
            # Update product link if it changed (unlikely needed often)
            c.execute("""
                UPDATE PRODUCT_LISTING SET product_link = ? WHERE listing_id = ?
            """, (p_link, listing_id))
            # print(f"Found existing listing ID: {listing_id}")
        else:
            # Insert new listing
            c.execute("""
                INSERT INTO PRODUCT_LISTING (product_id, platform_id, product_link)
                VALUES (?, ?, ?)
            """, (product_id, platform_id, p_link))
            listing_id = c.lastrowid
            # print(f"Inserted new listing ID: {listing_id}")

        # Add price history if price is valid
        if p_price > 0:
            c.execute("""
                INSERT INTO PRICE_HISTORY (listing_id, price_value, timestamp)
                VALUES (?, ?, ?)
            """, (listing_id, p_price, datetime.now()))
            # print(f"Inserted price history: {p_price}")

        # Save reviews - Check if reviews list is not empty
        if product_data.get('reviews'):
            for review_text in product_data['reviews']:
                 if review_text: # Ensure review text is not empty
                     # Storing overall product rating with each review text - consider if needed
                     c.execute("""
                         INSERT OR IGNORE INTO REVIEW (listing_id, review_text, rating, review_date)
                         VALUES (?, ?, ?, ?)
                     """, (listing_id, review_text, p_rating_int, datetime.now()))

        conn.commit()
        print(f"Successfully saved/updated data for listing ID: {listing_id}")

    except sqlite3.Error as db_e:
        print(f"Database error in save_product_data: {db_e}")
        conn.rollback() # Rollback changes on error
        return None, None # Indicate failure
    except Exception as e:
        print(f"Error in save_product_data: {e}")
        conn.rollback()
        return None, None # Indicate failure
    finally:
        conn.close()

    return product_id, listing_id

# --- Context Processor (No changes) ---
@app.context_processor
def inject_current_year():
    return {'current_year': datetime.now().year}

# --- Flask Routes (No significant changes, ensure data is handled) ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    product_name = request.form.get('product_name')
    if not product_name:
        flash('Please enter a product name')
        return redirect(url_for('index'))

    flipkart_data = None
    amazon_data = None
    flipkart_listing_id = None
    amazon_listing_id = None
    comparison = {}
    
    # Create cache key for this search
    cache_key = f"search_{product_name.lower().strip()}"
    
    # Check if results are in cache
    cached_result = get_from_cache(cache_key)
    if cached_result:
        print("Returning cached search results")
        return render_template('results.html', **cached_result)
    
    # If not in cache, perform parallel scraping
    try:
        start_time = time.time()
        print("\n--- Starting Parallel Product Search ---")
        
        # Create a thread pool
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit both scraping tasks to run in parallel
            flipkart_future = executor.submit(get_flipkart_data, product_name)
            amazon_future = executor.submit(get_amazon_data, product_name)
            
            # Retrieve results as they complete
            for future in as_completed([flipkart_future, amazon_future]):
                result = future.result()
                if result and 'platform' in result:
                    if result['platform'] == 'Flipkart':
                        flipkart_data = result
                        if flipkart_data and flipkart_data['name'] != "Error fetching product":
                            _, flipkart_listing_id = save_product_data(flipkart_data)
                    elif result['platform'] == 'Amazon':
                        amazon_data = result
                        if amazon_data and amazon_data['name'] != "Error fetching product":
                            _, amazon_listing_id = save_product_data(amazon_data)
        
        # Ensure both data dictionaries exist before comparing
        if flipkart_data and amazon_data and flipkart_data.get('name') != "Error fetching product" and amazon_data.get('name') != "Error fetching product":
            comparison = compare_products(flipkart_data, amazon_data)
        else:
            # Set default values if any data is missing
            if not flipkart_data:
                flipkart_data = {'name': "Product not found", 'platform': 'Flipkart'}
                flash('Could not find product on Flipkart.')
            if not amazon_data:
                amazon_data = {'name': "Product not found", 'platform': 'Amazon'}
                flash('Could not find product on Amazon.')
            if comparison == {}:
                flash("Could not compare products due to missing data.")
        
        # Package the result data
        result_data = {
            'flipkart': flipkart_data,
            'amazon': amazon_data,
            'comparison': comparison,
            'flipkart_listing_id': flipkart_listing_id,
            'amazon_listing_id': amazon_listing_id
        }
        
        # Cache the results
        save_to_cache(cache_key, result_data, 3600) # Cache for 1 hour
        
        print(f"--- Search Complete in {time.time() - start_time:.2f} seconds ---")
        return render_template('results.html', **result_data)

    except Exception as e:
        flash(f'An unexpected error occurred during search: {str(e)}')
        print(f"Error in /search route: {e}")
        return redirect(url_for('index'))


def get_flipkart_data(product_name):
    try:
        print("\n--- Starting Flipkart Search ---")
        flipkart_url = find_flipkart_product(product_name)
        if flipkart_url:
            return get_flipkart_product_details(flipkart_url)
        return {'name': "Product not found", 'platform': 'Flipkart'}
    except Exception as e:
        print(f"Error in Flipkart search: {e}")
        return {'name': "Error fetching product", 'platform': 'Flipkart'}

def get_amazon_data(product_name):
    try:
        print("\n--- Starting Amazon Search ---")
        amazon_url = find_amazon_product(product_name)
        if amazon_url:
            return get_amazon_product_details(amazon_url)
        return {'name': "Product not found", 'platform': 'Amazon'}
    except Exception as e:
        print(f"Error in Amazon search: {e}")
        return {'name': "Error fetching product", 'platform': 'Amazon'}

# --- User Auth & Tracking Routes (No changes needed here) ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if not username or not email or not password:
             flash('All fields are required.')
             return redirect(url_for('register'))

        conn = get_db_connection()
        c = conn.cursor()
        # Check if user exists
        c.execute("SELECT user_id FROM USER WHERE username = ? OR email = ?", (username, email))
        user = c.fetchone()
        if user:
            flash('Username or email already exists.')
            conn.close()
            return redirect(url_for('register'))

        # Create new user
        try:
             c.execute("""
                 INSERT INTO USER (username, email, password_hash, created_at)
                 VALUES (?, ?, ?, ?)
             """, (username, email, generate_password_hash(password), datetime.now()))
             conn.commit()
             flash('Registration successful! Please login.')
             return redirect(url_for('login'))
        except sqlite3.Error as e:
             flash(f'Database error during registration: {e}')
             conn.rollback()
             return redirect(url_for('register'))
        finally:
             conn.close()

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
             flash('Username and password are required.')
             return redirect(url_for('login'))

        conn = get_db_connection()
        c = conn.cursor()
        # Check if user exists
        c.execute("SELECT user_id, username, password_hash FROM USER WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()

        if not user or not check_password_hash(user['password_hash'], password):
            flash('Invalid username or password.')
            return redirect(url_for('login'))

        # Set session
        session['user_id'] = user['user_id']
        session['username'] = user['username']
        flash('Login successful!')
        return redirect(url_for('index'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('Logged out successfully')
    return redirect(url_for('index'))

@app.route('/track', methods=['POST'])
def track_price():
    if 'user_id' not in session:
        flash('Please login to track prices.')
        return redirect(url_for('login'))

    listing_id = request.form.get('listing_id')
    threshold_str = request.form.get('threshold', '').strip()
    
    # Get the original URL that sent the form (likely the results page)
    original_url = request.form.get('redirect_url') or request.referrer or url_for('index')

    if not listing_id:
         flash('Invalid product listing selected.')
         return redirect(original_url)

    # Validate threshold
    threshold = None
    if threshold_str:
        try:
            threshold = float(threshold_str)
            if threshold < 0:
                 flash('Notification threshold cannot be negative.')
                 return redirect(original_url)
        except ValueError:
            flash('Invalid notification threshold entered.')
            return redirect(original_url)

    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Check if already actively tracking
        c.execute("""
            SELECT tracking_id FROM PRICE_TRACKING
            WHERE user_id = ? AND listing_id = ? AND is_active = 1
        """, (session['user_id'], listing_id))
        existing_tracking = c.fetchone()

        if existing_tracking:
            flash('You are already actively tracking this product.')
        else:
            # Check if inactive tracking exists to potentially reactivate/update
            c.execute("""
                 SELECT tracking_id FROM PRICE_TRACKING
                 WHERE user_id = ? AND listing_id = ? AND is_active = 0
            """, (session['user_id'], listing_id))
            inactive_tracking = c.fetchone()

            if inactive_tracking:
                 # Update existing inactive record
                 c.execute("""
                      UPDATE PRICE_TRACKING SET is_active = 1, notification_threshold = ?, created_at = ?
                      WHERE tracking_id = ?
                 """, (threshold, datetime.now(), inactive_tracking['tracking_id']))
                 flash('Price tracking re-enabled for this product.')
            else:
                 # Add new tracking record
                 c.execute("""
                     INSERT INTO PRICE_TRACKING (user_id, listing_id, created_at, is_active, notification_threshold)
                     VALUES (?, ?, ?, ?, ?)
                 """, (session['user_id'], listing_id, datetime.now(), True, threshold))
                 flash('Price tracking enabled for this product.')

            conn.commit()

    except sqlite3.Error as e:
         flash(f"Database error: {e}")
         conn.rollback()
    finally:
         conn.close()

    # Redirect back to the original URL
    return redirect(url_for('price_history'))
    # return redirect(request.referrer or url_for('index'))


@app.route('/history')
def price_history():
    if 'user_id' not in session:
        flash('Please login to view price history.')
        return redirect(url_for('login'))

    conn = get_db_connection()
    c = conn.cursor()
    products_history = []
    try:
        # Get tracked products for the user
        c.execute("""
            SELECT pt.tracking_id, pt.listing_id, pt.created_at, pt.notification_threshold, pt.is_active,
                   p.product_name, pl.product_link, plat.platform_name
            FROM PRICE_TRACKING pt
            JOIN PRODUCT_LISTING pl ON pt.listing_id = pl.listing_id
            JOIN PRODUCT p ON pl.product_id = p.product_id
            JOIN PLATFORM plat ON pl.platform_id = plat.platform_id
            WHERE pt.user_id = ?
            ORDER BY pt.created_at DESC
        """, (session['user_id'],))
        tracked_products = c.fetchall()

        # Get price history for each tracked product
        for product in tracked_products:
            c.execute("""
                SELECT ph.price_value, ph.timestamp
                FROM PRICE_HISTORY ph
                WHERE ph.listing_id = ?
                ORDER BY ph.timestamp DESC
                LIMIT 50 -- Limit history points per product for performance
            """, (product['listing_id'],))
            history = c.fetchall()

            products_history.append({
                'tracking_id': product['tracking_id'],
                'product_name': product['product_name'],
                'platform': product['platform_name'],
                'product_link': product['product_link'],
                'threshold': product['notification_threshold'],
                'is_active': product['is_active'],
                'history': history
            })
    except sqlite3.Error as e:
         flash(f"Database error fetching history: {e}")
    finally:
         conn.close()

    return render_template('history.html', products=products_history)

@app.route('/toggle_tracking/<int:tracking_id>')
def toggle_tracking(tracking_id):
    if 'user_id' not in session:
        flash('Please login to manage tracking.')
        return redirect(url_for('login'))

    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Get current status, ensuring it belongs to the logged-in user
        c.execute("SELECT is_active FROM PRICE_TRACKING WHERE tracking_id = ? AND user_id = ?",
                  (tracking_id, session['user_id']))
        result = c.fetchone()

        if result:
            # Toggle status
            new_status = not result['is_active']
            c.execute("UPDATE PRICE_TRACKING SET is_active = ? WHERE tracking_id = ?",
                      (new_status, tracking_id))
            conn.commit()
            status_text = "enabled" if new_status else "disabled"
            flash(f"Price tracking {status_text} for this product.")
        else:
            flash("Tracking record not found or access denied.")
    except sqlite3.Error as e:
        flash(f"Database error: {e}")
        conn.rollback()
    finally:
        conn.close()

    return redirect(url_for('price_history'))

@app.route('/delete_tracking/<int:tracking_id>')
def delete_tracking(tracking_id):
    if 'user_id' not in session:
        flash('Please login to manage tracking.')
        return redirect(url_for('login'))

    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Delete tracking record, ensuring it belongs to the logged-in user
        c.execute("DELETE FROM PRICE_TRACKING WHERE tracking_id = ? AND user_id = ?",
                  (tracking_id, session['user_id']))

        if c.rowcount > 0:
            conn.commit()
            flash("Price tracking record deleted.")
        else:
            flash("Tracking record not found or access denied.")
    except sqlite3.Error as e:
        flash(f"Database error: {e}")
        conn.rollback()
    finally:
        conn.close()

    return redirect(url_for('price_history'))

# --- Main Execution ---
if __name__ == '__main__':
    init_db()
    # Consider using Waitress or Gunicorn for production instead of debug=True
    configure_app(app)
    
    # Use Waitress for production
    try:
        from waitress import serve
        print("Starting Waitress server...")
        serve(app, host='0.0.0.0', port=5001, threads=4)
    except ImportError:
        # Fallback to Flask development server
        print("Waitress not available. Using Flask development server (not recommended for production)")
        app.run(host='0.0.0.0', port=5001, debug=False)
     # Running on different port just in case