import requests
from xml_baxter_watchdog.env_config import API_URL, API_TOKEN


def stuur_naar_api(payload: dict) -> bool:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Token {API_TOKEN}",
    }

    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return True

    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False

    except requests.exceptions.HTTPError:
        return False

    except Exception:
        return False