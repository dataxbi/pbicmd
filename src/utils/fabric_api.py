import requests


def get_fabric_capacity(access_token: str, capacity_id: str):
    """Obtiene las propiedades de una capacidad Fabric.
    Devuelve un objeto con las propiedades."""
    api_url = (
        f"https://management.azure.com/{capacity_id}?api-version=2022-07-01-preview"
    )

    headers = {
        "Authorization": "Bearer " + access_token,
    }

    http_response = requests.get(api_url, headers=headers)
    http_response.raise_for_status()
    return http_response.json()


def __change_fabric_capacity_state(access_token: str, capacity_id: str, new_state: str):
    """Cambia el estado de una capacidad Fabric.
    Los estados pueden ser resume o suspend."""
    api_url = f"https://management.azure.com{capacity_id}/{new_state}?api-version=2022-07-01-preview"

    headers = {
        "Authorization": "Bearer " + access_token,
    }

    http_response = requests.post(api_url, headers=headers)
    http_response.raise_for_status()
    return http_response.ok


def suspend_fabric_capacity(access_token: str, capacity_id: str):
    return __change_fabric_capacity_state(access_token, capacity_id, "suspend")


def resume_fabric_capacity(access_token: str, capacity_id: str):
    return __change_fabric_capacity_state(access_token, capacity_id, "resume")


def run_data_pipeline(access_token: str, workspace_id: str, data_pipeline_id: str):
    api_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/items/{data_pipeline_id}/jobs/instances?jobType=Pipeline"

    headers = {
        "Authorization": "Bearer " + access_token,
    }

    http_response = requests.post(api_url, headers=headers)
    http_response.raise_for_status()
    return http_response.ok


# Las siguientes dos funciones no se están usando en este momento,
# pero las dejo aquí para recordar cómo se puede crear y borrar un fichero en OneLake.


def create_control_file(
    access_token, workspace_id, lakehouse_id, control_directory, control_file_prefix
):
    file_name = f"{control_file_prefix}_{datetime.datetime.now().strftime('%Y-%m-%d')}_{uuid4()}.txt"
    file_url = f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}/{lakehouse_id}/Files/{control_directory}/{file_name}"
    url = f"{file_url}?resource=file"

    headers = {
        "Authorization": f"Bearer " + access_token,
        "Content-Type": "application/octet-stream",
    }

    http_response = requests.put(url, headers=headers, data=b"")
    http_response.raise_for_status()
    return file_url


def delete_control_file(access_token, file_url):
    headers = {
        "Authorization": f"Bearer " + access_token,
        "Content-Type": "application/octet-stream",
    }

    http_response = requests.delete(file_url, headers=headers)
    http_response.raise_for_status()
    return http_response.ok
