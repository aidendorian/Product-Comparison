import json
import random
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth
from bs4 import BeautifulSoup

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# User agents list
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
]

def setup_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")

    driver = webdriver.Chrome(options=options)

    # Stealth mode
    stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )

    return driver

def random_sleep(a=1, b=3):
    time.sleep(random.uniform(a, b))

def scrape_flipkart(product_name):
    result = {"platform": "Flipkart", "product_name": product_name, "price": "N/A", "rating": "N/A", "product_link": "N/A", "reviews": []}
    driver = setup_driver()

    try:
        driver.get(f'https://www.flipkart.com/search?q={product_name.replace(" ", "+")}')
        random_sleep()

        # Close login popup
        try:
            close_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(text(),"✕")]'))
            )
            close_button.click()
        except:
            pass  # No popup

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'a.CGtC98, a.VJA3rP'))
        )

        first_product = driver.find_element(By.CSS_SELECTOR, 'a.CGtC98, a.VJA3rP')
        result["product_link"] = first_product.get_attribute("href")

        try:
            price = driver.find_element(By.CSS_SELECTOR, "div.Nx9bqj._4b5DiR").text.strip()
        except:
            try:
                price = driver.find_element(By.CSS_SELECTOR, "div.Nx9bqj").text.strip()
            except:
                price = "N/A"
        result["price"] = price

        driver.get(result["product_link"])
        random_sleep()

        try:
            result["product_name"] = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "span.VU-ZEz"))
            ).text.strip()
        except:
            pass

        try:
            result["rating"] = driver.find_element(By.CSS_SELECTOR, "div.ipqd2A").text.strip()
        except:
            pass

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.ZmyHeo"))
            )
            review_elements = driver.find_elements(By.CSS_SELECTOR, "div.ZmyHeo")[:3]
            result["reviews"] = [review.text.strip() for review in review_elements]
        except:
            pass

    except Exception as e:
        logging.error(f"Flipkart scraping error: {e}")
    finally:
        driver.quit()

    return result

def scrape_amazon(product_name):
    result = {"platform": "Amazon", "product_name": product_name, "price": "N/A", "rating": "N/A", "product_link": "N/A", "reviews": []}
    driver = setup_driver()

    try:
        driver.get(f'https://www.amazon.in/s?k={product_name.replace(" ", "+")}')
        random_sleep()

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-cel-widget="search_result_4"]'))
        )

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        product = soup.select_one('div[data-cel-widget="search_result_4"]')

        if product:
            name_element = product.select_one("h2 span")
            result["product_name"] = name_element.text.strip() if name_element else "N/A"

            product_link_element = product.select_one("a.a-link-normal")
            if product_link_element and product_link_element.get("href"):
                result["product_link"] = f"https://www.amazon.in{product_link_element['href']}"

            price_element = product.select_one(".a-price .a-offscreen")
            result["price"] = price_element.text.strip() if price_element else "N/A"

            rating_element = product.select_one(".a-icon-alt")
            result["rating"] = rating_element.text.strip() if rating_element else "N/A"

            if result["product_link"] != "N/A":
                driver.get(result["product_link"])
                random_sleep(2, 4)

                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "cm-cr-dp-review-list"))
                    )
                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    review_elements = soup.select("div[data-hook='review-collapsed'] span")[:3]
                    result["reviews"] = [review.text.strip() for review in review_elements]
                except:
                    pass

    except Exception as e:
        logging.error(f"Amazon scraping error: {e}")
    finally:
        driver.quit()

    return result

def save_to_json(data, filename="product_data.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logging.info(f"Data saved to {filename}")

def main():
    product_name = input("Enter the product name: ").strip()
    if not product_name:
        logging.error("Please enter a valid product name.")
        return

    with ThreadPoolExecutor() as executor:
        future_flipkart = executor.submit(scrape_flipkart, product_name)
        future_amazon = executor.submit(scrape_amazon, product_name)

        flipkart_data = future_flipkart.result()
        amazon_data = future_amazon.result()

    results = [flipkart_data, amazon_data]

    # Print as clean JSON-style output
    print(json.dumps(results, indent=4, ensure_ascii=False))

    # Optional: save to JSON
    save_to_json(results)

if __name__ == "__main__":
    main()