import sys
from enum import StrEnum
from pathlib import Path
import csv
import json

import typer
from typing_extensions import Annotated
from pyarrow import csv as pacsv
import pandas as pd
from deltalake import write_deltalake
from rich.console import Console
from rich.panel import Panel


class DeltaMode(StrEnum):
    append = "append"
    overwrite = "overwrite"


class InputFormat(StrEnum):
    csv = "csv"
    json = "json"


class CsvDelimiterNotDetected(Exception):
    pass


def convert_csv_to_delta(
    csv_file, delta_folder, delta_mode="error", schema_mode="merge", csv_delimiter=None
):
    if csv_delimiter is None:
        try:
            with open(csv_file, newline="", encoding="utf-8") as csvfile:
                dialect = csv.Sniffer().sniff(csvfile.read(10_000))
                csv_delimiter = dialect.delimiter
        except Exception as ex:
            raise CsvDelimiterNotDetected(
                f"no se pudo detectar el deimitador de celdas del archivo csv: {csv_file}"
            )

    parse_options = pacsv.ParseOptions(delimiter=csv_delimiter)

    t = pacsv.read_csv(csv_file, parse_options=parse_options)
    write_deltalake(
        delta_folder, t, mode=delta_mode, schema_mode=schema_mode, engine="rust"
    )


def convert_json_to_delta(
    json_file, delta_folder, delta_mode="error", schema_mode="merge"
):
    json_file_path = Path(json_file)
    try:
        json_text = json_file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        json_text = json_file_path.read_text()

    data = json.loads(json_text)
    df = pd.json_normalize(data)

    # Si alguna columna esta vacía, el tipo de datos será Null que no es compatible con Delta
    # por tanto se buscan dichas columnas y se le cambia el tipo de dato a string.
    cols_with_all_nulls = df.columns[df.isnull().all()]
    df[cols_with_all_nulls] = df[cols_with_all_nulls].astype("string")

    write_deltalake(
        delta_folder, df, mode=delta_mode, schema_mode=schema_mode, engine="rust"
    )


def print_error(error_message):
    Console().print(
        Panel(error_message, title="Error", title_align="left", border_style="red")
    )


def todelta_command(
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
    output: Annotated[
        Path,
        typer.Argument(
            help="Ruta de destino a una carpeta que contendrá la tabla Delta. Si la carpeta no exite, la crea.",
            show_default=False,
            file_okay=False,
            dir_okay=True,
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
    delta_mode: Annotated[
        DeltaMode,
        typer.Option(
            "--deltamode",
            "-dm",
            show_default=False,
            help="Indica qué hacer si la tabla Delta ya existe, si sobrescribir o si anexar los datos de origen. Si no se indica y la tabla Delta ya existe, devuelve un error.",
            case_sensitive=False,
        ),
    ] = None,
    input_pattern: Annotated[
        str,
        typer.Option(
            "--pattern",
            "-p",
            help="Patrón para filtrar los archivos de entrada cuando se indique una carpeta. Por ejemplo: yello_tripdata_*.csv. Por defecto se utiliza *.csv o *.json dependiendo del formato de entrada.",
            show_default=False,
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
    """Convierte archivos CSV o JSON a una tabla Delta.
    Puede convertir un solo archivo o todos los archivos de una carpeta que cumplan con un patrón.
    """

    # Por defecto, si la tabla Delta ya existe, no se puede sobreescribir.
    if delta_mode is None:
        delta_mode = "error"

    # Por defecto, se aceptan cambios en el esquema
    schema_mode = "merge"
    # Pero si se indicó que se sobreescriba la tabla, se sobrescribe el esquema
    if delta_mode == DeltaMode.overwrite:
        schema_mode = "overwrite"

    if input_pattern is None:
        if input_format == InputFormat.csv:
            input_pattern = "*.csv"
        else:
            input_pattern = "*.json"

    if input.is_file():

        print(f"Archivo origen: {input}")
        print(f"Carpeta destino: {output}")

        if delta_mode != "error":
            print(f"Modo de escritura en la tabla Delta: {delta_mode}")

        print()

        try:
            if input_format == InputFormat.csv:
                convert_csv_to_delta(input, output, delta_mode, schema_mode, delimiter)
            else:
                convert_json_to_delta(input, output, delta_mode, schema_mode)

        except CsvDelimiterNotDetected:
            print_error(
                f"No se pudo detectar el delimitador de celdas del archivo CSV. Compruebe que el archivo es un CSV, y si lo es, indique un delimitador con el parámetro -d."
            )
            sys.exit(4)

        except FileExistsError:
            print_error(
                f"La tabla Delta ya existe y no se ha indicado ningún modo con el parámetro -dm."
            )
            sys.exit(5)

        except Exception as ex:
            print_error(
                "Ocurrió un error leyendo el archivo de origen o escribiendo hacia la tabla Delta."
                + "\n\nCompruebe que el origen es un arhivo CSV o JSON y que tiene permisos para crear o sobrescribir en la carpeta de destino."
                + "\nSi la tabla Delta ya existía, utiliza el parámetro -dm para indicar si quiere sobrescribir o anexar los nuevos datos."
                + "\n\nA continuación puedes ver el mensaje de error original:"
                + f"\n\n{ex}"
            )
            sys.exit(2)

    elif input.is_dir():

        print(f"Carpeta origen: {input}")
        print(f"Patrón: {input_pattern}")
        print(f"Carpeta destino: {output}")

        if delta_mode != "error":
            print(f"Modo de escritura en la tabla Delta: {delta_mode}")

        print()

        is_first_file = True
        for input_file in Path(input).glob(input_pattern):
            print(f"Procesando el archivo de origen: {input_file}")

            if not is_first_file:
                # Se fuerza el modo "append" a partir del segundo archivo de la carpeta, sin importar cual fue el modo escogido por el usuario.
                # Si el modo era "error" y la tabla ya existía, ya dió el error con el primer archivo.
                # Si el modo era "overwrite", ya el primer archivo sobrescribió la tabla Delta
                delta_mode = "append"
                # También se fuerza a que se pueda cambiar el esquema a partir del segun archivo
                schema_mode = "merge"

            is_first_file = False

            try:

                if input_format == InputFormat.csv:
                    convert_csv_to_delta(
                        input_file, output, delta_mode, schema_mode, delimiter
                    )
                else:
                    convert_json_to_delta(input_file, output, delta_mode, schema_mode)

            except CsvDelimiterNotDetected:
                print_error(
                    f"No se pudo detectar el delimitador de celdas del archivo CSV. Compruebe que el archivo es un CSV, y si lo es, indique un delimitador con el parámetro -d."
                )
                sys.exit(4)

            except FileExistsError:
                print_error(
                    f"La tabla Delta ya existe y no se ha indicado ningún modo con el parámetro -dm."
                )
                sys.exit(5)

            except Exception as ex:
                print_error(
                    "Ocurrió un error leyendo el archivo de origen o escribiendo hacia la tabla Delta."
                    + "\n\nCompruebe que el origen es un arhivo CSV o JSON y que tiene permisos para crear o sobrescribir en la carpeta de destino."
                    + "\nSi la tabla Delta ya existía, utiliza el parámetro -dm para indicar si quiere sobrescribir o anexar los nuevos datos."
                    + "\n\nA continuación puedes ver el mensaje de error original:"
                    + f"\n\n{ex}"
                )
                sys.exit(2)

    else:
        print_error(
            f'El origen "{input}" no es válido. Tiene que ser la ruta a un archivo CSV o JSON o a una carpeta que existan.'
        )
        sys.exit(3)
