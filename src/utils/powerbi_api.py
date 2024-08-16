import requests

POWER_BI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"
POWER_BI_API_BASE = "https://api.powerbi.com/v1.0/myorg"


def get_dataset(access_token, dataset_id):
    """Devuelve información sobre un modelo semántico"""
    api_url = f"{POWER_BI_API_BASE}/datasets/{dataset_id}"

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + access_token,
    }

    http_response = requests.get(
        api_url,
        headers=headers,
    )

    http_response.raise_for_status()
    http_response.encoding = "utf-8-sig"
    return http_response.json()


def execute_dax(access_token, dataset_id, dax_query):
    """Ejecuta una consulta DAX con la API de Power BI.
    Retorna un JSON con la respuesta de la API.
    """
    api_url = f"{POWER_BI_API_BASE}/datasets/{dataset_id}/executeQueries"

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + access_token,
    }

    http_response = requests.post(
        api_url,
        headers=headers,
        json={
            "queries": [{"query": f"{dax_query}"}],
            "serializerSettings": {"includeNulls": True},
        },
    )

    http_response.raise_for_status()
    http_response.encoding = "utf-8-sig"
    return http_response.json()
