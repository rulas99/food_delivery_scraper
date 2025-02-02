from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (TimeoutException, NoSuchElementException, 
                                        ElementClickInterceptedException, StaleElementReferenceException)
from time import sleep
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class WebScraper:
    def __init__(self, timeout=10):
        options = webdriver.ChromeOptions()
        #options.add_argument("--headless")  # para evitar abrir el navegador si solo necesitas scraping
        self.driver = webdriver.Chrome(options=options)
        self.timeout = timeout
        self.driver.implicitly_wait(2)

    def navigate_to_url(self, url):
        logging.info(f"Navegando a la URL: {url}")
        try:
            self.driver.get(url)
        except Exception as e:
            logging.error(f"Error al cargar la URL {url}: {e}")
            self.driver.quit()

    def click_element(self, xpath, sleep_time=1):
        element_text = None
        try:
            element = WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            sleep(sleep_time)
            element_text = element.text
            element.click()
            logging.info(f"Elemento en {xpath} clickeado correctamente.")
        except (TimeoutException, ElementClickInterceptedException, StaleElementReferenceException) as e:
            logging.error(f"No se pudo hacer clic en el elemento en {xpath}: {e}")
            self.driver.quit()
            
        return element_text

    def enter_address(self, address, input_xpath, selection_xpath, sleep_time=1):
        final_address = None
        try:
            address_input = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.XPATH, input_xpath))
            )
            sleep(sleep_time)
            address_input.send_keys(address)
            sleep(sleep_time)
            final_address = self.click_element(selection_xpath)
            logging.info("Dirección ingresada correctamente.")
        except TimeoutException:
            logging.error("No se pudo encontrar el campo de dirección.")
            
        return final_address

    def scrape_cards(self, cards_xpath, aditional_info=None, sleep_time=1):
        results = []
        try:
            cards_container = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.XPATH, cards_xpath))
            )
            sleep(sleep_time)
            cards = cards_container.find_elements(By.XPATH, './div')
            for card in cards:
                try:
                    text = card.text
                    href = card.find_element(By.TAG_NAME, 'a').get_attribute('href')
                    results.append({
                        "text": text,
                        "href": href,
                        **aditional_info
                    })
                except NoSuchElementException:
                    logging.warning("No se encontró enlace en una tarjeta.")
            logging.info(f"Scraping completado. Total de tarjetas: {len(results)}")
        except TimeoutException:
            logging.error("No se excedió el tiempo de espera.")
        except StaleElementReferenceException:
            logging.error("Se perdió la referencia a un elemento.")
        except Exception as e:
            logging.error(f"Error inesperado: {e}")
        return results

    def close(self):
        self.driver.quit()
        
    def get_html_source(self):
        return self.driver.page_source