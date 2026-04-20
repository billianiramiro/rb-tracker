import os
import json
import base64
import requests
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ============================================================
#  CONFIGURACIÓN
# ============================================================
GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN_PAT")
GITHUB_REPO   = os.environ.get("GITHUB_REPO")
GITHUB_BRANCH = "main"
GITHUB_FILE   = "fitbit_hoy.json"
# ============================================================

SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.read',
    'https://www.googleapis.com/auth/fitness.nutrition.read',
    'https://www.googleapis.com/auth/fitness.location.read',
]

def get_credentials():
    token_json = os.environ.get("GOOGLE_TOKEN_JSON")
    if token_json:
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    elif os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        raise Exception("No se encontró token de Google.")

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return creds

def get_today_millis():
    now   = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end   = now.replace(hour=23, minute=59, second=59, microsecond=0)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)

def detectar_ejercicio(minutos, distancia_km, fecha):
    dia_semana = datetime.strptime(fecha, "%Y-%m-%d").weekday()  # 5=sábado, 6=domingo
    es_finde = dia_semana in (5, 6)

    if (minutos or 0) < 20 and (distancia_km or 0) < 2:
        return "DESCANSO"

    if (distancia_km or 0) >= 2:
        if es_finde:
            return "FONDO"
        else:
            return "CORRIDA"

    if (minutos or 0) >= 20:
        return "GIMNASIO"

    return "DESCANSO"

def fetch_fitness_data():
    creds   = get_credentials()
    service = build('fitness', 'v1', credentials=creds)
    start_ms, end_ms = get_today_millis()

    body = {
        "aggregateBy": [
            {"dataTypeName": "com.google.calories.expended"},
            {"dataTypeName": "com.google.step_count.delta"},
            {"dataTypeName": "com.google.active_minutes"},
            {"dataTypeName": "com.google.distance.delta"},
            {"dataTypeName": "com.google.nutrition"},
        ],
        "bucketByTime": {"durationMillis": 86400000},
        "startTimeMillis": start_ms,
        "endTimeMillis":   end_ms,
    }

    response = service.users().dataset().aggregate(userId='me', body=body).execute()

    from datetime import timezone, timedelta
ARG = timezone(timedelta(hours=-3))
fecha_hoy = datetime.now(ARG).strftime("%Y-%m-%d")
data = {
        "fecha":               fecha_hoy,
        "calorias_quemadas":   0,
        "calorias_consumidas": 0,
        "pasos":               0,
        "minutos_activos":     0,
        "distancia_km":        0.0,
        "ritmo_medio":         None,
        "ejercicio":           "DESCANSO",
    }

    for bucket in response.get('bucket', []):
        for dataset in bucket.get('dataset', []):
            for point in dataset.get('point', []):
                dtype = point['dataTypeName']
                value = point['value'][0]

                if dtype == 'com.google.calories.expended':
                    data['calorias_quemadas'] = round(value.get('fpVal', 0))
                elif dtype == 'com.google.step_count.delta':
                    data['pasos'] = value.get('intVal', 0)
                elif dtype == 'com.google.active_minutes':
                    data['minutos_activos'] = value.get('intVal', 0)
                elif dtype == 'com.google.distance.delta':
                    data['distancia_km'] = round(value.get('fpVal', 0) / 1000, 2)
                elif dtype == 'com.google.nutrition':
                    for nutrient in point.get('value', []):
                        if nutrient.get('mapVal'):
                            for item in nutrient['mapVal']:
                                if item['key'] == 'calories':
                                    data['calorias_consumidas'] = round(
                                        data['calorias_consumidas'] + item['value']['fpVal']
                                    )

    if data['distancia_km'] > 0 and data['minutos_activos'] > 0:
        data['ritmo_medio'] = round(data['minutos_activos'] / data['distancia_km'], 2)

    data['ejercicio'] = detectar_ejercicio(
        data['minutos_activos'],
        data['distancia_km'],
        fecha_hoy
    )

    return data

def push_to_github(data):
    url     = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
    }

    sha = None
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        sha = r.json().get("sha")

    content = json.dumps(data, indent=2, ensure_ascii=False)
    encoded = base64.b64encode(content.encode()).decode()

    payload = {
        "message": f"sync: fitness data {data['fecha']}",
        "content": encoded,
        "branch":  GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(url, headers=headers, json=payload)
    if r.status_code in (200, 201):
        print(f"✅ fitbit_hoy.json subido a GitHub correctamente")
    else:
        print(f"❌ Error subiendo a GitHub: {r.status_code} — {r.text}")

if __name__ == '__main__':
    print("📡 Obteniendo datos de Google Fit...")
    data = fetch_fitness_data()
    print(f"📊 Resultado:")
    for k, v in data.items():
        print(f"   {k}: {v}")
    print()
    print("🚀 Subiendo a GitHub...")
    push_to_github(data)
    with open('fitbit_hoy.json', 'w') as f:
        json.dump(data, f, indent=2)
    print("💾 Copia local guardada en fitbit_hoy.json")
