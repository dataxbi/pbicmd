"""pbicmd: Una herramienta de línea de comando para automatizar tareas de Power BI.

La idea es desarrollar una herramienta CLI (Command Line Interface) que ayude en la automatización de tareas de Power BI.
Se distribuye como un ejecutable EXE para Windows para que pueda ser utilizada sin instalar Python.

Ejecutando el script o el ejecutable sin parámetros, muestra la ayuda con los comandos disponibles.

Por ahora tiene un solo comando para ejecutar consultas DAX utilizando la API REST de Power BI.
La consulta DAX se lee desde un fichero y el resultado de ejecutar dicha consulta se guarda en un fichero CSV o Parquet.
El modelo semántico sobre el que se ejecuta la consulta se indica a través de un parámetro.

Las principales librerías que se utilizan son:
- Typer:            Para manejar los parámetros
- azure-identity:   Para la autenticación 

"""

from pathlib import Path
from uuid import UUID
from enum import StrEnum
from typing import Callable
import sys

from _version import __version__

import typer
from typing import List
from typing_extensions import Annotated
from azure.identity import DefaultAzureCredential
import requests
import pandas as pd
from pandas.core.groupby.generic import DataFrameGroupBy
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

    # Si se está ejecutando un comando, no ejecutar esta función
    if ctx.invoked_subcommand is not None:
        return

    if version:
        print(f"pbicmd {__version__}")
        return

    # Mostrar la ayuda si no se pasa ningún parámetro
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
    print_dax_result: Annotated[
        bool,
        typer.Option(
            "--print",
            "-p",
            help="Imprime el resultado de la consulta DAX. Si son más de 10 filas sólo imprime las 5 primeras y las 5 últimas filas.",
        ),
    ] = False,
):
    """Ejecuta una consulta DAX en un modelo semántico publicado en el servicio de Power BI."""
    dax_query = read_dax_query(file_dax)
    access_token = get_access_token()
    r = execute_dax(access_token, data_set, dax_query)
    df = load_dax_result_to_dataframe(r)

    if print_dax_result:
        print_dataframe(df)

    if output_file_path is None:
        # El nombre del fichero de salida por defecto es el nombre del fichero de la consulta y el nombre de dataset
        default_output_file_name = f"{file_dax.stem}-{data_set}"
        if output_file_format == OutputFileFormat.csv:
            output_file_path = f"{default_output_file_name}.csv"
        elif output_file_format == OutputFileFormat.parquet:
            output_file_path = f"{default_output_file_name}.parquet"

    if output_file_format == OutputFileFormat.csv:
        save_dataframe_to_csv(df, output_file_path)
    elif output_file_format == OutputFileFormat.parquet:
        save_dataframe_to_parquet(df, output_file_path)


# Nombre de la columna del resultado donde se indicará el dataset de origen de la fila (d1, d2)
COLUMN_NAME_SOURCE = "__origen__"
# Nombre de la columna del resultado donde se indicará las columnas que son diferentes
COLUMN_NAME_DIFFERENCES = "__diferencias__"


@app.command()
def daxdif(
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
    data_set1: Annotated[
        UUID,
        typer.Option(
            "--dataset1",
            "-d1",
            help="ID del primer modelo semántico en el servicio de Power BI donde ejecutar la consulta DAX.",
            show_default=False,
        ),
    ],
    data_set2: Annotated[
        UUID,
        typer.Option(
            "--dataset2",
            "-d2",
            help="ID del segundo modelo semántico en el servicio de Power BI donde ejecutar la consulta DAX.",
            show_default=False,
        ),
    ],
    dif_file_path: Annotated[
        Path,
        typer.Option(
            "--outputdif",
            "-od",
            help="Ruta a un fichero para guardar el resultado de la comparación.",
            show_default=False,
            dir_okay=False,
            resolve_path=True,
        ),
    ] = None,
    output_file1_path: Annotated[
        Path,
        typer.Option(
            "--output1",
            "-o1",
            help="Ruta a un fichero para guardar el resultado de la consulta DAX sobre el primero modelo semántico.",
            show_default=False,
            dir_okay=False,
            resolve_path=True,
        ),
    ] = None,
    output_file2_path: Annotated[
        Path,
        typer.Option(
            "--output2",
            "-o2",
            help="Ruta a un fichero para guardar el resultado de la consulta DAX sobre el segundo modelo semántico.",
            show_default=False,
            dir_okay=False,
            resolve_path=True,
        ),
    ] = None,
    columns_include_key: Annotated[
        List[str],
        typer.Option(
            "--keyinclude",
            "-ki",
            help="Columna a incluir como parte de la clave para identificar una fila. Para incluir varias columnas, utilice esta opción varias veces. Por defecto se usan todas las columnas de texto.",
            show_default=False,
        ),
    ] = None,
    columns_exclude_key: Annotated[
        List[str],
        typer.Option(
            "--keyexclude",
            "-ke",
            help="Columna a excluir de la clave para identificar una fila. Para excluir varias columnas, utilice esta opción varias veces. Por defecto se usan todas las columnas de texto.",
            show_default=False,
        ),
    ] = None,
    decimal_places: Annotated[
        int,
        typer.Option(
            "--decplaces",
            "-dp",
            help="Número de lugares decimales a los que redondear para las columnas numéricas.",
            show_default=True,
            min=0,
            max=8,
        ),
    ] = 4,
    tolerance: Annotated[
        float,
        typer.Option(
            "--tolerance",
            "-to",
            help="Margen de tolerancia cuando se van a restar dos valores numéricos.",
            show_default=True,
            min = 0,
        ),
    ] = 0.01,
    print_dif_result: Annotated[
        bool,
        typer.Option(
            "--print",
            "-p",
            help="Imprime el resultado de la comparación. Si son más de 10 filas sólo imprime las 5 primeras y las 5 últimas filas.",
        ),
    ] = False,
):
    """Compara el resultado de ejecutar una misma consulta DAX sobre dos modelos semánticos publicados en el servicio de Power BI."""

    console = Console()

    # Valores por defecto de los ficheros de salida

    if output_file1_path is None:
        output_file1_path = f"{file_dax.stem}_{data_set1}.csv"

    if output_file2_path is None:
        output_file2_path = f"{file_dax.stem}_{data_set2}.csv"

    if dif_file_path is None:
        dif_file_path = f"{file_dax.stem}_dif_{data_set1}_{data_set2}.csv"

    # Ejecutando la consulta

    dax_query = read_dax_query(file_dax)
    access_token = get_access_token()

    df1 = execute_dax_and_save(access_token, data_set1, dax_query, output_file1_path)
    print(
        f"Se ha ejecutado la consulta DAX sobre el primer modelo semántico y se ha guarado en el archivo: {output_file1_path}"
    )

    df2 = execute_dax_and_save(access_token, data_set2, dax_query, output_file2_path)
    print(
        f"Se ha ejecutado la consulta DAX sobre el segundo modelo semántico y se ha guarado en el archivo: {output_file2_path}"
    )

    # Determinando cuales columnas serán parte de la clave
    key_columns = get_dataframe_key_columns(
        df1, columns_include_key, columns_exclude_key
    )

    # La columnas que no sean parte de la clave, se usarán para la comparación.
    compare_columns = [c for c in df1.columns if c not in key_columns]

    print(f"Columnas claves: {key_columns}")
    print(f"Columnas a comparar: {compare_columns}")
    print(f"Lugares decimales para la comparación: {decimal_places}")
    print(f"Tolerancia para la comparación: {tolerance}")

    # Creando un DataFrame para hacer la conparación, donde estén concanedados los resultados ambos datasets
    df1[COLUMN_NAME_SOURCE] = "d1"
    df2[COLUMN_NAME_SOURCE] = "d2"
    df_union = pd.concat([df1, df2], ignore_index=True)
    df_union = df_union.round(decimal_places)

    # Agrupando ambos resultados por las columnas claves.
    # En cada grupo solo deben haber 2 filas, una por cada dataset.
    grouped_df = df_union.groupby(key_columns)

    # Si se encuentra algún grupo con más de 2 filas, significa que la clave no es correcta porque produce más de una fila por dataset.
    if (grouped_df.count() > 2).any(axis=None):
        console.print(
            "No se puede hacer la comparación porque el resultado de la consulta DAX tiene más de una fila para las columnas claves.",
            style="red",
        )
        print(
            "Utilice los parámetros -ki o -ke para definir correctamente las columnas claves."
        )
        sys.exit(2)

    df_dif = compare_grouped_dataframes(grouped_df, compare_columns, tolerance)

    # Si el DataFrame no está vacío indica que se encontraron diferencias
    if df_dif is not None:
        console.print(
            "Se encontraron diferencias al ejecutar la consulta DAX entre los dos modelos semánticos.",
            style="red",
        )

        save_dataframe_to_csv(df_dif, dif_file_path)
        print(f"Las diferencias se guardaron en el archivo: {dif_file_path}")

        if print_dif_result:
            print_dataframe(df_dif, add_dif_dataframe_rows_to_table)

        sys.exit(1)
    else:  # No se encontraron diferencias
        console.print(
            "¡Muy bien! No se encontraron diferencias al ejecutar la consulta DAX entre los dos modelos semánticos.",
            style="green",
        )


def read_dax_query(file_dax: Path) -> str:
    """Lee la consulta DAX desde un fichero.
    Si la consulta DAX tiene caracteres acentuados o con otros signos, por ejemplo, ñ, puede haber conflictos con decodificación.
    No hay una forma 100% segura de conocer la codificación de fun fichero, por lo que primero se asume que el fichero está codificado en UUTF-8
    y se trata de leer. Si se recibe un error al decodificar, se intenta leer de nuevo el fichero pero con la codificación por defecto del Sistema Operativo.
    """
    try:
        return file_dax.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return file_dax.read_text()


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


def print_dataframe(
    df: pd.DataFrame,
    fx_add_rows: Callable[[Table, pd.DataFrame], None] = add_dataframe_rows_to_table,
) -> None:
    """Imprime en la consola el contenido de un DataFrame utilizando la librería Rich.
    Si el DataFrame tiene más de 10 filas, solo imprime las primeas 5 y las últimas 5 filas.
    """
    table = Table(show_header=True, header_style="bold")

    df_print = df.astype("str")

    for column_name in df_print.columns:
        table.add_column(column_name)

    if df_print.shape[0] <= 10:
        fx_add_rows(table, df_print)
    else:
        fx_add_rows(table, df_print.head())
        table.add_row(*["..."] * df_print.shape[1])
        fx_add_rows(table, df_print.tail())

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


def execute_dax_and_save(
    access_token: str, dataset_id: UUID, dax_query: str, output_file_path: str
) -> pd.DataFrame:
    """Ejecuta una consulta DAX contra un modelos semántico y guarda el resultado en un archivo CSV.
    Retorna un DataFrame con el resultado."""
    r = execute_dax(access_token, dataset_id, dax_query)
    df = load_dax_result_to_dataframe(r)
    save_dataframe_to_csv(df, output_file_path)
    return df


def get_dataframe_key_columns(
    df: pd.DataFrame,
    columns_include_key: [str] = None,
    columns_exclude_key: [str] = None,
) -> [str]:
    """Decide cuales columnas de un DatFrame se van a utilizar como clave para identificar las filas."""
    key_columns = []

    for column_name, column_type in df.dtypes.items():
        if column_name in columns_include_key:
            key_columns.append(column_name)
            continue

        if column_name in columns_exclude_key:
            continue

        # la columna es de tipo texto
        if str(column_type) == "object":
            key_columns.append(column_name)

    return key_columns


def compare_grouped_dataframes(
    grouped_df: DataFrameGroupBy, compare_columns: [str] = None, tolerance: float = 0.01
) -> pd.DataFrame:
    df_dif = None

    for _, dfg in grouped_df:
        # Si no hay exactamente 2 filas, una por cada dataset, es que algún dataset tiene filas que el otro no
        # En ese caso, dichas filas se reportan como diferentes y se señalizan con el signo +
        if dfg.shape[0] != 2:
            dfg[COLUMN_NAME_DIFFERENCES] = "+"
            df_dif = pd.concat([df_dif, dfg], ignore_index=True)
            continue

        # Comparando los valores en las columnas numéricas.
        # Si se encuentran diferencias en una fila, se guarda la lista de las columnas con valores diferentes.
        found_dif = False
        dif_columns = []
        for c in compare_columns:
            if abs(dfg.iloc[0][c] - dfg.iloc[1][c]) > tolerance:
                found_dif = True
                dif_columns.append(c)
        if found_dif:
            dfg[COLUMN_NAME_DIFFERENCES] = "|".join(dif_columns)
            df_dif = pd.concat([df_dif, dfg], ignore_index=True)

    return df_dif


def add_dif_dataframe_rows_to_table(table: Table, df: pd.DataFrame) -> None:
    """Una función auxiliar utilizada por la función que imprime un DataFrame.
    Añade las filas de un DataFrame a una Table de la librería Rich.
    Formatea con colores las columnas con diferencias.
    """
    dif_df_columns = df.columns

    for _, row in df.iterrows():
        # Buscando si hay columnas con valores diferentes para marcarlas en rojo
        dif = row[COLUMN_NAME_DIFFERENCES]
        for c in dif.split("|"):
            if c in dif_df_columns:
                row[c] = f"[red]{row[c]}[/red]"

        # Agregando la fila a la tabla
        table.add_row(*list(row))


if __name__ == "__main__":
    app()
