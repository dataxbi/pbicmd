from azure.identity import DefaultAzureCredential

AZURE_MANAGEMENT_SCOPE = "https://management.azure.com/.default"


def get_access_token(scope: str) -> str:
    """Se conecta a la API de Azure para pedir un token que autorice el acceso a un scope
    Retorna una cadena de texto con el token.
    """
    credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
    access_token = credential.get_token(scope)
    return access_token.token
