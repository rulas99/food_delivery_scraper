import pandas as pd
from playwright.sync_api import sync_playwright

data = pd.read_csv('results/complete_data_new.csv')
uberStores = pd.Series(data.query('platform == "ubereats"').href.unique())
rappiStores = pd.Series(data.query('platform == "rappi"').href.unique())



# Uber scraper
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
        address = page.locator('//html/body/div[1]/div[3]/div[1]/div[2]/main/div/div[1]/div/div[3]/div/div/div[1]/div/p[3]').text_content()
        # Schedule
        schedule = page.locator('//html/body/div[1]/div[3]/div[1]/div[2]/main/div/div[2]/div/div/div[2]/div[2]/section/div[2]/div').all_text_contents()
        
        final = {
            'restaurantName': restaurantName,
            'tags': tags,
            'address': address,
            'schedule': schedule
        }
        
        print(final)
        
        input('Press Enter when you are ready to close the browser...')

    return {
        'restaurantName': restaurantName,
        # 'tags': tags
    } 
        

page = scrappUber(uberStores[0])
