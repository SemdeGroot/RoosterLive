import requests
from xml_baxter_watchdog.config import API_URL, API_TOKEN

def stuur_naar_api(payload: dict) -> bool:
    """
    Stuurt de payload als JSON naar de Django API.
    Geeft True terug bij succes, False bij fout.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Token {API_TOKEN}",
    }

    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        print(f"  [SUCCES] API response {response.status_code}: {response.json()}")
        return True

    except requests.exceptions.ConnectionError:
        print(f"  [ERROR] Kan API niet bereiken: {API_URL}")
    except requests.exceptions.Timeout:
        print(f"  [ERROR] API timeout na 10 seconden")
    except requests.exceptions.HTTPError as e:
        print(f"  [ERROR] API fout {response.status_code}: {e}")
    except Exception as e:
        print(f"  [ERROR] Onverwachte fout: {e}")

    return False