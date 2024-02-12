import pandas as pd
from rich.table import Table
from rich.console import Console
from typing import Callable


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
