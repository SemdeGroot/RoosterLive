import requests
import json
from django.conf import settings

def call_review_api(text, source="medimo", scope="afdeling"):
    """
    Stuurt de tekst naar de FastAPI/Lambda microservice en wacht op het eindresultaat.
    
    Args:
        text (str): De ruwe tekst uit het EPD/AIS.
        source (str): Bron systeem (default "medimo").
        scope (str): "afdeling" of "patient".

    Returns:
        tuple: (resultaat_dict, error_lijst)
               - resultaat_dict is None als het mislukt.
               - error_lijst bevat strings met foutmeldingen.
    """
    
    url = settings.MEDICATIEREVIEW_API_URL
    api_key = getattr(settings, "MEDICATIEREVIEW_API_KEY", None)

    payload = {
        "text": text,
        "source": source,
        "scope": scope,
    }

    # Headers opbouwen
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key

    results = None
    errors = []

    try:
        # Timeout ruim zetten (120s) omdat het parsen van een hele afdeling 
        # met AI/analyse logica best even kan duren.
        with requests.post(
            url,
            json=payload,
            headers=headers,
            stream=True,
            timeout=120,
        ) as r:
            
            # 401 expliciet afvangen voor duidelijkere foutmelding
            if r.status_code == 401:
                errors.append("Niet geautoriseerd bij de medicatiereview-service (check API key).")
                return results, errors

            # Check op overige HTTP fouten (404, 500, etc) direct bij connectie
            r.raise_for_status()
            
            # We lezen de NDJSON stream regel voor regel
            for line in r.iter_lines():
                if not line:
                    continue
                
                try:
                    data = json.loads(line.decode("utf-8"))
                    msg_type = data.get("type")

                    # Alleen eindresultaat of errors gebruiken
                    if msg_type == "result":
                        results = data
                    elif msg_type == "error":
                        errors.append(data.get("msg", "Onbekende fout in API"))

                except json.JSONDecodeError:
                    # Als een regel niet valide is, skippen we hem
                    continue
                        
    except requests.exceptions.Timeout:
        errors.append("De analyse duurde te lang (timeout). Probeer een kleinere tekst.")
    except requests.exceptions.ConnectionError:
        errors.append(f"Kan geen verbinding maken met de medicatiereview-service op {url}. Draait deze wel?")
    except requests.exceptions.RequestException as e:
        errors.append(f"Fout bij communicatie met de medicatiereview-service: {str(e)}")

    return results, errors