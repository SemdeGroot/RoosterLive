# core/services/medicatiereview_api.py
import requests
import json
from django.conf import settings
from django.db import transaction
from core.models import MedicatieReviewComment, MedicatieReviewPatient
from core.utils.medication import group_meds_by_jansen

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

def sync_standaardvragen_to_db(patient: MedicatieReviewPatient, user=None) -> int:
    """
    Maak standaardvragen uit analysis_data 1-op-1 aan als DB-comments,
    maar alleen als er nog géén comment-record bestaat voor die jansen_group_id.
    Hierdoor:
      - vragen worden 'echt' bewerkbaar/verwijderbaar
      - als apotheker tekst leeg maakt en opslaat -> record bestaat -> komt niet terug
    """
    analysis = patient.analysis_data or {}
    meds = analysis.get("geneesmiddelen", [])
    vragen = analysis.get("analyses", {}).get("standaardvragen", []) or []
    if not vragen:
        return 0

    grouped_meds = group_meds_by_jansen(meds)

    # map medicatie-clean -> group_id
    med_to_group = {}
    for gid, gdata in grouped_meds:
        for m in gdata.get("meds", []):
            clean = m.get("clean")
            if clean:
                med_to_group[clean] = gid

    # bestaande comment-records (ook lege tekst!) tellen als "bestaat al"
    existing_gids = set(
        patient.comments.values_list("jansen_group_id", flat=True)
    )

    created = 0
    to_create = []

    for vraag in vragen:
        middelen = (vraag.get("betrokken_middelen") or "").strip()
        vraag_tekst = (vraag.get("vraag") or "").strip()
        if not middelen or not vraag_tekst:
            continue

        target_gid = None
        for med, gid in med_to_group.items():
            if med in middelen:
                target_gid = gid
                break
        if not target_gid:
            continue

        if target_gid in existing_gids:
            continue

        to_create.append(MedicatieReviewComment(
            patient=patient,
            jansen_group_id=target_gid,
            tekst=vraag_tekst,
            historie="",
            updated_by=user
        ))
        existing_gids.add(target_gid)

    if to_create:
        MedicatieReviewComment.objects.bulk_create(to_create)
        created = len(to_create)

    return created