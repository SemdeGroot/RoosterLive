from celery import shared_task
from core.utils.kompasscraper.scraper import KompasScraper
import time
import random
from core.models import ScrapedPage
import hashlib

@shared_task(name="tasks.run_kompas_scraper")
def run_kompas_scraper(test_mode=False):
    # In test_mode gebruiken we een lage limiet voor de discovery
    limit = 3 if test_mode else None
    scraper = KompasScraper(debug_limit=limit)
    
    urls = scraper.discovery_phase()
    
    uploaded_count = 0
    # Sorteer op categorie om een mix van preparaat, groep en indicatie te krijgen
    urls.sort(key=lambda x: x['category'])
    
    for item in urls:
        # Harde stop bij 3 uploads als test_mode aan staat
        if test_mode and uploaded_count >= 3:
            print("DEBUG: Test-limiet van 3 uploads bereikt. Stoppen.")
            break
            
        print(f"DEBUG: Verwerken [{uploaded_count + 1}] {item['category']}: {item['url']}")
        
        if scraper.process_url(item):
            uploaded_count += 1
            print(f"DEBUG: Succesvol geüpload. Totaal deze run: {uploaded_count}")
        
        # Slaap om de Gemini API en de FK server te ontzien
        time.sleep(random.uniform(3, 6))

    return f"Klaar. {uploaded_count} urls verwerkt en geindexeerd."