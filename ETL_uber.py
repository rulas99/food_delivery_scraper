import pandas as pd
from playwright.sync_api import sync_playwright
import concurrent.futures
import os
from tqdm import tqdm

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
        try:
            address = page.locator("//html/body/div[1]/div[3]/div[1]/div[2]/main/div/div[2]/div/div/div[2]/div[2]/section/ul/button[1]/div[2]/div[1]").inner_text()
            # Schedule
            schedule = page.locator('//html/body/div[1]/div[3]/div[1]/div[2]/main/div/div[2]/div/div/div[2]/div[2]/section/div[2]/div').all_text_contents()[0]
        except:
            address = page.locator("//html/body/div[1]/div[3]/div[1]/div[2]/main/div/div[2]/div/div/div[3]/div/section/ul/button[1]/div[2]/div[1]").inner_text()
            schedule = page.locator('//html/body/div[1]/div[3]/div[1]/div[2]/main/div/div[2]/div/div/div[3]/div/section/div[2]/div').all_text_contents()[0]
        
        # Extraer coordenadas geográficas del JSON en el script
        latitude = None
        longitude = None
        try:
            # Buscar todos los scripts en la página (sin filtrar por tipo)
            scripts = page.query_selector_all('script')
            for script in scripts:
                try:
                    script_content = script.inner_text()
                    # Verificar si el contenido tiene geo o geoCoordinates
                    if 'geo' in script_content and ('latitude' in script_content or 'geoCoordinates' in script_content):
                        # Intentar parsear el JSON
                        import json
                        # Limpiar el contenido si es necesario
                        script_content = script_content.strip()
                        data_json = json.loads(script_content)
                        
                        # Buscar las coordenadas en el JSON
                        # Primero intentar con geo.geoCoordinates
                        if 'geo' in data_json and isinstance(data_json['geo'], dict):
                            if 'geoCoordinates' in data_json['geo']:
                                geo = data_json['geo']['geoCoordinates']
                                latitude = geo.get('latitude')
                                longitude = geo.get('longitude')
                            else:
                                # Intentar directamente con geo
                                geo = data_json['geo']
                                latitude = geo.get('latitude')
                                longitude = geo.get('longitude')
                            break
                        # Intentar con geoCoordinates directo
                        elif 'geoCoordinates' in data_json:
                            geo = data_json['geoCoordinates']
                            latitude = geo.get('latitude')
                            longitude = geo.get('longitude')
                            break
                except Exception as e:
                    # Continuar con el siguiente script
                    continue
            
            # Si no se encontró en los scripts, intentar extraer de manera alternativa
            if latitude is None or longitude is None:
                # Ejecutar JavaScript para buscar en todos los scripts
                coords = page.evaluate("""
                    () => {
                        const scripts = document.querySelectorAll('script');
                        for (const script of scripts) {
                            try {
                                if (script.textContent.includes('geo') && 
                                    (script.textContent.includes('latitude') || script.textContent.includes('geoCoordinates'))) {
                                    const content = script.textContent;
                                    const jsonStart = content.indexOf('{');
                                    const jsonEnd = content.lastIndexOf('}') + 1;
                                    if (jsonStart >= 0 && jsonEnd > jsonStart) {
                                        const jsonStr = content.substring(jsonStart, jsonEnd);
                                        const data = JSON.parse(jsonStr);
                                        if (data.geo && data.geo.latitude) {
                                            return {latitude: data.geo.latitude, longitude: data.geo.longitude};
                                        } else if (data.geo && data.geo.geoCoordinates) {
                                            return {latitude: data.geo.geoCoordinates.latitude, longitude: data.geo.geoCoordinates.longitude};
                                        } else if (data.geoCoordinates) {
                                            return {latitude: data.geoCoordinates.latitude, longitude: data.geoCoordinates.longitude};
                                        }
                                    }
                                }
                            } catch (e) {
                                continue;
                            }
                        }
                        return null;
                    }
                """)
                
                if coords:
                    latitude = coords.get('latitude')
                    longitude = coords.get('longitude')
        except Exception as e:
            print(f"Error al extraer coordenadas: {str(e)}")
            # Continuar con el proceso aunque no se puedan extraer las coordenadas

        
        data = {
            'href': url,
            'restaurantName': restaurantName,
            'tags': tags,
            'address': address,
            'schedule': schedule,
            'latitude': latitude,
            'longitude': longitude
        }
        
        return data
    except Exception as e:        
        print('error al procesar la url: ', url)
        print(e)
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
                result = process_uber_url(url, browser)
                if result:
                    results.append(result)
        finally:
            browser.close()
    return results

# Función principal para paralelizar el scraping
def scrape_uber_parallel(urls, max_workers=8, batch_size=30):
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




uber_results = scrape_uber_parallel(uberStores)

# Si necesitas convertir los resultados a DataFrame:
uber_df = pd.DataFrame(uber_results)
uber_df.to_csv('results/uber_results_geo.csv', index=False)
