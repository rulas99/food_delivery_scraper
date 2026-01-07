import pandas as pd
from playwright.sync_api import sync_playwright
import concurrent.futures
import os
from tqdm import tqdm
import json
import re

data = pd.read_csv('results/complete_data_new.csv')
rappiStores = pd.Series(data.query('platform == "rappi"').href.unique())


# Función para procesar una URL individual con un navegador ya inicializado
def process_rappi_url(url, browser):
    page = browser.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded")
        
        # Extract restaurant name
        restaurantName = page.locator('//html/body/div[1]/div[3]/div[2]/div[2]/div[2]/div[1]/div[2]/h1').text_content()
        # extract tags and rating
        tags = page.locator('//html/body/div[1]/div[3]/div[3]/div/table/tbody/tr[2]/td[2]').text_content()
        # extract address
        address = page.locator("//html/body/div[1]/div[3]/div[3]/div/table/tbody/tr[1]/td[2]").text_content()
        # extract rating
        rating = None
        if page.locator("//html/body/div[1]/div[3]/div[3]/div/table/tbody/tr[3]/td[1]/h3").text_content() == "Rating":
            rating = page.locator("//html/body/div[1]/div[3]/div[3]/div/table/tbody/tr[3]/td[2]").text_content()
        else:
            rating = None
        schedule = page.locator("//html/body/div[1]/div[3]/div[3]/main/div/table").all_text_contents()
        
        # Extraer coordenadas geográficas del script con data-testid="seo-structured-schema"
        latitude = None
        longitude = None
        try:
            # Buscar específicamente el script con data-testid="seo-structured-schema"
            seo_script = page.query_selector('script[data-testid="seo-structured-schema"]')
            
            if seo_script:
                try:
                    # Obtener el contenido del script
                    script_content = seo_script.inner_text()
                    
                    # Parsear el JSON
                    data_json = json.loads(script_content)
                    
                    # Buscar las coordenadas en la estructura geo
                    if 'geo' in data_json and isinstance(data_json['geo'], dict):
                        geo = data_json['geo']
                        if 'latitude' in geo and 'longitude' in geo:
                            latitude = geo['latitude']
                            longitude = geo['longitude']
                            print(f"Coordenadas encontradas en script SEO: {latitude}, {longitude}")
                except Exception as e:
                    print(f"Error al parsear el script SEO: {e}")
            
            # Si no se encontraron coordenadas en el script SEO, intentar con JavaScript
            if latitude is None or longitude is None:
                coords = page.evaluate("""
                    () => {
                        try {
                            // Buscar el script con data-testid="seo-structured-schema"
                            const seoScript = document.querySelector('script[data-testid="seo-structured-schema"]');
                            if (seoScript) {
                                try {
                                    const data = JSON.parse(seoScript.textContent);
                                    if (data.geo && data.geo.latitude && data.geo.longitude) {
                                        return {
                                            latitude: data.geo.latitude,
                                            longitude: data.geo.longitude
                                        };
                                    }
                                } catch (e) {
                                    console.error('Error parsing SEO script JSON:', e);
                                }
                            }
                            return null;
                        } catch (e) {
                            console.error('Error in coordinate extraction:', e);
                            return null;
                        }
                    }
                """)
                
                if coords:
                    latitude = coords.get('latitude')
                    longitude = coords.get('longitude')
                    print(f"Coordenadas encontradas con JavaScript: {latitude}, {longitude}")
        except Exception as e:
            print(f"Error al extraer coordenadas: {e}")
            # Continuar con el proceso aunque no se puedan extraer las coordenadas
            pass
        
        data = {
            'href': url,
            'restaurantName': restaurantName,
            'tags': tags,
            'address': address,
            'rating': rating,
            'schedule': schedule,
            'latitude': latitude,
            'longitude': longitude
        }
        
        return data
    except Exception as e:        
        print('Error scraping url', url)
        print("error", e)
        data = {
            'href': url,
            'restaurantName': None,
            'tags': None,
            'address': None,
            'schedule': None,
            'latitude': None,
            'longitude': None
        }
        return data
    finally:
        page.close()

# Función para inicializar un navegador y procesar un lote de URLs
def process_batch(urls_batch):
    results = []
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)  # Modo headless para mejor rendimiento
        try:
            # Usar tqdm para mostrar progreso dentro del batch
            for url in tqdm(urls_batch, desc="Batch progress", leave=False):
                result = process_rappi_url(url, browser)
                if result:
                    results.append(result)
        finally:
            browser.close()
    return results

# Función principal para paralelizar el scraping
def scrape_rappi_parallel(urls, max_workers=7, batch_size=30):
    """
    Paraleliza el scraping de URLs de Rappi
    
    Args:
        urls: Serie de pandas con las URLs a procesar
        max_workers: Número máximo de workers (procesos paralelos)
        batch_size: Número de URLs a procesar por cada navegador
    
    Returns:
        Lista de diccionarios con los datos extraídos
    """
    all_results = []
    
    # Mostrar información sobre el procesamiento
    total_urls = len(urls)
    print(f"Procesando {total_urls} URLs con {max_workers} workers en lotes de {batch_size}")
    
    # Dividir las URLs en lotes
    url_batches = []
    urls_list = urls.tolist()
    for i in range(0, len(urls_list), batch_size):
        url_batches.append(urls_list[i:i+batch_size])
    
    # Mostrar barra de progreso para los lotes
    print(f"Total de lotes: {len(url_batches)}")
    
    # Procesar los lotes en paralelo con barra de progreso
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Crear un mapa de futuros
        futures = {executor.submit(process_batch, batch): i for i, batch in enumerate(url_batches)}
        
        # Usar tqdm para mostrar el progreso general
        batch_results = []
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(url_batches), desc="Overall progress"):
            batch_index = futures[future]
            try:
                result = future.result()
                batch_results.append(result)
                print(f"Lote {batch_index+1}/{len(url_batches)} completado")
            except Exception as e:
                print(f"Error en lote {batch_index+1}: {str(e)}")
    
    # Aplanar los resultados
    for batch in batch_results:
        if batch:  # Verificar que el batch no sea None
            all_results.extend(batch)
    
    print(f"Procesamiento completado. Se obtuvieron datos de {len(all_results)}/{total_urls} URLs")
    return all_results




rappi_results = scrape_rappi_parallel(rappiStores)

# Si necesitas convertir los resultados a DataFrame:
rappi_df = pd.DataFrame(rappi_results)
rappi_df.to_csv('results/rappi_results_geo.csv', index=False)

