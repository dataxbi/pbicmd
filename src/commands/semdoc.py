""" Este módulo contiene el comando 'semdoc', que genera ficheros HTML para documentar un modelo semántico publicado en el serevicio de Power BI.

- Utiliza la API REST de Power BI para ejecutar consultas DAX con las funciones INFO.

- Utiliza las plantillas Jinja para las páginas HTML. El código de dichas platillas está como textos al final de este módulo, en lugar de tener 
ficheros separados, para que todo esté contendio dentro del EXE y no tener que crear una carpeta con las plantillas en el ordenador del usuario.

- En las páginas HTML se utiliza la librería Javascript mermaid.js y el framework CSS Pico, en ambos casos se referencia el CDN para no tener que 
distribuir ningún fichero adicional.
"""

from pathlib import Path
from uuid import UUID
import os
from datetime import datetime
import webbrowser
import sys

import typer
from typing_extensions import Annotated
import pandas as pd
from jinja2 import Environment, DictLoader
from requests import HTTPError
from rich import print, inspect
from rich.console import Console
from rich.panel import Panel


from utils.azure_api import get_access_token
from utils.powerbi_api import POWER_BI_SCOPE, execute_dax, get_dataset
from utils.dax_utils import load_dax_result_to_dataframe
import utils.tom as tom


def semdoc_command(
    data_set: Annotated[
        UUID,
        typer.Argument(
            help="ID del modelo semántico en el servicio de Power BI.",
            show_default=False,
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Ruta a una carpeta donde se guardarán los ficheros HTML. Si la carpeta no exite, la crea. Si no se indica, se crea una carpeta con un nombre como semdoc-<dataset_id> donde <dataset_id> es e ID del modelo semántico.",
            show_default=False,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = None,
    no_browser: Annotated[
        bool,
        typer.Option(
            "--nobrowser",
            "-nb",
            help="Indica que no se abra el navegador por defecto al terminar de generar la documentación.",
        ),
    ] = False,
):
    """Genera páginas HTML con documentación de un modelo semántico publicado en el servicio de Power BI."""

    console = Console()

    # Valor por defecto de la carpeta de salida
    if output is None:
        output = f"./semdoc-{data_set}"

    # Obteniendo información del modelo semántico

    access_token = get_access_token(POWER_BI_SCOPE)

    print("Obteniendo los metadatos del modelo semántico...")

    try:
        semantic_model = get_semantic_model(access_token, data_set)
    except HTTPError as e:
        print_error(
            console,
            f"Ha ocurrido un error al tratar de obtener los metadatos del modelo semántico.\nCompruebe que tiene permisos para acceder al modelo y que el modelo conteniene alguna tabla.\nA continuación le mostramos el mensaje de error emitido por el servicio de Power BI.\n\n{e}",
        )
        sys.exit(1)

    # Generando los ficheros HTML

    print(f"Preparando la carpeta para guardar las páginas HTML: {output}")
    prepare_output_folder(output)

    environment = Environment(loader=DictLoader(jinja_templates))

    html_file_model = f"{output}/model.html"
    print(f"Generando la página HTML del modelo: {html_file_model}")
    generate_model_page(environment, "model.html", html_file_model, semantic_model)

    for table_id in semantic_model["tables"]["ID"]:
        html_file_table = f"{output}/table_{table_id}.html"
        print(
            f"Generando la página HTML para la tabla del modelo con el ID {table_id} en: {html_file_table}"
        )
        generate_table_page(
            table_id,
            environment,
            "table.html",
            html_file_table,
            semantic_model,
        )

    print(f"Ya todo está listo en la carpeta: {output}")

    if not no_browser:
        print(
            f"Se está abriendo la página {html_file_model} en el navegador web por defecto."
        )
        webbrowser.open(f"file://{os.path.abspath(html_file_model)}")


def prepare_output_folder(output):
    """Crear la carpeta de salida, sino existe.
    Y si existe, elimina los ficheros HTML que contenga."""
    if not os.path.exists(output):
        os.makedirs(output)
    else:
        for file in Path(output).glob("*"):
            if file.is_file() and file.match("model.html"):
                file.unlink()
            if file.is_file() and file.match("table_*.html"):
                file.unlink()


def generate_model_page(
    jinja_environment: Environment,
    jinja_template: str,
    html_file_path: str,
    semantic_model,
):
    """Crea una página HTML con información sobre el modelo semántico, incluyendo un diagrama mermaid con las relaciones entre las tablas.
    Utiliza la plantilla de Jira model.html.
    """

    dataset_info = semantic_model["dataset_info"]
    model_info = semantic_model["model_info"]
    tables = semantic_model["tables"]
    relationships = semantic_model["relationships"]

    mermaid_diagram = generate_mermaid_relationships(tables, relationships)
    template = jinja_environment.get_template(jinja_template)

    html_content = template.render(
        generation_time=semantic_model["generation_time"],
        dataset_info=dataset_info,
        model_info=model_info,
        mermaid_diagram=mermaid_diagram,
    )
    with open(html_file_path, mode="w", encoding="utf-8") as f:
        f.write(html_content)


def generate_table_page(
    table_id: int,
    jinja_environment: Environment,
    jinja_template: str,
    html_file_path: str,
    semantic_model,
):
    """Genera una página HTML con información sobre una tabla del modelo semántico.
    Utiliza la plantilla de Jira table.html.

    """

    dataset_info = semantic_model["dataset_info"]
    tables = semantic_model["tables"]
    columns = semantic_model["columns"]
    measures = semantic_model["measures"]
    relationships = semantic_model["relationships"]
    calculation_groups = semantic_model["calculation_groups"]
    calculation_items = semantic_model["calculation_items"]

    # Datos de la tabla
    t = tables[tables["ID"] == table_id].iloc[0].to_dict()
    table_name = t["Name"]
    table_visibility = "Oculta" if t["IsHidden"] else ""
    table_description = t["Description"]

    # Columnas de la tabla
    columns = columns[columns["TableID"] == table_id]
    table_columns = []
    for _, c in columns.iterrows():
        # No tener en cuenta la columna Row_Number
        if c["Type"] == tom.ColumnType.ROW_NUMBER:
            continue

        tc = {}
        tc["name"] = c["Name"]
        tc["visibility"] = "Oculta" if c["IsHidden"] else ""
        tc["data_type"] = (
            c["InferredDataType"].name
            if c["InferredDataType"] != tom.DataType.UNKNOWN
            else c["ExplicitDataType"].name
        )
        tc["format_string"] = ";<br>".join(str(c["FormatString"]).split(";"))
        tc["summarize_by"] = (
            c["SummarizeBy"].name
            if c["SummarizeBy"] != tom.AggregateFunction.NONE
            else ""
        )
        tc["sort_by"] = c["SortByColumnName"]
        tc["description"] = c["Description"]
        table_columns.append(tc)

    # Medidas de la tabla
    measures = measures[measures["TableID"] == table_id]
    table_measures = []
    for _, m in measures.iterrows():
        tm = {}
        tm["name"] = m["Name"]
        tm["visibility"] = "Oculta" if m["IsHidden"] else ""
        tm["data_type"] = m["DataType"].name
        tm["format_string"] = ";<br>".join(str(m["FormatString"]).split(";"))
        tm["expression"] = m["Expression"]
        tm["description"] = m["Description"]
        table_measures.append(tm)

    # Grupo de cálculo asociado a esta tabla, si hay alguno

    table_calculation_items = []
    if not calculation_groups.empty:
        calculation_groups = calculation_groups[
            calculation_groups["TableID"] == table_id
        ]

        if len(calculation_groups) > 0:
            cg = calculation_groups.iloc[0].to_dict()
            calculation_items = calculation_items[
                calculation_items["CalculationGroupID"] == cg["ID"]
            ]
            for _, ci in calculation_items.iterrows():
                tci = {}
                tci["name"] = ci["Name"]
                tci["expression"] = ci["Expression"]
                tci["ordinal"] = ci["Ordinal"]
                tci["description"] = ci["Description"]
                table_calculation_items.append(tci)

    # Filtra las relaciones que corresponden a table_id.
    relationships = relationships[
        (relationships["FromTableID"] == table_id)
        | (relationships["ToTableID"] == table_id)
    ]
    # Dibuja el diagrama de relaciones con esta tabla
    mermaid_diagram = generate_mermaid_relationships(
        tables, relationships, show_disconnected_tables=False
    )

    # Creando la página HTML a partir de la plantilla

    template = jinja_environment.get_template(jinja_template)

    html_content = template.render(
        generation_time=semantic_model["generation_time"],
        dataset_info=dataset_info,
        table_name=table_name,
        table_visibility=table_visibility,
        table_description=table_description,
        table_columns=table_columns,
        table_measures=table_measures,
        table_calculation_items=table_calculation_items,
        mermaid_diagram_relationships=mermaid_diagram,
    )
    with open(html_file_path, mode="w", encoding="utf-8") as f:
        f.write(html_content)


def generate_mermaid_relationships(
    tables: pd.DataFrame,
    relationships: pd.DataFrame,
    show_disconnected_tables: bool = True,
) -> str:
    """Genera el código mermaid para dibujar un diagrama que represente las relaciones entre las tablas del modelo."""
    tables_ids_in_relationships = list(
        set(relationships["FromTableID"]) | set(relationships["ToTableID"])
    )
    tables_in_relationships = pd.DataFrame(tables_ids_in_relationships, columns=["ID"])
    tables_in_relationships = tables_in_relationships.merge(
        tables[["ID", "Name"]], on="ID"
    )

    disconnected_tables = tables[~tables["ID"].isin(tables_ids_in_relationships)]
    disconnected_tables = disconnected_tables[["ID", "Name"]]

    mermaid_diagram = ""

    for _, r in tables_in_relationships.iterrows():
        mermaid_diagram += f'T{r["ID"]}[{r["Name"]}]\n'

    for _, r in relationships.iterrows():
        left_table = f'T{r["ToTableID"]}'
        right_table = f'T{r["FromTableID"]}'

        is_active = r["IsActive"]
        is_both_directions = (
            tom.CrossFilteringBehavior(r["CrossFilteringBehavior"])
            == tom.CrossFilteringBehavior.BOTHDIRECTIONS
        )
        arrow = ""
        if is_both_directions:
            arrow += "<"
        if is_active:
            arrow += "-->"
        else:
            arrow += "-.->"

        left_cardinality = tom.RelationshipEndCardinality(r["ToCardinality"])
        right_cardinality = tom.RelationshipEndCardinality(r["FromCardinality"])
        cardinality = "|"
        if left_cardinality == tom.RelationshipEndCardinality.ONE:
            cardinality += "1.."
        else:
            cardinality += "*.."
        if right_cardinality == tom.RelationshipEndCardinality.ONE:
            cardinality += "1"
        else:
            cardinality += "*"
        cardinality += "|"

        mermaid_diagram += f"{left_table} {arrow} {cardinality} {right_table} \n"

    if show_disconnected_tables:
        for _, r in disconnected_tables.iterrows():
            mermaid_diagram += f'T{r["ID"]}[{r["Name"]}]\n'

    for _, r in tables_in_relationships.iterrows():
        mermaid_diagram += f'click T{r["ID"]} "table_{r["ID"]}.html"\n'

    if show_disconnected_tables:
        for _, r in disconnected_tables.iterrows():
            mermaid_diagram += f'click T{r["ID"]} "table_{r["ID"]}.html"\n'

    # Si no hay datos en el diagrama, devolver una texto vacío
    if mermaid_diagram == "":
        return ""

    # Si hay datos, comenzar el texto indicando el tipo de gráfico que debe dibujar mermaid
    mermaid_diagram = "graph LR\n" + mermaid_diagram

    return mermaid_diagram


def get_semantic_model(access_token: str, dataset_id: UUID):
    """Devuelve un diccionario con información sobre un modelo semántico publicado en el servicio de Power BI."""
    dataset_info = get_dataset(access_token, dataset_id)
    model_info = get_model_info(access_token, dataset_id)
    tables = get_model_tables(access_token, dataset_id)
    columns = get_model_columns(access_token, dataset_id)
    measures = get_model_measures(access_token, dataset_id)
    relationships = get_model_relationships(access_token, dataset_id, tables)
    calculation_groups = get_model_calculation_groups(access_token, dataset_id)
    calculation_items = get_model_calculation_items(access_token, dataset_id)

    return {
        "generation_time": datetime.now().replace(microsecond=0).isoformat(),
        "dataset_info": dataset_info,
        "model_info": model_info,
        "tables": tables,
        "columns": columns,
        "measures": measures,
        "relationships": relationships,
        "calculation_groups": calculation_groups,
        "calculation_items": calculation_items,
    }


def get_model_info(access_token: str, dataset_id: UUID):
    """Devuelve un dicconario con informacion sobre el modelo semántico, utilizando la función DAX INFO.MODEL()."""
    dax_query = "EVALUATE INFO.MODEL()"
    model = execute_dax_to_dataframe(access_token, dataset_id, dax_query)

    model["Description"] = model["Description"].apply(
        lambda v: v if pd.notna(v) else ""
    )

    return model.iloc[0].to_dict()


def get_model_tables(access_token: str, dataset_id: UUID) -> pd.DataFrame:
    """Devuelve la lista de tablas del modelo."""
    dax_query = "EVALUATE INFO.TABLES()"
    tables = execute_dax_to_dataframe(access_token, dataset_id, dax_query)

    tables["Description"] = tables["Description"].apply(
        lambda v: v if pd.notna(v) else ""
    )

    return tables


def get_model_columns(access_token: str, dataset_id: UUID) -> pd.DataFrame:
    """Devuelve la lista de columnas del modelo."""
    dax_query = "EVALUATE INFO.COLUMNS()"
    columns = execute_dax_to_dataframe(access_token, dataset_id, dax_query)

    # Asegurando que las columnas por las que se van a hacer JOINs tengan tipos compatibles
    columns["ID"] = columns["ID"].astype("Int64")
    columns["SortByColumnID"] = columns["SortByColumnID"].astype("Int64")

    # Aplicando los Enum de TOM
    columns["Type"] = columns["Type"].apply(tom.ColumnType)
    columns["ExplicitDataType"] = columns["ExplicitDataType"].apply(tom.DataType)
    columns["InferredDataType"] = columns["InferredDataType"].apply(tom.DataType)
    columns["SummarizeBy"] = columns["SummarizeBy"].apply(tom.AggregateFunction)

    # Decidiendo cual es el nombre de la columna
    columns["Name"] = columns.apply(
        lambda c: (
            c["ExplicitName"] if pd.notna(c["ExplicitName"]) else c["InferredName"]
        ),
        axis=1,
    )

    # JOIN con las misma tabla para agregar una columna con el nombre de la clumna SortByColumn
    columns_sort_by = columns[["ID", "Name"]]
    columns_sort_by.columns = ["SortByColumnID", "SortByColumnName"]
    columns = pd.merge(columns, columns_sort_by, how="left", on="SortByColumnID")
    columns["SortByColumnName"] = columns["SortByColumnName"].apply(
        lambda v: v if pd.notna(v) else ""
    )

    # Sustituyendo nan por un texto vacío
    columns["Description"] = columns["Description"].apply(
        lambda v: v if pd.notna(v) else ""
    )
    columns["FormatString"] = columns["FormatString"].apply(
        lambda v: v if pd.notna(v) else ""
    )

    return columns


def get_model_measures(access_token: str, dataset_id: UUID) -> pd.DataFrame:
    """Devuelve la lista de medidas del modelo."""
    dax_query = "EVALUATE INFO.MEASURES()"
    measures = execute_dax_to_dataframe(access_token, dataset_id, dax_query)

    measures["DataType"] = measures["DataType"].apply(tom.DataType)

    measures["Description"] = measures["Description"].apply(
        lambda v: v if pd.notna(v) else ""
    )
    measures["FormatString"] = measures["FormatString"].apply(
        lambda v: v if pd.notna(v) else ""
    )

    return measures


def get_model_relationships(
    access_token: str, dataset_id: UUID, tables: pd.DataFrame
) -> pd.DataFrame:
    """Devuelve las relaciones del modelo."""
    dax_query = "EVALUATE INFO.RELATIONSHIPS()"
    relationships = execute_dax_to_dataframe(access_token, dataset_id, dax_query)

    tables_rel_from = tables[["ID", "Name"]]
    tables_rel_from.columns = ["FromTableID", "FromTableName"]
    relationships = pd.merge(
        relationships, tables_rel_from, how="left", on="FromTableID"
    )

    tables_rel_to = tables[["ID", "Name"]]
    tables_rel_to.columns = ["ToTableID", "ToTableName"]
    relationships = pd.merge(relationships, tables_rel_to, how="left", on="ToTableID")
    return relationships


def get_model_calculation_groups(access_token: str, dataset_id: UUID) -> pd.DataFrame:
    """Devuelve un DataFrame con los grupos de cálculo."""
    dax_query = "EVALUATE INFO.CALCULATIONGROUPS()"
    cg = execute_dax_to_dataframe(access_token, dataset_id, dax_query)

    if not cg.empty:
        cg["Description"] = cg["Description"].apply(lambda v: v if pd.notna(v) else "")

    return cg


def get_model_calculation_items(access_token: str, dataset_id: UUID) -> pd.DataFrame:
    """Devuelve un DataFrame con los calculation items."""
    dax_query = "EVALUATE INFO.CALCULATIONITEMS()"
    ci = execute_dax_to_dataframe(access_token, dataset_id, dax_query)

    if not ci.empty:
        ci["Description"] = ci["Description"].apply(lambda v: v if pd.notna(v) else "")

    return ci


def execute_dax_to_dataframe(
    access_token: str, dataset_id: UUID, dax_query: str
) -> pd.DataFrame:
    """Ejecuta una consulta DAX contra un modelo semántico y devuelve el resultado en un DataFrame Pandas."""
    r = execute_dax(access_token, dataset_id, dax_query)
    df = load_dax_result_to_dataframe(r)

    if not df.empty:
        # Quitando los corchetes de los nombres de las columnas
        df.columns = df.columns.str.replace(r"[\[\]]", "", regex=True)

    return df


def print_error(console, error_message):
    console.print(
        Panel(error_message, title="Error", title_align="left", border_style="red")
    )


# Las plantillas de Jinja se definen aquí mimso en lugar de en ficheros separados, para que todo esté contendio dentro del EXE
# y no tener que crear una carpeta con las plantillas en el ordenador del usuario.

jinja_templates = {
    "base.html": """
<!DOCTYPE html>
<html lang="en">
  <head>
    {% block head %}
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="color-scheme" content="light dark" />
    <link
      rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css"
    />
    <title>{% block title %}pbicmd semdoc{% endblock %}</title>
    {% endblock %}
  </head>
  <body>
    <header class="container">
        <hgroup>
            <h5 style="color:grey;">DOCUMENTACIÓN DE UN MODELO SEMÁNTICO DE POWER BI</h5>
            <span style="color:grey;">Fecha de generación: <strong>{{ generation_time }}</strong></span>
        </hgroup>
        <hr>
    </header>
    <main class="container">
    {% block content %}
    {% endblock %}
    </main>
    <footer class="container">  
        <hr>
        <small style="color:grey;">Esta documentación fue generada con la herramienta <a href="https://github.com/dataxbi/pbicmd" class="secondary">pbicmd</a></small>
    </footer>
    {% block script %}
    <script type="module">
      import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
      const config = {
        startOnLoad: true,
        flowchart: { useMaxWidth: true },
        securityLevel: "loose",
      };
      mermaid.initialize(config);
    </script>
    {% endblock %}
  </body>
</html>
""",
    "model.html": """
{% extends "base.html" %}
{% block title %}{{ dataset_info.name }}{% endblock %}
{% block content %}
<hgroup>
  <h3>{{ dataset_info.name }}</h3>
  <p>{{ model_info.Description }}</p>
</hgroup>


<div><small style="color:grey;">Haga clic sobre una tabla para ver más información.</small></div>
<pre class="mermaid">
{{ mermaid_diagram }}
</pre>
{% endblock %}
""",
    "table.html": """
{% extends "base.html" %}
{% block title %}Tabla: {{table_name}}{% endblock %}
{% block content %}
<hgroup>
  <h5><a href="model.html" style="text-decoration: none;">🡄</a> {{ dataset_info.name }}</h5>
  <h3>Tabla: {{table_name}}</h3>
  {% if table_visibility %}
  <h6>Visibilidad: {{table_visibility}}</h6>
  {% endif %}
  <p>
    {{table_description}}
  </p>
</hgroup>

<hr>
{% if table_columns %}
<a href="#columns">Columnas</a> 
{% endif %}
{% if table_measures %}
| <a href="#measures">Medidas</a>
{% endif %}
{% if table_calculation_items %}
| <a href="#calculation_items">Grupo de cálculo</a>
{% endif %}
{% if mermaid_diagram_relationships %}
| <a href="#relationships">Relaciones con otras tablas</a>
{% endif %}
<hr>

{% if table_columns %}
<h5 id="columns"><a href="#" style="text-decoration: none;">🡅</a> Columnas</h5>
<div class="overflow-auto"></div>
<table>
  <thead>
    <tr>
      <th>Columna</th>
      <th>Visibilidad</th>
      <th>Tipo</th>
      <th>Formato</th>
      <th>Resumen</th>
      <th>Ordenar por</th>
      <th>Descripción</th>
    </tr>  
  </thead>
  <tbody>
  {% for c in table_columns %}
  <tr>
    <td>{{ c.name }}</td>
    <td>{{ c.visibility }}</td>
    <td>{{ c.data_type }}</td>
    <td><small style="font-family:monoespace;">{{ c.format_string }}</small></td>
    <td>{{ c.summarize_by }}</td>
    <td>{{ c.sort_by }}</td>
    <td>
      {{ c.description }}
    </td>
  </tr>
  {% endfor %}
</tbody>
</table>
</div>
{% endif %}

{% if table_measures %}
<h5 id="measures"><a href="#" style="text-decoration: none;">🡅</a> Medidas</h5>
<div class="overflow-auto">
<table>
  <thead>
    <tr>
      <th>Medida</th>
      <th>Carpeta</th>
      <th>Visibilidad</th>
      <th>Tipo</th>
      <th>Formato</th>
      <th>Expresión DAX</th>
      <th>Descripción</th>
    </tr>
  </thead>
  <tbody>
    {% for m in table_measures %}
    <tr>
      <td><span id="mname{{loop.index}}">{{ m.name }}</span></td>
      <td>{{ m.display_folder }}</td>
      <td>{{ m.visibility }}</td>
      <td>{{ m.data_type }}</td>
      <td><small style="font-family:monoespace;">{{ m.format_string }}</small></td>
      <td>
        {% if m.expression %}
          <code onclick="openMeasureDialog('mname{{loop.index}}','mexp{{loop.index}}')" title="Haga clic para mostrar todo el código de la medida" style="cursor:pointer;">{{m.expression|truncate(100,True)}}</code>
          <pre id="mexp{{loop.index}}" style="display:none;">
            {{ m.expression }}
          </pre>
        {% endif %}
      </td>
      <td>
        {{ m.description }}
      </td>
    </tr>
    {% endfor %}
</tbody>
</table>
</div>
{% endif %}

{% if table_calculation_items %}
<h5 id="calculation_items"><a href="#" style="text-decoration: none;">🡅</a> Grupo de cálculo</h5>
<div class="overflow-auto"></div>
<table>
  <thead>
    <tr>
      <th>Item</th>
      <th>Expresión DAX</th>
      <th>Orden</th>
      <th>Descripción</th>
    </tr>
  </thead>
  <tbody>
  {% for ci in table_calculation_items %}
    <tr>
      <td><span id="ciname{{loop.index}}">{{ ci.name }}</span></td>
      <td>
        {% if ci.expression %}
          <pre onclick="openMeasureDialog('ciname{{loop.index}}','ciexp{{loop.index}}')" title="Haga clic para mostrar todo el código DAX" style="cursor:pointer;">{{ci.expression|truncate(300,True)}}</pre>
          <pre id="ciexp{{loop.index}}" style="display:none;">
            {{ ci.expression }}
          </pre>
        {% endif %}
      </td>
      <td>{{ ci.ordinal }}</td>
      <td>
        {{ ci.description }}
      </td>
    </tr>
  {% endfor %}
  </tbody>
</table>
</div>
{% endif %}

{% if mermaid_diagram_relationships %}
<h5 id="relationships"><a href="#" style="text-decoration: none;">🡅</a> Relaciones con otras tablas</h5>
<pre class="mermaid">
  {{ mermaid_diagram_relationships }}
</pre>
{% endif %}

{% endblock %}
{% block script %}
{{ super() }}
<script>
  function openMeasureDialog(measureNameId, measureExpressionId) {
    closeMeasureDialog();
    const measureName = document.querySelector('#' + measureNameId).innerText;
    const measureExpression = document.querySelector('#' + measureExpressionId).innerText;
    const dialog = document.createElement('dialog');
    dialog.setAttribute('id','measureDialog')
    dialog.setAttribute('open', '');
    dialog.innerHTML = `
      <article>
        <header>
          <button aria-label="Close" rel="prev" onclick="closeMeasureDialog()"></button>
          <p>
            <strong>${measureName}</strong>
          </p>
        </header>
        <pre style="max-width:100%;max-height:500px;overflow:auto;">${measureExpression}</pre>
      </article>
    `;    
    document.body.appendChild(dialog);
  }

  function closeMeasureDialog() {
      const dialog = document.querySelector('#measureDialog');
      if (dialog) {
          dialog.remove();
      }
  }
</script>

{% endblock %}

""",
}
