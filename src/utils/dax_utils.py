from pathlib import Path

import pandas as pd


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


def load_dax_result_to_dataframe(dax_result) -> pd.DataFrame:
    """Crea un DataFrame con el contenido de la tabla con la respuesta a la consulta DAX.
    Retorna el DataFrame.
    """
    rows = dax_result["results"][0]["tables"][0]["rows"]
    # En el JSON que retorna la API de Power BI, puede ser que no todas las filas tengan las mismas columnas,
    # y json_normalize se encarga de revisar todo el JSON y crear todas las columnas, llenando con NaN las filas que no tengan alguna columna.
    return pd.json_normalize(rows)
