import time
from uuid import UUID
from enum import StrEnum

import typer
from typing_extensions import Annotated
import requests
from rich import print
from rich.console import Console
from rich.table import Table

from utils.azure_api import AZURE_MANAGEMENT_SCOPE, get_access_token


SLEEP_TIME_AFTER_CAPACITY_CHANGE = 15


def get_fabric_capacities(access_token: str, subscription_id: str):
    """Obtiene las propiedades de las capacidades Fabric de una subscripción Azure.
    Devuelve una lista de objetos con las propiedades de cada capacidad."""
    api_url = f"https://management.azure.com/subscriptions/{subscription_id}/providers/Microsoft.Fabric/capacities?api-version=2022-07-01-preview"

    headers = {
        "Authorization": "Bearer " + access_token,
    }

    http_response = requests.get(api_url, headers=headers)
    http_response.raise_for_status()
    response_json = http_response.json()
    return response_json["value"]


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


def change_fabric_capacity_state(access_token: str, capacity_id: str, new_state: str):
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
    return change_fabric_capacity_state(access_token, capacity_id, "suspend")


def resume_fabric_capacity(access_token: str, capacity_id: str):
    return change_fabric_capacity_state(access_token, capacity_id, "resume")


def change_fabric_capacity_sku(access_token: str, capacity_id: str, new_sku: str):
    """Cambia el SKU de una capacidad Fabric.
    Los SKU pueden ser F2, F4, F8, F16, F32, F64, F128, F256, F512, F1024, F2048."""
    api_url = (
        f"https://management.azure.com{capacity_id}?api-version=2022-07-01-preview"
    )

    headers = {
        "Authorization": "Bearer " + access_token,
    }

    http_response = requests.patch(
        api_url, headers=headers, json={"sku": {"name": new_sku}}
    )
    http_response.raise_for_status()
    return http_response.ok


def print_capacity(capacity):

    table = Table(show_header=False, show_lines=True)
    table.add_row("Nombre:", capacity["name"])
    table.add_row("Estado:", capacity["properties"]["state"])
    table.add_row("SKU:", capacity["sku"]["name"])
    table.add_row("ID:", capacity["id"])
    table.add_row("Ubicación:", capacity["location"])

    console = Console()
    console.print(table)


def get_refresh_history(access_token: str, group_id: str, dataset_id: str, top=10):
    """Obtiene la historia de actualizaciones de un modelo semántico de Power BI"""
    api_url = f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/datasets/{dataset_id}/refreshes?$top={top}"

    headers = {
        "Authorization": "Bearer " + access_token,
    }

    http_response = requests.get(api_url, headers=headers)
    http_response.raise_for_status()
    response_json = http_response.json()
    return response_json["value"]


app = typer.Typer(add_completion=False)


@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    help: Annotated[
        bool, typer.Option("--help", "-h", help="Imprime este mensaje de ayuda.")
    ] = False,
):
    """Comandos para automatizar tareas de Microsoft Fabric.

    Para ver la ayuda de un comando: pbicmd fabric <comando> --help

    """

    # Si se está ejecutando un comando, no ejecutar esta función
    if ctx.invoked_subcommand is not None:
        return

    # Mostrar la ayuda si no se pasa ningún parámetro
    ctx.get_help()


class FabricSku(StrEnum):
    f2 = "F2"
    f4 = "F4"
    f8 = "F8"
    f16 = "F16"
    f32 = "F16"
    f64 = "F64"
    f128 = "F128"
    f256 = "F256"
    f512 = "F512"
    f1024 = "F1024"
    f2048 = "F2048"


@app.command()
def capacities(
    subscription_id: Annotated[
        UUID,
        typer.Option(
            "--azsub",
            "-as",
            help="ID de una subscripción a Azure.",
            show_default=False,
        ),
    ],
):
    """Lista las capacidades Fabric de una subscripción Azure."""

    access_token = get_access_token(AZURE_MANAGEMENT_SCOPE)

    capacities = get_fabric_capacities(access_token, subscription_id)

    for cap in capacities:
        print_capacity(cap)
        print()


@app.command()
def sku(
    capacity_id: Annotated[
        str,
        typer.Option(
            "--cap",
            "-c",
            help="ID de una capacidad Fabric.",
            show_default=False,
        ),
    ],
    sku: Annotated[
        FabricSku,
        typer.Option(
            "--sku",
            "-k",
            help="SKU de la capacidad.",
            case_sensitive=False,
        ),
    ],
):
    """Cambia el SKU de una capacidad Fabric."""

    access_token = get_access_token(AZURE_MANAGEMENT_SCOPE)

    change_fabric_capacity_sku(access_token, capacity_id, sku)

    capacity = get_fabric_capacity(access_token, capacity_id)
    print_capacity(capacity)
    print()


@app.command()
def resume(
    capacity_id: Annotated[
        str,
        typer.Option(
            "--cap",
            "-c",
            help="ID de una capacidad Fabric.",
            show_default=False,
        ),
    ],
    sku: Annotated[
        FabricSku,
        typer.Option(
            "--sku",
            "-k",
            help="SKU de la capacidad.",
            case_sensitive=False,
        ),
    ] = None,
):
    """Inicia una capacidad Fabric."""

    access_token = get_access_token(AZURE_MANAGEMENT_SCOPE)

    if sku is not None:
        change_fabric_capacity_sku(access_token, capacity_id, sku)

    print("Iniciando la capacidad...")
    resume_fabric_capacity(access_token, capacity_id)
    capacity = get_fabric_capacity(access_token, capacity_id)
    print_capacity(capacity)
    print()

    print(f"Esperando {SLEEP_TIME_AFTER_CAPACITY_CHANGE} segundos...")
    time.sleep(SLEEP_TIME_AFTER_CAPACITY_CHANGE)
    print()

    print("Comprobando el estado de la capacidad:")
    capacity = get_fabric_capacity(access_token, capacity_id)
    print_capacity(capacity)
    print()


@app.command()
def suspend(
    capacity_id: Annotated[
        str,
        typer.Option(
            "--cap",
            "-c",
            help="ID de una capacidad Fabric.",
            show_default=False,
        ),
    ],
):
    """Pausa una capacidad Fabric."""

    access_token = get_access_token(AZURE_MANAGEMENT_SCOPE)

    print("Pausando la capacidad...")
    suspend_fabric_capacity(access_token, capacity_id)
    capacity = get_fabric_capacity(access_token, capacity_id)
    print_capacity(capacity)
    print()

    print(f"Esperando {SLEEP_TIME_AFTER_CAPACITY_CHANGE} segundos...")
    time.sleep(SLEEP_TIME_AFTER_CAPACITY_CHANGE)
    print()

    print("Comprobando el estado de la capacidad:")
    capacity = get_fabric_capacity(access_token, capacity_id)
    print_capacity(capacity)
    print()
