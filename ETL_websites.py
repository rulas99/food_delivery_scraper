import pandas as pd
from playwright.sync_api import sync_playwright
import concurrent.futures
import os

data = pd.read_csv('results/complete_data_new.csv')
uberStores = pd.Series(data.query('platform == "ubereats"').href.unique())
rappiStores = pd.Series(data.query('platform == "rappi"').href.unique())

# Función para procesar una URL individual con un navegador ya inicializado
def process_uber_url(url, browser):
    page = browser.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded")
        
        # Extract restaurant name
        restaurantName = page.locator('//html/body/div[1]/div[3]/div[1]/div[2]/main/div/div[1]/div/div[3]/div/div/div[1]/h1').text_content()
        # extract tags and rating
        tags = page.locator('//html/body/div[1]/div[3]/div[1]/div[2]/main/div/div[1]/div/div[3]/div/div/div[1]/div/p[1]').text_content()
        # extract address
        xpathAddress = '//html/body/div[1]/div[3]/div[1]/div[2]/main/div/div[1]/div/div[3]/div/div/div[1]/div/p[3]/span'
        if page.locator(xpathAddress).count() > 0:
            address = page.locator(xpathAddress).text_content()
        else:
            address = page.locator('//html/body/div[1]/div[3]/div[1]/div[2]/main/div/div[1]/div/div[3]/div/div/div[1]/div/p[2]/span').text_content()
        # Schedule
        schedule = page.locator('//html/body/div[1]/div[3]/div[1]/div[2]/main/div/div[2]/div/div/div[2]/div[2]/section/div[2]/div').all_text_contents()
        
        data = {
            'restaurantName': restaurantName,
            'tags': tags,
            'address': address,
            'schedule': schedule
        }
        print(f"Processed: {url}")
        return data
    except Exception as e:
        print(f"Error processing {url}: {str(e)}")
        return None
    finally:
        page.close()

# Función para inicializar un navegador y procesar un lote de URLs
def process_batch(urls_batch):
    results = []
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=False)  # Puedes cambiar a True para modo headless
        try:
            for url in urls_batch:
                result = process_uber_url(url, browser)
                if result:
                    results.append(result)
        finally:
            browser.close()
    return results

# Función principal para paralelizar el scraping
def scrape_uber_parallel(urls, max_workers=4, batch_size=5):
    """
    Paraleliza el scraping de URLs de Uber
    
    Args:
        urls: Serie de pandas con las URLs a procesar
        max_workers: Número máximo de workers (procesos paralelos)
        batch_size: Número de URLs a procesar por cada navegador
    
    Returns:
        Lista de diccionarios con los datos extraídos
    """
    all_results = []
    
    # Dividir las URLs en lotes
    url_batches = []
    urls_list = urls.tolist()
    for i in range(0, len(urls_list), batch_size):
        url_batches.append(urls_list[i:i+batch_size])
    
    # Procesar los lotes en paralelo
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        batch_results = list(executor.map(process_batch, url_batches))
    
    # Aplanar los resultados
    for batch in batch_results:
        all_results.extend(batch)
    
    return all_results

# Mantener la función original para compatibilidad
def scrappUber(url):
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=False)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded")
        
        # Extract restaurant name
        restaurantName = page.locator('//html/body/div[1]/div[3]/div[1]/div[2]/main/div/div[1]/div/div[3]/div/div/div[1]/h1').text_content()
        # extract tags and rating
        tags = page.locator('//html/body/div[1]/div[3]/div[1]/div[2]/main/div/div[1]/div/div[3]/div/div/div[1]/div/p[1]').text_content()
        # extract address
        xpathAddress = '//html/body/div[1]/div[3]/div[1]/div[2]/main/div/div[1]/div/div[3]/div/div/div[1]/div/p[3]/span'
        if page.locator(xpathAddress).count()> 0:
            address = page.locator(xpathAddress).text_content()
        else:
            address = page.locator('//html/body/div[1]/div[3]/div[1]/div[2]/main/div/div[1]/div/div[3]/div/div/div[1]/div/p[2]/span').text_content()
        # Schedule
        schedule = page.locator('//html/body/div[1]/div[3]/div[1]/div[2]/main/div/div[2]/div/div/div[2]/div[2]/section/div[2]/div').all_text_contents()
        
        data = {
            'restaurantName': restaurantName,
            'tags': tags,
            'address': address,
            'schedule': schedule
        }
        print(data)
    return data

# Reemplazar la línea original con la versión paralela
# uberStores.apply(scrappUber)
uber_results = scrape_uber_parallel(uberStores)

# Si necesitas convertir los resultados a DataFrame:
# uber_df = pd.DataFrame(uber_results)
