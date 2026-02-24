import requests
from xml_baxter_watchdog.env_config import API_URL, API_TOKEN, PROXY_URL


def stuur_naar_api(payload: dict) -> bool:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Token {API_TOKEN}",
    }
    proxies = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None

    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=10, proxies=proxies)
        response.raise_for_status()
        return True

    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False

    except requests.exceptions.HTTPError:
        return False

    except Exception:
        return False