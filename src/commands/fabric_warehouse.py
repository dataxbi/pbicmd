from uuid import UUID

import typer
from typing_extensions import Annotated
import requests
from rich import print_json

from utils.azure_api import get_access_token
from utils.powerbi_api import POWER_BI_SCOPE


def restore_base_command(
    access_token: str, workspace_id: str, warehouse_id: str, json_body
):
    """Comando base que se utiliza en el resto de las llamadas de la API para hacer restauración del Warehouse"""
    api_url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datawarehouses/{warehouse_id}"

    headers = {
        "Authorization": "Bearer " + access_token,
    }

    http_response = requests.post(
        api_url,
        headers=headers,
        json=json_body,
    )

    http_response.raise_for_status()
    response_json = http_response.json()
    return response_json


def list_restore_points(access_token: str, workspace_id: str, warehouse_id: str):
    """Obtiene una lista de los puntos de restauración de un Warehouse."""
    json_body = {"commands": [{"$type": "WarehouseListRestorePointsCommand"}]}
    return restore_base_command(access_token, workspace_id, warehouse_id, json_body)


def create_restore_point(access_token: str, workspace_id: str, warehouse_id: str):
    """Crea un punto de restauración definido por el usuario."""
    json_body = {"commands": [{"$type": "WarehouseCreateRestorePointCommand"}]}
    return restore_base_command(access_token, workspace_id, warehouse_id, json_body)


def restore_warehouse(
    access_token: str,
    workspace_id: str,
    warehouse_id: str,
    restore_point_create_time: str,
):
    """Restaura un Warehouse al punto de restauración indicado por la fecha y hora de creación."""
    json_body = {
        "commands": [
            {
                "$type": "WarehouseRestoreInPlaceCommand",
                "RestorePoint": restore_point_create_time,
            }
        ]
    }
    return restore_base_command(access_token, workspace_id, warehouse_id, json_body)


def delete_restore_point(
    access_token: str,
    workspace_id: str,
    warehouse_id: str,
    restore_point_create_time: str,
):
    """Borra un punto de restauración creado por el usuario identificado por la fecha y hora de creación."""
    json_body = {
        "commands": [
            {
                "$type": "WarehouseDeleteRestorePointsCommand",
                "RestorePointsToDelete": [restore_point_create_time],
            }
        ]
    }
    return restore_base_command(access_token, workspace_id, warehouse_id, json_body)


app = typer.Typer(add_completion=False)


@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    help: Annotated[
        bool, typer.Option("--help", "-h", help="Imprime este mensaje de ayuda.")
    ] = False,
):
    """Comandos para automatizar tareas de un Warehouse de Fabric.

    Para ver la ayuda de un comando: pbicmd fabricwh <comando> --help

    """

    # Si se está ejecutando un comando, no ejecutar esta función
    if ctx.invoked_subcommand is not None:
        return

    # Mostrar la ayuda si no se pasa ningún parámetro
    ctx.get_help()


@app.command()
def listrestpoints(
    workspace_id: Annotated[
        UUID,
        typer.Option(
            "--workspace",
            "-ws",
            help="ID de un área de trabajo Fabric.",
            show_default=False,
        ),
    ],
    warehouse_id: Annotated[
        UUID,
        typer.Option(
            "--warehouse",
            "-wh",
            help="ID de un Warehouse de Fabric.",
            show_default=False,
        ),
    ],
):
    """Lista los puntos de restauración de un Warehouse de Fabric."""

    access_token = get_access_token(POWER_BI_SCOPE)

    restore_points = list_restore_points(access_token, workspace_id, warehouse_id)

    print_json(data=restore_points)


@app.command()
def createrestpoint(
    workspace_id: Annotated[
        UUID,
        typer.Option(
            "--workspace",
            "-ws",
            help="ID de un área de trabajo Fabric.",
            show_default=False,
        ),
    ],
    warehouse_id: Annotated[
        UUID,
        typer.Option(
            "--warehouse",
            "-wh",
            help="ID de un Warehouse de Fabric.",
            show_default=False,
        ),
    ],
):
    """Crea un punto de restauración definido por el usuario en un Warehouse de Fabric."""

    access_token = get_access_token(POWER_BI_SCOPE)

    r = create_restore_point(access_token, workspace_id, warehouse_id)

    print_json(data=r)


@app.command()
def restore(
    workspace_id: Annotated[
        UUID,
        typer.Option(
            "--workspace",
            "-ws",
            help="ID de un área de trabajo Fabric.",
            show_default=False,
        ),
    ],
    warehouse_id: Annotated[
        UUID,
        typer.Option(
            "--warehouse",
            "-wh",
            help="ID de un Warehouse de Fabric.",
            show_default=False,
        ),
    ],
    restore_point: Annotated[
        str,
        typer.Option(
            "--restpoint",
            "-rp",
            help="Fecha y hora de creación del punto de restauración-",
            show_default=False,
        ),
    ],
):
    """Restaura un Warehouse al punto de restauración indicado por su fecha y hora de creación."""

    access_token = get_access_token(POWER_BI_SCOPE)

    r = restore_warehouse(access_token, workspace_id, warehouse_id, restore_point)

    print_json(data=r)


@app.command()
def delrestpoint(
    workspace_id: Annotated[
        UUID,
        typer.Option(
            "--workspace",
            "-ws",
            help="ID de un área de trabajo Fabric.",
            show_default=False,
        ),
    ],
    warehouse_id: Annotated[
        UUID,
        typer.Option(
            "--warehouse",
            "-wh",
            help="ID de un Warehouse de Fabric.",
            show_default=False,
        ),
    ],
    restore_point: Annotated[
        str,
        typer.Option(
            "--restpoint",
            "-rp",
            help="Fecha y hora de creación del punto de restauración-",
            show_default=False,
        ),
    ],
):
    """Borra un punto de restauración creado por el usuario identificado por su fecha y hora de creación."""

    access_token = get_access_token(POWER_BI_SCOPE)

    r = delete_restore_point(access_token, workspace_id, warehouse_id, restore_point)

    print_json(data=r)
