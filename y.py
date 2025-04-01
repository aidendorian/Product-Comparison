from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import random
import time

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

def scrape_flipkart(product_name):
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=options)
    
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
                    price = "N/A"

            print(f"Price: {price}")
            print(f"Product Link: {product_link}")

        except:
            driver.quit()
            return

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
        except:
            reviews = []

        print(f"Product Name: {product_name}")
        print(f"Rating: {rating}")

        for i, review in enumerate(reviews, 1):
            print(f"Review {i}: {review}")

    finally:
        driver.quit()

def scrape_amazon(product_name):
    driver = setup_driver()

    try:
        driver.get(f'https://www.amazon.in/s?k={product_name.replace(" ", "+")}')

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-cel-widget="search_result_4"]'))
        )
        time.sleep(random.uniform(1, 3))

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        product = soup.select_one('div[data-cel-widget="search_result_4"]')

        if not product:
            return

        name_element = product.select_one("h2 span")
        product_name = name_element.text.strip() if name_element else "N/A"

        product_link_element = product.select_one("a.a-link-normal")
        product_link = "N/A"
        if product_link_element and product_link_element.get("href"):
            product_link = product_link_element["href"]
            if not product_link.startswith("http"):
                product_link = f"https://www.amazon.in{product_link}"

        price_element = product.select_one(".a-price .a-offscreen")
        price = price_element.text.strip() if price_element else "N/A"

        rating_element = product.select_one(".a-icon-alt")
        rating = rating_element.text.strip() if rating_element else "N/A"

        print(f"Product Name: {product_name}")
        print(f"Price: {price}")
        print(f"Product Link: {product_link}")
        print(f"Rating: {rating}")

        if product_link == "N/A":
            return

        driver.get(product_link)
        time.sleep(random.uniform(2, 4))

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "cm-cr-dp-review-list"))
            )
        except:
            return

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        review_elements = soup.select("div[data-hook='review-collapsed'] span")[:3]
        reviews = [review.text.strip() for review in review_elements]

        for i, review in enumerate(reviews):
            print(f"Review {i+1}: {review}")

    finally:
        driver.quit()

def main():
    product_name = input("Enter the product name: ").strip()
    if not product_name:
        print("Please enter a valid product name.")
        return

    scrape_flipkart(product_name)
    scrape_amazon(product_name)

if __name__ == "__main__":
    main()