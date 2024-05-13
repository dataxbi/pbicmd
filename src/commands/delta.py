from pathlib import Path

import typer
from typing_extensions import Annotated
from deltalake import DeltaTable
from rich.console import Console
from rich.panel import Panel


def print_error(error_message):
    Console().print(
        Panel(error_message, title="Error", title_align="left", border_style="red")
    )


def delta_command(
    delta_folder: Annotated[
        Path,
        typer.Argument(
            help="Ruta a una carpeta que contiene una tabla Delta.",
            show_default=False,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ],
    delta_optimize: Annotated[
        bool,
        typer.Option(
            "--deltaoptimize",
            "-do",
            help="Optimiza la tabla Delta, consolidando varios archivos Parquet pequeños en un archivo más grande.",
            show_default=False,
        ),
    ] = False,
    delta_vacuum: Annotated[
        bool,
        typer.Option(
            "--deltavacuum",
            "-dv",
            help="Elimina los archivos que han sido marcados para borrar, con un período de retención de 7 días.",
            show_default=False,
        ),
    ] = False,
    delta_vacuum0: Annotated[
        bool,
        typer.Option(
            "--deltavacuum0",
            "-dv0",
            help="Elimina todos los archivos que han sido marcados para borrar, sin ningún período de retención.",
            show_default=False,
        ),
    ] = False,
):
    """Permite optimizar una tabla Delta."""

    if delta_optimize or delta_vacuum or delta_vacuum0:

        print()
        print(f"Ruta a la tabla Delta: {delta_folder}")

        dt = DeltaTable(delta_folder)

        if delta_optimize:
            print()
            print(
                "Optimizando la tabla Delta. Esta operación puede tardar varios minutos..."
            )

            ro = dt.optimize()

            print(
                f"La tabla Delta fue optimizada. {ro['numFilesRemoved']} archivo(s) marcado(s) para borrar. {ro['numFilesAdded']} archivo(s) creados(s)."
            )

        if delta_vacuum0:
            print()
            print("Ejecutando la operación VACUUM sin ningún período de retención...")
            deleted_files = dt.vacuum(
                dry_run=False, enforce_retention_duration=False, retention_hours=0
            )
            print(
                f"Operación VACUUM sin ningún período de retención aplicada a la tabla Delta. {len(deleted_files)} archivo(s) eliminado(s)."
            )
        elif delta_vacuum:
            print()
            print("Ejecutando la operación VACUUM con 7 días de retención...")
            deleted_files = dt.vacuum(dry_run=False)
            print(
                f"Operación VACUUM con 7 días de retención aplicada a la tabla Delta. {len(deleted_files)} archivo(s) eliminado(s)."
            )

    else:
        print_error("No se ha indicado ningún comando.")
