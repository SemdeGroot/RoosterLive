import requests
import json
from django.conf import settings

def call_review_api(text, source="medimo", scope="afdeling", geboortedatum=None):
    url = settings.MEDICATIEREVIEW_API_URL
    api_key = getattr(settings, "MEDICATIEREVIEW_API_KEY", None)

    payload = {"text": text, "source": source, "scope": scope}

    # Alleen meesturen bij scope=patient en als ingevuld
    if scope == "patient" and geboortedatum:
        payload["geboortedatum"] = geboortedatum  # verwacht ISO "YYYY-MM-DD"

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    results = None
    errors = []

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=120)

        if r.status_code == 401:
            return None, ["Niet geautoriseerd bij de medicatiereview-service (check API key)."]

        if r.status_code >= 400:
            return None, [f"HTTP {r.status_code} van medicatiereview-service: {r.text[:1000]}"]

        for line in r.text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")
            if msg_type == "result":
                results = data
            elif msg_type == "error":
                errors.append(data.get("msg", "Onbekende fout in API"))

    except requests.exceptions.Timeout:
        errors.append("De analyse duurde te lang (timeout). Probeer een kleinere tekst.")
    except requests.exceptions.ConnectionError:
        errors.append(f"Kan geen verbinding maken met de medicatiereview-service op {url}.")
    except requests.exceptions.RequestException as e:
        errors.append(f"Fout bij communicatie met de medicatiereview-service: {str(e)}")

    return results, errors