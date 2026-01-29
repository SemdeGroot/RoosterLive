# core/services/medicatiereview_api.py
import requests
import json
from django.conf import settings
from django.db import transaction
from core.models import MedicatieReviewComment, MedicatieReviewPatient
from core.utils.medication import group_meds_by_jansen
from collections import defaultdict

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

def _normalize_lines(txt: str) -> str:
    # kleine normalisatie om dubbele whitespace te beperken
    return "\n".join([line.rstrip() for line in (txt or "").strip().splitlines()]).strip()

def _append_unique_questions(existing_text: str, questions: list[str]) -> str:
    """
    Voegt nieuwe vragen toe als bullets onderaan de bestaande tekst.
    GEEN header meer.
    """
    existing_text = existing_text or ""
    norm_existing = existing_text

    # bestaande regels verzamelen
    existing_lines = set(
        l.strip() for l in norm_existing.splitlines() if l.strip()
    )

    # nieuwe bullets verzamelen (geen duplicaten)
    new_bullets = []
    for q in questions:
        q = (q or "").strip()
        if not q:
            continue
        bullet = f"- {q}"
        if bullet not in existing_lines:
            new_bullets.append(bullet)

    if not new_bullets:
        return existing_text  # niets te doen

    # gewoon achteraan plakken
    base = norm_existing.strip()
    if base:
        base += "\n\n"

    return base + "\n".join(new_bullets)


@transaction.atomic
def sync_standaardvragen_to_db(patient: MedicatieReviewPatient, user=None) -> int:
    """
    Sync standaardvragen uit analysis_data naar DB, ZONDER ze te verliezen als meerdere
    vragen in dezelfde Jansen-groep vallen.

    Strategie (geen migratie nodig):
    - 1 DB-comment per (patient, jansen_group_id)
    - Alle standaardvragen voor die groep worden als bullets toegevoegd onder
      '### Standaardvragen (automatisch)'.
    - We overschrijven geen bestaande tekst; we appenden alleen nieuwe vragen.
    """
    analysis = patient.analysis_data or {}
    meds = analysis.get("geneesmiddelen", []) or []
    vragen = analysis.get("analyses", {}).get("standaardvragen", []) or []
    if not vragen or not meds:
        return 0

    # 1) Bepaal per medicijn (clean) welke jansen-groep het is
    grouped_meds = group_meds_by_jansen(meds)

    med_to_gid: dict[str, int] = {}
    for gid, gdata in grouped_meds:
        for m in (gdata.get("meds") or []):
            clean = (m.get("clean") or "").strip()
            if clean:
                med_to_gid[clean] = int(gid)

    # 2) Groepeer vragen per target_gid
    questions_by_gid: dict[int, list[str]] = defaultdict(list)

    for vraag in vragen:
        middelen = (vraag.get("betrokken_middelen") or "").strip()
        vraag_tekst = (vraag.get("vraag") or "").strip()
        if not middelen or not vraag_tekst:
            continue

        # probeer alle middelen in middelen-string te matchen
        # (middelen kan comma-separated zijn)
        matched_gids = set()
        for med_clean, gid in med_to_gid.items():
            if med_clean and med_clean in middelen:
                matched_gids.add(gid)

        # als niets matched -> skip
        if not matched_gids:
            continue

        # meestal 1 gid; maar als er meerdere middelen uit verschillende groepen in 1 vraag staan,
        # dan zetten we dezelfde vraag bij alle relevante gids.
        for gid in matched_gids:
            questions_by_gid[int(gid)].append(vraag_tekst)

    if not questions_by_gid:
        return 0

    created_or_updated = 0

    # 3) Voor elke gid: update_or_create 1 record, en append vragen
    for gid, qs in questions_by_gid.items():
        qs_unique = []
        seen = set()
        for q in qs:
            qn = _normalize_lines(q)
            if qn and qn not in seen:
                seen.add(qn)
                qs_unique.append(qn)

        if not qs_unique:
            continue

        comment_obj, created = MedicatieReviewComment.objects.get_or_create(
            patient=patient,
            jansen_group_id=gid,
            defaults={
                "tekst": "",
                "historie": "",
                "updated_by": user,
            }
        )

        new_text = _append_unique_questions(comment_obj.tekst or "", qs_unique)

        # Alleen saven als tekst echt verandert
        if new_text != (comment_obj.tekst or ""):
            comment_obj.tekst = new_text
            if user is not None:
                comment_obj.updated_by = user
            comment_obj.save(update_fields=["tekst", "updated_by"])
            created_or_updated += 1
        else:
            # record bestond al en had al die vragen -> tel niet
            if created:
                created_or_updated += 1

    return created_or_updated
