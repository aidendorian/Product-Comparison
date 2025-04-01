import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import random
import time
import logging
from typing import Optional
from fake_useragent import UserAgent

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_driver() -> webdriver.Chrome:
    """Set up a headless Chrome driver with common options."""
    ua = UserAgent()
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument(f"user-agent={ua.random}")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    return driver

def scrape_flipkart(product_name: str):
    """Scrape Flipkart for product details including name, price, link, rating, and reviews."""
    
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")  
    options.add_argument("--headless=new")  # Run in headless mode
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=options)

    try:
        flipkart_url = f'https://www.flipkart.com/search?q={product_name.replace(" ", "+")}'
        driver.get(flipkart_url)

        try:
            close_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(text(),"✕")]'))
            )
            close_button.click()
        except:
            print("No popup appeared")

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'a.CGtC98, a.VJA3rP'))
        )

        try:
            first_product = driver.find_element(By.CSS_SELECTOR, 'a.CGtC98, a.VJA3rP')
            product_link = first_product.get_attribute("href")

            try:
                price = driver.find_element(By.CSS_SELECTOR, "div.Nx9bqj._4b5DiR").text.strip()
            except:
                try:
                    price = driver.find_element(By.CSS_SELECTOR, "div.Nx9bqj").text.strip()
                except:
                    print("❌ Price not found")
                    price = "N/A"

            print(f"Price: {price}")
            print(f"Product Link: {product_link}")

        except Exception as e:
            print("Error extracting product details:", e)
            print(driver.page_source)
            driver.quit()
            return None

        driver.get(product_link)

        try:
            product_name = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "span.VU-ZEz"))
            ).text.strip()
        except:
            product_name = "N/A"
        try:
            rating = driver.find_element(By.CSS_SELECTOR, "div.ipqd2A").text.strip()
        except:
            rating = "N/A"
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.ZmyHeo"))
            )

            review_elements = driver.find_elements(By.CSS_SELECTOR, "div.ZmyHeo")[:3]
            reviews = [review.text.strip() for review in review_elements]

            print("\n📌 Extracted Reviews:")
            for i, review in enumerate(reviews, 1):
                print(f"{i}. {review}")

        except Exception as e:
            print("Error extracting reviews:", e)
            reviews = []

        print(f"\n🛒 Product Name: {product_name}")
        print(f"Rating: {rating}")

    except Exception as e:
        print("Flipkart scrape failed:", e)

    finally:
        driver.quit()

def scrape_amazon(product_name: str) -> dict:
    driver = None
    try:
        driver = setup_driver()
        amazon_url = f'https://www.amazon.in/s?k={product_name.replace(" ", "+")}'
        logger.info(f"Scraping Amazon for {product_name}")

        driver.get(amazon_url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="listitem"][data-asin]'))
        )
        time.sleep(random.uniform(1, 3))  # Random sleep to avoid detection

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # Ignore Sponsored Ads
        products = soup.select('div[role="listitem"][data-asin]:not([data-component-type="sp-sponsored-result"])')
        if not products:
            logger.error("No product found on Amazon.")
            return {"error": "No product found"}

        first_product = products[0]  # Get the first valid product

        # ✅ Fix Product Name Extraction
        name_element = first_product.select_one("a.a-link-normal.s-line-clamp-2.s-link-style.a-text-normal h2 span")
        product_name = name_element.text.strip() if name_element else "N/A"

        # ✅ Fix Price Extraction
        price_element = first_product.select_one(".a-price .a-offscreen")
        price = price_element.text.strip() if price_element else "N/A"

        # ✅ Fix Product Link Extraction
        product_link = "N/A"
        product_link_element = first_product.select_one('a.a-link-normal.s-line-clamp-2.s-link-style.a-text-normal')

        if product_link_element:
            product_link = product_link_element['href']
            if not product_link.startswith('http'):
                product_link = f"https://www.amazon.in{product_link}"
            logger.info(f"Product Link: {product_link}")
        else:
            logger.error("Product link not found.")

        # ✅ Fix Rating Extraction
        rating_element = first_product.select_one(".a-icon-alt")
        rating = rating_element.text.strip() if rating_element else "N/A"

        logger.info(f"Found Product: {product_name} | Price: {price} | Rating: {rating}")
        logger.info(f"Product Link: {product_link}")

        # 🚨 Handle Missing Product Link
        if product_link == "N/A":
            logger.warning("No valid product link found. Skipping reviews extraction.")
            return {
                "name": product_name,
                "price": price,
                "product_link": product_link,
                "rating": rating,
                "reviews": ["No reviews found"],
            }

        # ✅ Navigate to Product Page
        driver.get(product_link)
        time.sleep(random.uniform(2, 4))  # Random delay

        # ✅ Fix Review Extraction: Wait for Reviews Section
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "span.cr-widget-FocalReviews"))
            )
            logger.info("Reviews section loaded successfully.")
        except Exception as e:
            logger.warning(f"Error waiting for reviews section: {e}")
            return {
                "name": product_name,
                "price": price,
                "product_link": product_link,
                "rating": rating,
                "reviews": ["No reviews found"],
            }

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        review_elements = soup.select("div.review-text-content span")[:3]
        reviews = [review.text.strip() for review in review_elements]
        for i in range(3):
            print(f"Review {i+1}: {reviews[i]}")
        logger.info(f"📌 Extracted {len(reviews)} Reviews")
        return {
            "name": product_name,
            "price": price,
            "product_link": product_link,
            "rating": rating,
            "reviews": reviews if reviews else ["No reviews found"],
        }

    except Exception as e:
        logger.error(f"❌ Amazon scrape failed: {e}")
        return {"error": str(e)}

    finally:
        if driver:
            driver.quit()
            
def main():
    product_name = input("Enter the product name: ").strip()
    if not product_name:
        logger.error("No product name provided")
        print("Please enter a valid product name.")
        return

    scrape_flipkart(product_name)
    scrape_amazon(product_name)

if __name__ == "__main__":
    main()