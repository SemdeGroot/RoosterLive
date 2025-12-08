import json
import boto3
import sqlite3
import os
from django.conf import settings
from botocore.exceptions import ClientError

LOOKUP_DB_PATH = os.path.join(settings.BASE_DIR, 'lookup.db')
S3_KEY = "config/vragen.json"

def get_s3_client():
    region = os.getenv('AWS_S3_REGION_NAME', 'eu-central-1')
    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    kwargs = {'region_name': region}
    if access_key and secret_key:
        kwargs['aws_access_key_id'] = access_key
        kwargs['aws_secret_access_key'] = secret_key
    return boto3.client('s3', **kwargs)

def get_bucket_name():
    bucket = os.getenv('AWS_STORAGE_BUCKET_NAME')
    if not bucket:
        bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)
    if not bucket:
        raise ValueError("Geen bucket gevonden")
    return bucket

def get_review_settings_json():
    s3 = get_s3_client()
    try:
        response = s3.get_object(Bucket=get_bucket_name(), Key=S3_KEY)
        return json.loads(response['Body'].read().decode('utf-8'))
    except ClientError:
        return {"version": "2.0", "criteria": []}

def save_review_settings_json(data):
    s3 = get_s3_client()
    from datetime import datetime
    data['last_modified'] = datetime.now().strftime("%Y-%m-%d")
    s3.put_object(
        Bucket=get_bucket_name(), 
        Key=S3_KEY, 
        Body=json.dumps(data, indent=4),
        ContentType='application/json'
    )

def search_atc_icpc(query, search_type='ATC'):
    if not os.path.exists(LOOKUP_DB_PATH): return []
    conn = sqlite3.connect(LOOKUP_DB_PATH)
    cursor = conn.cursor()
    sql = f"SELECT code, description FROM {'atc' if search_type == 'ATC' else 'icpc'} WHERE code LIKE ? OR description LIKE ? LIMIT 50"
    cursor.execute(sql, (f"{query}%", f"%{query}%"))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "text": f"{r[0]} - {r[1]}"} for r in rows]

def hydrate_criteria_with_descriptions(criteria_list):
    """Vult de codes aan met tekst uit DB"""
    if not os.path.exists(LOOKUP_DB_PATH) or not criteria_list: return criteria_list
    
    all_codes = set()
    fields = ['triggers', 'required_co_medication', 'excluded_co_medication', 'requires_at_least_one_of']
    
    for item in criteria_list:
        logic = item.get('logic_rules', {})
        for f in fields:
            all_codes.update(logic.get(f, []))
            
    if not all_codes: return criteria_list

    conn = sqlite3.connect(LOOKUP_DB_PATH)
    cursor = conn.cursor()
    placeholders = ','.join('?' for _ in all_codes)
    cursor.execute(f"SELECT code, description FROM atc WHERE code IN ({placeholders})", list(all_codes))
    lookup = {r[0]: r[1] for r in cursor.fetchall()}
    conn.close()

    for item in criteria_list:
        logic = item.setdefault('logic_rules', {})
        for f in fields:
            logic[f'{f}_enriched'] = [{"id": c, "text": f"{c} - {lookup.get(c, '?')}"} for c in logic.get(f, [])]
            
    return criteria_list