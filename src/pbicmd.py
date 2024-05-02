"""pbicmd: Una herramienta de línea de comando para automatizar tareas de Power BI.

La idea es desarrollar una herramienta CLI (Command Line Interface) que ayude en la automatización de tareas de Power BI.
Se distribuye como un ejecutable EXE para Windows para que pueda ser utilizada sin instalar Python.

Ejecutando el script o el ejecutable sin parámetros, muestra la ayuda con los comandos disponibles.

Los comandos están definidos en ficheros separados en la subcarpeta commands.

"""

from _version import __version__

import typer
from typing_extensions import Annotated

import commands.dax as dax
import commands.daxdif as daxdif
import commands.fabric as fabric
import commands.fabric_lakehouse as fabriclh
import commands.toparquet as toparquet
import commands.todelta as todelta

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


app.command(name="dax")(dax.dax_command)
app.command(name="daxdif")(daxdif.daxdif_command)
app.command(name="toparquet")(toparquet.toparquet_command)
app.command(name="todelta")(todelta.todelta_command)
app.add_typer(fabric.app, name="fabric")
app.add_typer(fabriclh.app, name="fabriclh")


if __name__ == "__main__":
    app()
