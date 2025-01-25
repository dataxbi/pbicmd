import datetime
import time
import sys
from uuid import UUID, uuid4

import typer
from typing_extensions import Annotated
import requests
from rich import print
from rich.console import Console
from rich.panel import Panel

from utils.azure_api import (
    get_access_token,
    AZURE_MANAGEMENT_SCOPE,
    AZURE_STORAGE_SCOPE,
)
from utils.powerbi_api import POWER_BI_SCOPE
from utils.fabric_api import (
    get_fabric_capacity,
    resume_fabric_capacity,
    suspend_fabric_capacity,
)


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


def get_dataset(access_token: str, workspace_id: str, dataset_id: str):
    """Obtiene los detalles de un modelo semántico."""
    api_url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}"

    headers = {
        "Authorization": "Bearer " + access_token,
    }

    http_response = requests.get(api_url, headers=headers)
    http_response.raise_for_status()
    response_json = http_response.json()
    return response_json


def get_refresh_history(access_token: str, workspace_id: str, dataset_id: str, top=1):
    """Obtiene la historia de actualizaciones de un modelo semántico de Power BI"""
    api_url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/refreshes?$top={top}"

    headers = {
        "Authorization": "Bearer " + access_token,
    }

    http_response = requests.get(api_url, headers=headers)
    http_response.raise_for_status()
    response_json = http_response.json()
    return response_json["value"]


def print_error(error_message):
    Console().print(
        Panel(error_message, title="Error", title_align="left", border_style="red")
    )


def fabricetl_command(
    capacity_id: Annotated[
        str,
        typer.Option(
            "--cap",
            "-c",
            help="ID de una capacidad Fabric.",
            show_default=False,
        ),
    ],
    fabric_workspace_id: Annotated[
        UUID,
        typer.Option(
            "--fabworkspace",
            "-fws",
            help="ID de un área de trabajo con capacidad Fabric.",
            show_default=False,
        ),
    ],
    lakehouse_id: Annotated[
        UUID,
        typer.Option(
            "--lakehouse",
            "-lh",
            help="ID del Lakehouse donde se creará el fichero de control.",
            show_default=False,
        ),
    ],
    pbi_workspace_id: Annotated[
        UUID,
        typer.Option(
            "--pbiworkspace",
            "-pws",
            help="ID de un área de trabajo donde está el modelo semántico de Power BI.",
            show_default=False,
        ),
    ],
    dataset_id: Annotated[
        UUID,
        typer.Option(
            "--dataset",
            "-ds",
            help="ID del modelo semántico de Power BI que se va a actualizar.",
            show_default=False,
        ),
    ],
    control_directory: Annotated[
        str,
        typer.Option(
            "--cdir",
            "-cd",
            help="Ruta a la carpeta donde se creará el fichero de control.",
            show_default=True,
        ),
    ] = "control",
    control_control_file_prefix: Annotated[
        str,
        typer.Option(
            "--cfile",
            "-cf",
            help="Inicio del nombre del fichero de control.",
            show_default=True,
        ),
    ] = "start_etl_pipeline",
    wait_time: Annotated[
        int,
        typer.Option(
            "--wtime",
            "-wt",
            help="Tiempo de espera, en segundos.",
            show_default=True,
        ),
    ] = 120,
    max_iter: Annotated[
        int,
        typer.Option(
            "--maxiter",
            "-mi",
            help="Cantidad máxima de veces que se comprobará la actualización del modelo semántico.",
            show_default=True,
        ),
    ] = 10,
):
    """Enciende una capacidad Fabric, crea un fichero de control en un Lakehouse, y se queda esperando a que un modelo semántico se actualice y luego apaga la capacidad.."""

    access_token_azure = get_access_token(AZURE_MANAGEMENT_SCOPE)
    access_token_storage = get_access_token(AZURE_STORAGE_SCOPE)
    access_token_powerbi = get_access_token(POWER_BI_SCOPE)

    capacity = get_fabric_capacity(
        access_token=access_token_azure, capacity_id=capacity_id
    )
    print(
        f"Capacidad Fabric: [b]{capacity['name']}[/b]  SKU: [b]{capacity['sku']['name']}[/b]  Estado: [b]{capacity['properties']['state']}[/b]"
    )
    print()

    dataset = get_dataset(
        access_token=access_token_powerbi,
        workspace_id=pbi_workspace_id,
        dataset_id=dataset_id,
    )
    print(f"Modelo semántico: [b]{dataset['name']}[/b]")

    dataset_last_update = None
    refresh_history = get_refresh_history(
        access_token=access_token_powerbi,
        workspace_id=pbi_workspace_id,
        dataset_id=dataset_id,
        top=1,
    )
    if len(refresh_history) > 0:
        rh = refresh_history[0]
        dataset_last_update = rh["endTime"]
        print(
            f"Última actualización del modelo semántico: [b]{dataset_last_update}[/b]  Estado: [b]{rh['status']}[/b]"
        )
    else:
        print("El modelo semántico no ha sido actualizado antes.")

    print()

    if capacity["properties"]["state"] == "Paused":
        print("Encendiendo la capacidad...")
        resume_fabric_capacity(access_token_azure, capacity_id)
        capacity = get_fabric_capacity(access_token_azure, capacity_id)
        time.sleep(10)
        capacity = get_fabric_capacity(access_token_azure, capacity_id)

    while capacity["properties"]["state"] == "Resuming":
        time.sleep(10)
        capacity = get_fabric_capacity(access_token_azure, capacity_id)

    if capacity["properties"]["state"] != "Active":
        print_error(
            f"No se ha podido ENCENDER la capacidad Fabric y resporta este estado: {capacity['properties']['state']}"
        )
        sys.exit(1)

    print("La capacidad está [b]ENCENDIDA[/b].")
    print()

    print("Creando el fichero de control...")
    file_url = create_control_file(
        access_token=access_token_storage,
        workspace_id=fabric_workspace_id,
        lakehouse_id=lakehouse_id,
        control_directory=control_directory,
        control_file_prefix=control_control_file_prefix,
    )
    print(f"El fichero de control ha sido CREADO: {file_url}")
    print()

    time.sleep(10)

    print("Borrando el fichero de control...")
    r = delete_control_file(access_token=access_token_storage, file_url=file_url)
    print(f"El fichero de control ha sido BORRADO: {file_url}")
    print()

    print(
        "Esperando unos minutos para comenzar a monitorizar la actualización del modelo semántico..."
    )
    print()
    time.sleep(wait_time)

    print("Monitorizando la actualización del modeleo semántico...")
    while max_iter > 0:
        refresh_history = get_refresh_history(
            access_token=access_token_powerbi,
            workspace_id=pbi_workspace_id,
            dataset_id=dataset_id,
            top=1,
        )
        dataset_update = None
        dataset_status = None
        if len(refresh_history) > 0:
            rh = refresh_history[0]
            if rh["status"] == "Completed":
                dataset_update = rh["endTime"]

            if dataset_update != dataset_last_update:
                dataset_status = rh["status"]
                break

        max_iter = max_iter - 1

        if max_iter > 0:
            print("Esperando unos minutos...")
            time.sleep(wait_time)

    if dataset_status == "Completed":
        print("El modelo semántico de Power BI ha sido ACTUALIZADO.")
        print(
            f"Última actualización del modelo semántico: [b]{dataset_update}[/b]  Estado: [b]{rh['status']}[/b]"
        )
    else:
        print_error("El modelo semántico de Power BI NO pudo ser ACTUALIZADO.")
    print()

    print("Esperando unos minutos para apagar la capacidad...")
    time.sleep(wait_time)

    print("Apagando la capacidad...")
    suspend_fabric_capacity(access_token_azure, capacity_id)
    capacity = get_fabric_capacity(access_token_azure, capacity_id)

    while capacity["properties"]["state"] == "Pausing":
        time.sleep(10)
        capacity = get_fabric_capacity(access_token_azure, capacity_id)

    if capacity["properties"]["state"] != "Paused":
        print_error(
            f"No se ha podido APAGAR la capacidad Fabric y reporta este estado: {capacity['properties']['state']}"
        )
        sys.exit(2)

    print("La capacidad está [b]APAGADA[/b].")
