import time
from uuid import UUID
from enum import StrEnum

import typer
from typing_extensions import Annotated
import requests
from rich import print, print_json
from rich.console import Console
from rich.table import Table

from utils.azure_api import get_access_token
from utils.powerbi_api import POWER_BI_SCOPE


def list_lakehouses(access_token: str, workspace_id: str):
    """Obtiene una lista de lakehouses de un área de trabajo.
    https://learn.microsoft.com/en-us/rest/api/fabric/lakehouse/items/list-lakehouses
    """
    api_url = (
        f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/lakehouses"
    )

    headers = {
        "Authorization": "Bearer " + access_token,
    }

    http_response = requests.get(api_url, headers=headers)
    http_response.raise_for_status()
    response_json = http_response.json()
    return response_json["value"]


def create_lakehouse(
    access_token: str, workspace_id: str, display_name: str, description: str = None
):
    """Crea un Lakeouse en un área de trabajo.
    https://learn.microsoft.com/en-us/rest/api/fabric/lakehouse/items/create-lakehouse
    """
    api_url = (
        f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/lakehouses"
    )

    headers = {
        "Authorization": "Bearer " + access_token,
    }

    http_response = requests.post(
        api_url,
        headers=headers,
        json={"displayName": display_name, "description": description},
    )
    http_response.raise_for_status()
    return http_response.json()


def delete_lakehouse(access_token: str, workspace_id: str, lakehouse_id: str):
    """Borrar un Lakeouse de un área de trabajo.
    https://learn.microsoft.com/en-us/rest/api/fabric/lakehouse/items/delete-lakehouse
    """
    api_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/lakehouses/{lakehouse_id}"

    headers = {
        "Authorization": "Bearer " + access_token,
    }

    http_response = requests.delete(api_url, headers=headers)
    http_response.raise_for_status()
    return http_response.ok


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
    """Comandos para automatizar tareas de un Lakehouse de Fabric.

    Para ver la ayuda de un comando: pbicmd fabriclh <comando> --help

    """

    # Si se está ejecutando un comando, no ejecutar esta función
    if ctx.invoked_subcommand is not None:
        return

    # Mostrar la ayuda si no se pasa ningún parámetro
    ctx.get_help()


@app.command()
def list(
    workspace_id: Annotated[
        UUID,
        typer.Option(
            "--workspace",
            "-ws",
            help="ID de un área de trabajo Fabric.",
            show_default=False,
        ),
    ],
):
    """Lista los Lakehouses de un área de trabajo Fabric."""

    access_token = get_access_token(POWER_BI_SCOPE)

    lakehouses = list_lakehouses(access_token, workspace_id)

    for lh in lakehouses:
        print_json(data=lh)
        print()


@app.command()
def create(
    workspace_id: Annotated[
        UUID,
        typer.Option(
            "--workspace",
            "-ws",
            help="ID de un área de trabajo Fabric.",
            show_default=False,
        ),
    ],
    display_name: Annotated[
        str,
        typer.Option("--name", "-n", help="Nombre del Lakehouse", show_default=False),
    ],
    description: Annotated[
        str,
        typer.Option(
            "--desc", "-d", help="Descripción del Lakehouse", show_default=False
        ),
    ] = None,
):
    """Crea un Lakehouse en un área de trabajo Fabric."""

    access_token = get_access_token(POWER_BI_SCOPE)
    r = create_lakehouse(access_token, workspace_id, display_name, description)
    print_json(data=r)


@app.command()
def delete(
    workspace_id: Annotated[
        UUID,
        typer.Option(
            "--workspace",
            "-ws",
            help="ID de un área de trabajo Fabric.",
            show_default=False,
        ),
    ],
    lakehouse_id: Annotated[
        UUID,
        typer.Option(
            "--lakehouse",
            "-lh",
            help="ID del Lakehouse a borrar.",
            show_default=False,
        ),
    ],
):
    """Borra un Lakehouse de un área de trabajo Fabric."""

    access_token = get_access_token(POWER_BI_SCOPE)
    r = delete_lakehouse(access_token, workspace_id, lakehouse_id)
    print(r)
