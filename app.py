from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from datetime import datetime
import re
import os
from werkzeug.security import generate_password_hash, check_password_hash
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import random
import time

app = Flask(__name__)
app.secret_key = os.urandom(24)
DATABASE = 'product_comparison.db'

# Database initialization
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS USER (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username VARCHAR(255) UNIQUE,
        email VARCHAR(255) UNIQUE,
        password_hash VARCHAR(255),
        created_at DATETIME
    )
    ''')
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS PLATFORM (
        platform_id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform_name VARCHAR(255),
        platform_url VARCHAR(255)
    )
    ''')
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS PRODUCT (
        product_id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name VARCHAR(255),
        product_description TEXT,
        category VARCHAR(255)
    )
    ''')
    
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
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS PRICE_HISTORY (
        price_id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_id INTEGER,
        price_value DECIMAL(10,2),
        timestamp DATETIME,
        FOREIGN KEY (listing_id) REFERENCES PRODUCT_LISTING(listing_id)
    )
    ''')
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS REVIEW (
        review_id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_id INTEGER,
        review_text TEXT,
        rating INTEGER,
        review_date DATETIME,
        FOREIGN KEY (listing_id) REFERENCES PRODUCT_LISTING(listing_id)
    )
    ''')
    
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

# Setup WebDriver for scraping
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

    return webdriver.Chrome(options=options)

# Find product on Flipkart based on search query
def find_flipkart_product(product_name):
    driver = setup_driver()
    
    try:
        driver.get(f'https://www.flipkart.com/search?q={product_name.replace(" ", "+")}')
        
        try:
            close_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(text(),"✕")]'))
            )
            close_button.click()
        except:
            pass
        
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'a._1fQZEK, a._2rpwqI, a.s1Q9rs, a._8VNy32'))
        )
        
        first_product = driver.find_element(By.CSS_SELECTOR, 'a._1fQZEK, a._2rpwqI, a.s1Q9rs, a._8VNy32')
        flipkart_url = first_product.get_attribute("href")
        return flipkart_url
    except Exception as e:
        print(f"Error finding Flipkart product: {e}")
        return None
    finally:
        driver.quit()

# Improved Web scraping functions
def get_flipkart_product_details(url):
    driver = setup_driver()
    
    try:
        driver.get(url)
        
        try:
            close_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(text(),"✕")]'))
            )
            close_button.click()
        except:
            pass
        
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'span.B_NuCI'))
        )
        
        # Extract product name
        try:
            product_name = driver.find_element(By.CSS_SELECTOR, 'span.B_NuCI').text.strip()
        except:
            product_name = "Product name not found"
        
        # Extract price
        try:
            price_element = driver.find_element(By.CSS_SELECTOR, 'div._30jeq3._16Jk6d')
            price = price_element.text.strip()
            price = re.sub(r'[^\d.]', '', price)
        except:
            price = "0"
        
        # Extract rating
        try:
            rating_element = driver.find_element(By.CSS_SELECTOR, 'div._3LWZlK')
            rating = rating_element.text.strip()
        except:
            rating = "0"
        
        # Extract reviews count
        try:
            reviews_count_element = driver.find_element(By.CSS_SELECTOR, 'span._2_R_DZ')
            reviews_count = reviews_count_element.text.strip()
            reviews_count = re.search(r'(\d+(?:,\d+)*)\s+reviews', reviews_count)
            reviews_count = reviews_count.group(1).replace(',', '') if reviews_count else "0"
        except:
            reviews_count = "0"
        
        # Extract description
        try:
            description_element = driver.find_element(By.CSS_SELECTOR, 'div._1mXcCf.RmoJUa')
            description = description_element.text.strip()
        except:
            description = "No description available"
        
        # Extract image
        try:
            image_element = driver.find_element(By.CSS_SELECTOR, 'img._396cs4')
            image_url = image_element.get_attribute('src')
        except:
            image_url = ""
        
        # Extract category
        category = "Unknown"  # Flipkart doesn't have clear category tags
        
        # Get reviews
        reviews = []
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.ZmyHeo"))
            )
            review_elements = driver.find_elements(By.CSS_SELECTOR, "div.ZmyHeo")[:3]
            reviews = [review.text.strip() for review in review_elements]
        except:
            pass
        
        return {
            'platform': 'Flipkart',
            'name': product_name,
            'price': float(price) if price.replace('.', '', 1).isdigit() else 0,
            'rating': float(rating) if rating.replace('.', '', 1).isdigit() else 0,
            'reviews_count': int(reviews_count) if reviews_count.isdigit() else 0,
            'description': description,
            'image_url': image_url,
            'category': category,
            'url': url,
            'reviews': reviews
        }
    except Exception as e:
        print(f"Error scraping Flipkart: {e}")
        return {
            'platform': 'Flipkart',
            'name': "Error fetching product",
            'price': 0,
            'rating': 0,
            'reviews_count': 0,
            'description': "Error fetching product details",
            'image_url': "",
            'category': "",
            'url': url,
            'reviews': []
        }
    finally:
        driver.quit()

def find_amazon_product(product_name):
    driver = setup_driver()
    
    try:
        driver.get(f'https://www.amazon.in/s?k={product_name.replace(" ", "+")}')
        
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-component-type="s-search-result"]'))
        )
        time.sleep(random.uniform(1, 3))
        
        product = driver.find_element(By.CSS_SELECTOR, 'div[data-component-type="s-search-result"]')
        link_element = product.find_element(By.CSS_SELECTOR, 'a.a-link-normal.s-no-outline')
        
        if link_element:
            product_url = link_element.get_attribute('href')
            return product_url
        
        return None
    except Exception as e:
        print(f"Error finding Amazon product: {e}")
        return None
    finally:
        driver.quit()

def get_amazon_product_details(url):
    driver = setup_driver()
    
    try:
        driver.get(url)
        time.sleep(random.uniform(2, 4))
        
        # Extract product name
        try:
            product_name = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, 'productTitle'))
            ).text.strip()
        except:
            product_name = "Product name not found"
        
        # Extract price
        try:
            price_element = driver.find_element(By.CSS_SELECTOR, 'span.a-price-whole')
            price = price_element.text.strip()
            price = re.sub(r'[^\d.]', '', price)
        except:
            price = "0"
        
        # Extract rating
        try:
            rating_element = driver.find_element(By.CSS_SELECTOR, 'span.a-icon-alt')
            rating = rating_element.text.strip()
            rating = re.search(r'(\d+(?:\.\d+)?)\s+out\s+of\s+5\s+stars', rating)
            rating = rating.group(1) if rating else "0"
        except:
            rating = "0"
        
        # Extract reviews count
        try:
            reviews_count_element = driver.find_element(By.ID, 'acrCustomerReviewText')
            reviews_count = reviews_count_element.text.strip()
            reviews_count = re.search(r'(\d+(?:,\d+)*)', reviews_count)
            reviews_count = reviews_count.group(1).replace(',', '') if reviews_count else "0"
        except:
            reviews_count = "0"
        
        # Extract description
        try:
            description_element = driver.find_element(By.ID, 'productDescription')
            description = description_element.text.strip()
        except:
            try:
                description_element = driver.find_element(By.CSS_SELECTOR, '#feature-bullets')
                description = description_element.text.strip()
            except:
                description = "No description available"
        
        # Extract image
        try:
            image_element = driver.find_element(By.ID, 'landingImage')
            image_url = image_element.get_attribute('src')
        except:
            image_url = ""
        
        # Extract category
        try:
            category_element = driver.find_element(By.CSS_SELECTOR, 'a.a-link-normal.a-color-tertiary')
            category = category_element.text.strip()
        except:
            category = "Unknown"
        
        # Get reviews
        reviews = []
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "cm-cr-dp-review-list"))
            )
            review_elements = driver.find_elements(By.CSS_SELECTOR, "div[data-hook='review-collapsed'] span")[:3]
            reviews = [review.text.strip() for review in review_elements]
        except:
            pass
        
        return {
            'platform': 'Amazon',
            'name': product_name,
            'price': float(price) if price.replace('.', '', 1).isdigit() else 0,
            'rating': float(rating) if rating.replace('.', '', 1).isdigit() else 0,
            'reviews_count': int(reviews_count) if reviews_count.isdigit() else 0,
            'description': description,
            'image_url': image_url,
            'category': category,
            'url': url,
            'reviews': reviews
        }
    except Exception as e:
        print(f"Error scraping Amazon: {e}")
        return {
            'platform': 'Amazon',
            'name': "Error fetching product",
            'price': 0,
            'rating': 0,
            'reviews_count': 0,
            'description': "Error fetching product details",
            'image_url': "",
            'category': "",
            'url': url,
            'reviews': []
        }
    finally:
        driver.quit()

def compare_products(flipkart_data, amazon_data):
    comparison = {}
    
    # Price comparison
    if flipkart_data['price'] < amazon_data['price'] and flipkart_data['price'] > 0:
        comparison['price_winner'] = 'Flipkart'
        comparison['price_diff'] = amazon_data['price'] - flipkart_data['price']
        comparison['price_diff_percent'] = (comparison['price_diff'] / amazon_data['price']) * 100 if amazon_data['price'] > 0 else 0
    elif amazon_data['price'] < flipkart_data['price'] and amazon_data['price'] > 0:
        comparison['price_winner'] = 'Amazon'
        comparison['price_diff'] = flipkart_data['price'] - amazon_data['price']
        comparison['price_diff_percent'] = (comparison['price_diff'] / flipkart_data['price']) * 100 if flipkart_data['price'] > 0 else 0
    else:
        comparison['price_winner'] = 'Equal' if flipkart_data['price'] > 0 and amazon_data['price'] > 0 else 'Unavailable'
        comparison['price_diff'] = 0
        comparison['price_diff_percent'] = 0
    
    # Rating comparison
    if flipkart_data['rating'] > amazon_data['rating']:
        comparison['rating_winner'] = 'Flipkart'
    elif amazon_data['rating'] > flipkart_data['rating']:
        comparison['rating_winner'] = 'Amazon'
    else:
        comparison['rating_winner'] = 'Equal' if flipkart_data['rating'] > 0 and amazon_data['rating'] > 0 else 'Unavailable'
    
    # Reviews count comparison
    if flipkart_data['reviews_count'] > amazon_data['reviews_count']:
        comparison['reviews_count_winner'] = 'Flipkart'
    elif amazon_data['reviews_count'] > flipkart_data['reviews_count']:
        comparison['reviews_count_winner'] = 'Amazon'
    else:
        comparison['reviews_count_winner'] = 'Equal' if flipkart_data['reviews_count'] > 0 and amazon_data['reviews_count'] > 0 else 'Unavailable'
    
    # Overall recommendation
    score_flipkart = 0
    score_amazon = 0
    
    if comparison['price_winner'] == 'Flipkart':
        score_flipkart += 3  # Price is the most important factor
    elif comparison['price_winner'] == 'Amazon':
        score_amazon += 3
    
    if comparison['rating_winner'] == 'Flipkart':
        score_flipkart += 2
    elif comparison['rating_winner'] == 'Amazon':
        score_amazon += 2
    
    if comparison['reviews_count_winner'] == 'Flipkart':
        score_flipkart += 1
    elif comparison['reviews_count_winner'] == 'Amazon':
        score_amazon += 1
    
    if score_flipkart > score_amazon:
        comparison['overall_winner'] = 'Flipkart'
    elif score_amazon > score_flipkart:
        comparison['overall_winner'] = 'Amazon'
    else:
        comparison['overall_winner'] = 'Equal'
    
    return comparison

def save_product_data(product_data):
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get platform ID
    c.execute("SELECT platform_id FROM PLATFORM WHERE platform_name = ?", (product_data['platform'],))
    platform_id = c.fetchone()['platform_id']
    
    # Check if product exists
    c.execute("SELECT product_id FROM PRODUCT WHERE product_name = ?", (product_data['name'],))
    product = c.fetchone()
    
    if product:
        product_id = product['product_id']
        # Update product details
        c.execute("""
            UPDATE PRODUCT 
            SET product_description = ?, category = ?
            WHERE product_id = ?
        """, (product_data['description'], product_data['category'], product_id))
    else:
        # Insert new product
        c.execute("""
            INSERT INTO PRODUCT (product_name, product_description, category)
            VALUES (?, ?, ?)
        """, (product_data['name'], product_data['description'], product_data['category']))
        product_id = c.lastrowid
    
    # Check if listing exists
    c.execute("""
        SELECT listing_id FROM PRODUCT_LISTING 
        WHERE product_id = ? AND platform_id = ?
    """, (product_id, platform_id))
    listing = c.fetchone()
    
    if listing:
        listing_id = listing['listing_id']
        # Update product link
        c.execute("""
            UPDATE PRODUCT_LISTING 
            SET product_link = ?
            WHERE listing_id = ?
        """, (product_data['url'], listing_id))
    else:
        # Insert new listing
        c.execute("""
            INSERT INTO PRODUCT_LISTING (product_id, platform_id, product_link)
            VALUES (?, ?, ?)
        """, (product_id, platform_id, product_data['url']))
        listing_id = c.lastrowid
    
    # Add price history
    c.execute("""
        INSERT INTO PRICE_HISTORY (listing_id, price_value, timestamp)
        VALUES (?, ?, ?)
    """, (listing_id, product_data['price'], datetime.now()))
    
    # Save reviews
    for review_text in product_data.get('reviews', []):
        c.execute("""
            INSERT INTO REVIEW (listing_id, review_text, rating, review_date)
            VALUES (?, ?, ?, ?)
        """, (listing_id, review_text, product_data['rating'], datetime.now()))
    
    conn.commit()
    conn.close()
    
    return product_id, listing_id

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    product_name = request.form.get('product_name')
    
    if not product_name:
        flash('Please enter a product name')
        return redirect(url_for('index'))
    
    try:
        # Find product on Flipkart
        flipkart_url = find_flipkart_product(product_name)
        
        if not flipkart_url:
            flash('Could not find product on Flipkart')
            return redirect(url_for('index'))
        
        # Get Flipkart product details
        flipkart_data = get_flipkart_product_details(flipkart_url)
        
        # Save Flipkart product data
        save_product_data(flipkart_data)
        
        # Find equivalent product on Amazon
        amazon_url = find_amazon_product(flipkart_data['name'])
        
        if not amazon_url:
            flash('Could not find an equivalent product on Amazon')
            amazon_data = {
                'platform': 'Amazon',
                'name': "Product not found",
                'price': 0,
                'rating': 0,
                'reviews_count': 0,
                'description': "Product not found on Amazon",
                'image_url': "",
                'category': "",
                'url': "",
                'reviews': []
            }
        else:
            # Get Amazon product details
            amazon_data = get_amazon_product_details(amazon_url)
            
            # Save Amazon product data
            save_product_data(amazon_data)
        
        # Compare products
        comparison = compare_products(flipkart_data, amazon_data)
        
        return render_template('results.html', 
                            flipkart=flipkart_data, 
                            amazon=amazon_data, 
                            comparison=comparison)
        
    except Exception as e:
        flash(f'Error searching for product: {str(e)}')
        return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Check if user exists
        c.execute("SELECT * FROM USER WHERE username = ? OR email = ?", (username, email))
        user = c.fetchone()
        
        if user:
            flash('Username or email already exists')
            conn.close()
            return redirect(url_for('register'))
        
        # Create new user
        c.execute("""
            INSERT INTO USER (username, email, password_hash, created_at)
            VALUES (?, ?, ?, ?)
        """, (username, email, generate_password_hash(password), datetime.now()))
        
        conn.commit()
        conn.close()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Check if user exists
        c.execute("SELECT * FROM USER WHERE username = ?", (username,))
        user = c.fetchone()
        
        if not user or not check_password_hash(user['password_hash'], password):
            flash('Invalid username or password')
            conn.close()
            return redirect(url_for('login'))
        
        # Set session
        session['user_id'] = user['user_id']
        session['username'] = user['username']
        
        conn.close()
        
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
        flash('Please login to track prices')
        return redirect(url_for('login'))
    
    listing_id = request.form.get('listing_id')
    threshold = request.form.get('threshold')
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Check if already tracking
    c.execute("""
        SELECT * FROM PRICE_TRACKING 
        WHERE user_id = ? AND listing_id = ? AND is_active = 1
    """, (session['user_id'], listing_id))
    
    if c.fetchone():
        flash('You are already tracking this product')
    else:
        # Add tracking
        c.execute("""
            INSERT INTO PRICE_TRACKING (user_id, listing_id, created_at, is_active, notification_threshold)
            VALUES (?, ?, ?, ?, ?)
        """, (session['user_id'], listing_id, datetime.now(), True, threshold))
        
        flash('Price tracking enabled for this product')
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('index'))

@app.route('/history')
def price_history():
    if 'user_id' not in session:
        flash('Please login to view price history')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get tracked products
    c.execute("""
        SELECT pt.tracking_id, pt.created_at, pt.notification_threshold, pt.is_active,
               p.product_name, pl.product_link, plat.platform_name
        FROM PRICE_TRACKING pt
        JOIN PRODUCT_LISTING pl ON pt.listing_id = pl.listing_id
        JOIN PRODUCT p ON pl.product_id = p.product_id
        JOIN PLATFORM plat ON pl.platform_id = plat.platform_id
        WHERE pt.user_id = ?
    """, (session['user_id'],))
    
    tracked_products = c.fetchall()
    
    # Get price history for each tracked product
    products_history = []
    
    for product in tracked_products:
        c.execute("""
            SELECT ph.price_value, ph.timestamp
            FROM PRICE_HISTORY ph
            WHERE ph.listing_id = (
                SELECT listing_id FROM PRICE_TRACKING 
                WHERE tracking_id = ?
            )
            ORDER BY ph.timestamp DESC
        """, (product['tracking_id'],))
        
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
    
    conn.close()
    
    return render_template('history.html', products=products_history)

@app.route('/toggle_tracking/<int:tracking_id>')
def toggle_tracking(tracking_id):
    if 'user_id' not in session:
        flash('Please login to manage tracking')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get current status
    c.execute("SELECT is_active FROM PRICE_TRACKING WHERE tracking_id = ? AND user_id = ?", 
              (tracking_id, session['user_id']))
    
    result = c.fetchone()
    
    if result:
        # Toggle status
        new_status = not result['is_active']
        c.execute("UPDATE PRICE_TRACKING SET is_active = ? WHERE tracking_id = ?", 
                  (new_status, tracking_id))
        
        status_text = "enabled" if new_status else "disabled"
        flash(f"Price tracking {status_text} for this product")
    else:
        flash("Tracking record not found")
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('price_history'))

@app.route('/delete_tracking/<int:tracking_id>')
def delete_tracking(tracking_id):
    if 'user_id' not in session:
        flash('Please login to manage tracking')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Delete tracking
    c.execute("DELETE FROM PRICE_TRACKING WHERE tracking_id = ? AND user_id = ?", 
              (tracking_id, session['user_id']))
    
    if c.rowcount > 0:
        flash("Price tracking deleted for this product")
    else:
        flash("Tracking record not found")
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('price_history'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)