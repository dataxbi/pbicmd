import sys
from pathlib import Path
import csv
import json
from enum import StrEnum

import typer
from typing_extensions import Annotated
from pyarrow import csv as pacsv, parquet
import pandas as pd
from rich.console import Console
from rich.panel import Panel


class InputFormat(StrEnum):
    csv = "csv"
    json = "json"


class CsvDelimiterNotDetected(Exception):
    pass


def convert_csv_to_parquet(csv_file, parquet_file, delimiter):
    if delimiter is None:
        try:
            with open(csv_file, newline="") as csvfile:
                dialect = csv.Sniffer().sniff(csvfile.read(10_000))
                delimiter = dialect.delimiter
        except:
            raise CsvDelimiterNotDetected(
                f"no se pudo detectar el deimitador de celdas del archivo csv: {csv_file}"
            )

    parse_options = pacsv.ParseOptions(delimiter=delimiter)

    t = pacsv.read_csv(csv_file, parse_options=parse_options)
    parquet.write_table(t, parquet_file)


def convert_json_to_parquet(json_file, parquet_file):
    json_file_path = Path(json_file)
    try:
        json_text = json_file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        json_text = json_file_path.read_text()

    data = json.loads(json_text)
    df = pd.json_normalize(data)

    # Si alguna columna esta vacía, el tipo de datos será Null que puede no ser compatible con parquet
    # por tanto se buscan dichas columnas y se le cambia el tipo de dato a string.
    cols_with_all_nulls = df.columns[df.isnull().all()]
    df[cols_with_all_nulls] = df[cols_with_all_nulls].astype("string")

    df.to_parquet(parquet_file)


def print_error(error_message):
    Console().print(
        Panel(error_message, title="Error", title_align="left", border_style="red")
    )


def toparquet_command(
    input: Annotated[
        Path,
        typer.Argument(
            help="Ruta de origen a un archivo CSV o JSON o una carpeta con archivos CSV o JSON.",
            show_default=False,
            exists=True,
            file_okay=True,
            dir_okay=True,
            writable=False,
            readable=True,
            resolve_path=True,
        ),
    ],
    input_format: Annotated[
        InputFormat,
        typer.Option(
            "--inputformat",
            "-f",
            help="Formato de los archivos de entrada.",
            case_sensitive=False,
        ),
    ] = InputFormat.csv,
    input_pattern: Annotated[
        str,
        typer.Option(
            "--pattern",
            "-p",
            help="Patrón para filtrar los archivos de entrada cuando se indique una carpeta. Por ejemplo: yello_tripdata_*.csv. Por defecto se utiliza *.csv o *.json dependiendo del formato de entrada.",
            show_default=False,
        ),
    ] = None,
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Ruta de destino a un archivo Parquet o a una carpeta. Si no se indica, cada archivo Parquet se crea en la misma carpeta del archivo CSV de origen.",
            show_default=False,
            file_okay=True,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = None,
    delimiter: Annotated[
        str,
        typer.Option(
            "--delimiter",
            "-d",
            help="Delimitador de celdas del archivo CSV. Si no se indica, se trata de detectar el delimitador leyendo una muestra del archivo CSV.",
            show_default=False,
        ),
    ] = None,
):
    """Convierte archivos CSV o JSON a Parquet.
    Puede convertir un solo archivo o todos los archivos de una carpeta que cumplan con un patrón.
    """

    if input_pattern is None:
        if input_format == InputFormat.csv:
            input_pattern = "*.csv"
        else:
            input_pattern = "*.json"

    if input.is_file():
        output_file = input.with_suffix(".parquet")
        if output is not None:
            if output.is_dir():
                output_file = output / input.with_suffix(".parquet").name
            elif output.suffix == ".parquet":
                output_file = output
            else:
                print_error(
                    f'El destino "{output}" no es válido. Si el origen es un archivo, como destino debe indicar la ruta a un archivo con la extensión .parquet o a una carpeta que exista.'
                )
                sys.exit(2)

        print(f"Archivo origen: {input}")
        print(f"Archivo destino: {output_file}")

        try:
            if input_format == InputFormat.csv:
                convert_csv_to_parquet(input, output_file, delimiter)
            else:
                convert_json_to_parquet(input, output_file)

        except CsvDelimiterNotDetected:
            print_error(
                f"No se pudo detectar el delimitador de celdas del archivo CSV. Compruebe que el archivo es un CSV, y si lo es, indique un delimitador con el parámetro -d."
            )
            sys.exit(4)

        except:
            print_error(
                "Ocurrió un error leyendo el archivo de origen o escribiendo hacia el archivo de destino. Compruebe que el origen es un arhico CSV o JSON y que tiene permisos para crear o sobrescribir el archico de destino."
            )
            sys.exit(2)

    elif input.is_dir():

        if output is not None and not output.is_dir():
            print_error(
                f'El destino "{output}" no es válido. Si el origen es una carpeta, como destino debe indicar la ruta a una carpeta que exista.',
            )
            sys.exit(2)

        if output is None:
            output = input

        print(f"Carpeta origen: {input}")
        print(f"Patrón: {input_pattern}")
        print(f"Carpeta destino: {output}")

        for input_file in Path(input).glob(input_pattern):
            output_file = output / input_file.with_suffix(".parquet").name
            print()
            print(f"Archivo origen: {input_file}")
            print(f"Archivo destino: {output_file}")

            try:
                if input_format == InputFormat.csv:
                    convert_csv_to_parquet(input_file, output_file, delimiter)
                else:
                    convert_json_to_parquet(input_file, output_file)

            except CsvDelimiterNotDetected:
                print_error(
                    f"No se pudo detectar el delimitador de celdas del archivo CSV. Compruebe que el archivo es un CSV, y si lo es, indique un delimitador con el parámetro -d."
                )
                sys.exit(4)

    else:
        print_error(
            f'El origen "{output}" no es válido. Tiene que ser la ruta a un archivo CSV o a una carpeta que existan.'
        )
        sys.exit(3)
