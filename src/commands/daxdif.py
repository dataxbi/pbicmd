from pathlib import Path
from uuid import UUID
import sys

import typer
from typing import List
from typing_extensions import Annotated
import pandas as pd
from pandas.core.groupby.generic import DataFrameGroupBy
from rich.console import Console
from rich.table import Table

from utils.azure_api import get_access_token
from utils.powerbi_api import POWER_BI_SCOPE, execute_dax
from utils.dax_utils import read_dax_query, load_dax_result_to_dataframe
from utils.dataframe_utils import save_dataframe_to_csv, print_dataframe


# Nombre de la columna del resultado donde se indicará el dataset de origen de la fila (d1, d2)
COLUMN_NAME_SOURCE = "__origen__"
# Nombre de la columna del resultado donde se indicará las columnas que son diferentes
COLUMN_NAME_DIFFERENCES = "__diferencias__"


def daxdif_command(
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
            min=0,
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
    access_token = get_access_token(POWER_BI_SCOPE)

    df1 = execute_dax_and_save(access_token, data_set1, dax_query, output_file1_path)
    print(
        f"Se ha ejecutado la consulta DAX sobre el primer modelo semántico y se ha guardado en el archivo: {output_file1_path}"
    )

    df2 = execute_dax_and_save(access_token, data_set2, dax_query, output_file2_path)
    print(
        f"Se ha ejecutado la consulta DAX sobre el segundo modelo semántico y se ha guardado en el archivo: {output_file2_path}"
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
    columns_include_key: List[str] = None,
    columns_exclude_key: List[str] = None,
) -> List[str]:
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
    grouped_df: DataFrameGroupBy,
    compare_columns: List[str] = None,
    tolerance: float = 0.01,
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
