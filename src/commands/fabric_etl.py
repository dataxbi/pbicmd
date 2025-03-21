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
    run_data_pipeline,
)


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
    data_pipeline_id: Annotated[
        UUID,
        typer.Option(
            "--datapipeline",
            "-dp",
            help="ID de la canalización de datos que implemente la ETL.",
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
    """Controla el encendido y apagado de una capacidad Fabric para ejecutar una ETL. Enciende la capacidad, inicia la ejecución de una canalización de datos que orquesta la ETL, espera la actualización del modelo semántico en Power BI y apaga la capacidad al finalizar."""

    access_token_azure = get_access_token(AZURE_MANAGEMENT_SCOPE)
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

    print("Iniciando la ejecución de la canalización de datos...")

    run_data_pipeline(
        access_token=access_token_powerbi,
        workspace_id=fabric_workspace_id,
        data_pipeline_id=data_pipeline_id,
    )

    print("La ejecución de la canalización de datos se ha [b]INICIADO[/b].")
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
            dataset_update = rh["endTime"]
            dataset_status = rh["status"]
            if dataset_status == "Completed" and dataset_update != dataset_last_update:
                break

        max_iter = max_iter - 1

        if max_iter > 0:
            print("Esperando unos minutos...")
            time.sleep(wait_time)

    if dataset_status == "Completed":
        print("El modelo semántico de Power BI ha sido ACTUALIZADO.")
        print(
            f"Última actualización del modelo semántico: [b]{dataset_update}[/b]  Estado: [b]{dataset_status}[/b]"
        )
    else:
        print_error("El modelo semántico de Power BI NO pudo ser ACTUALIZADO.")
        print(
            f"Última actualización del modelo semántico: [b]{dataset_update}[/b]  Estado: [b]{dataset_status}[/b]"
        )
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
