from enum import StrEnum
from pathlib import Path
from uuid import UUID

import typer
from typing_extensions import Annotated

from utils.azure_api import get_access_token
from utils.powerbi_api import POWER_BI_SCOPE, execute_dax
from utils.dax_utils import read_dax_query, load_dax_result_to_dataframe
from utils.dataframe_utils import (
    save_dataframe_to_csv,
    save_dataframe_to_parquet,
    print_dataframe,
)


class OutputFileFormat(StrEnum):
    csv = "csv"
    parquet = "parquet"


def dax_command(
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
    access_token = get_access_token(POWER_BI_SCOPE)
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
