'''pbicmd: Una herramienta de línea de comando para automatizar tareas de Power BI.

La idea es desarrollar una herramienta CLI (Command Line Interface) que ayude en la automatización de tareas de Power BI.
Se distribuye como un ejecutable EXE para Windows para que pueda ser utilizada sin instalar Python.

Ejecutando el script o el ejecutable sin parámetros, muestra la ayuda con los comandos disponibles.

Por ahora tiene un solo comando para ejecutar consultas DAX utilizando la API REST de Power BI.
La consulta DAX se lee desde un fichero y el resultado de ejecutar dicha consulta se guarda en un fichero CSV o Parquet.
El modelo semántico sobre el que se ejecuta la consulta se indica a través de un parámetro.

Las principales librerías que se utilizan son:
- Typer:            Para manejar los parámetros
- azure-identity:   Para la autenticación 

'''

from pathlib import Path
from uuid import UUID
from enum import StrEnum

from _version import __version__

import typer
from typing_extensions import Annotated
from azure.identity import DefaultAzureCredential
import requests
import pandas as pd
from rich.console import Console
from rich.table import Table

POWER_BI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"
POWER_BI_API_BASE = "https://api.powerbi.com/v1.0/myorg"

class OutputFileFormat(StrEnum):
    csv = "csv"
    parquet = "parquet"

app = typer.Typer(add_completion=False)

@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    version: Annotated[
        bool, typer.Option("--version", "-v", help="Imprime la versión.")
    ] = False,
    help: Annotated[
        bool, typer.Option("--help", "-h", help="Imprime este mensaje de ayuda.")
    ] = False,
):
    """Una herramienta de línea de comando para automatizar tareas con Power BI.

    Para ver la ayuda de un comando: pbicmd <comando> --help

    Para más detalles visite https://www.dataxbi.com/pbicmd/
    """

    if version:
        print(f"pbicmd {__version__}")
        return

    ctx.get_help()


@app.command()
def dax(
    file_dax: Annotated[
        Path,
        typer.Argument(
            help="Ruta a un fichero con la consulta DAX.",
            show_default=False,
            exists=True,
            file_okay=True,
            dir_okay=False,
            writable=False,
            readable=True,
            resolve_path=True,
        ),
    ],
    data_set: Annotated[
        UUID,
        typer.Option(
            "--dataset",
            "-d",
            help="ID del modelo semántico en el servicio de Power BI.",
            show_default=False,
        ),
    ],
    output_file_path: Annotated[
        Path,
        typer.Option(
            "--outputfile",
            "-o",
            help="Ruta a un fichero para guardar el resultado de la consulta DAX.",
            show_default=False,
            dir_okay=False,
            resolve_path=True,
        ),
    ] = None,
    output_file_format: Annotated[
        OutputFileFormat,
        typer.Option(
            "--outputformat",
            "-f",
            help="Formato del fichero de salida.",
            case_sensitive=False,
        ),
    ] = OutputFileFormat.csv,
    print: Annotated[
        bool,
        typer.Option(
            "--print",
            "-p",
            help="Imprime el resultado de la consulta DAX. Si son más de 10 filas sólo imprime las 5 primeras y las 5 últimas filas.",
        ),
    ] = False,
):
    """Ejecuta una consulta DAX en un modelo semantico publicado en el servicio de Power BI."""
    dax_query = file_dax.read_text()

    access_token = get_access_token()

    r = execute_dax(access_token, data_set, dax_query)

    df = load_dax_result_to_dataframe(r)

    if print:
        print_dataframe(df)

    if output_file_path is None:
        default_output_file_name = file_dax.stem
        if output_file_format == OutputFileFormat.csv:
            output_file_path = f"{default_output_file_name}.csv"
        elif output_file_format == OutputFileFormat.parquet:
            output_file_path = f"{default_output_file_name}.parquet"

    if output_file_format == OutputFileFormat.csv:
        save_dataframe_to_csv(df, output_file_path)
    elif output_file_format == OutputFileFormat.parquet:
        save_dataframe_to_parquet(df, output_file_path)


def get_access_token() -> str:
    """Se conecta a la API de Azure para pedir un token que autorice el acceso a las API de Power BI
    Retorna una cadena de texto con el token.
    """
    credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
    access_token = credential.get_token(POWER_BI_SCOPE)
    return access_token.token


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
        api_url, headers=headers, json={"queries": [{"query": f"{dax_query}"}]}
    )

    http_response.raise_for_status()
    http_response.encoding = "utf-8-sig"
    return http_response.json()


def load_dax_result_to_dataframe(dax_result) -> pd.DataFrame:
    """Crea un DataFrame con el contenido de la tabla con la respuesta a la consulta DAX.
    Retorna el DataFrame.
    """
    rows = dax_result["results"][0]["tables"][0]["rows"]
    # En el JSON que retorna la API de Power BI, puede ser que no todas las filas tengan las mismas columnas,
    # y json_normalize se encarga de revisar todo el JSON y crear todas las columnas, llenando con NaN las filas que no tengan alguna columna.
    return pd.json_normalize(rows)


def add_dataframe_rows_to_table(table: Table, df: pd.DataFrame) -> None:
    """Una función auxiliar utilizada por la función que imprime un DataFrame.
    Añade las filas de un DataFrame a una Table de la librería Rich.
    """
    for _, row in df.iterrows():
        table.add_row(*list(row))


def print_dataframe(df: pd.DataFrame) -> None:
    """Imprime en la consola el contenido de un DataFrame utilizando la librería Rich.
    Si el DataFrame tiene más de 10 filas, sól imprime las primeas 5 y las últimas 5 filas.
    """
    table = Table(show_header=True, header_style="bold")

    df_print = df.astype("str")

    for column_name in df_print.columns:
        table.add_column(column_name)

    if df_print.shape[0] <= 10:
        add_dataframe_rows_to_table(table, df_print)
    else:
        add_dataframe_rows_to_table(table, df_print.head())
        table.add_row(*["..."] * df_print.shape[1])
        add_dataframe_rows_to_table(table, df_print.tail())

    console = Console()
    console.print(table)


def save_dataframe_to_csv(df: pd.DataFrame, file_path: str, **parameters) -> None:
    """Guarda el contenido de un DataFrame en un fichero CSV."""
    default_parameters = {"index": False, "sep": ";"}
    parameters = {**default_parameters, **parameters}
    df.to_csv(file_path, **parameters)


def save_dataframe_to_parquet(df: pd.DataFrame, file_path: str, **parameters) -> None:
    """Guarda el contenido de un DataFrame en un fichero Parquet."""
    default_parameters = {"index": False}
    parameters = {**default_parameters, **parameters}
    df.to_parquet(file_path, **parameters)


if __name__ == "__main__":
    app()
