"""
gsheets.py — Integração Google Drive + Sheets
==============================================
Arquitetura:
  [PASTA RAIZ DO PROJETO]
    └── [NOME DA LOJA]
          └── "Auditoria — [LOJA] [N° AUDITORIA] [DD/MM]"

Autenticação: OAuth2 via oauth_client.json (arquivos ficam no Drive do usuário).
Token salvo em token.json para não pedir login toda vez.
"""

import os
import sys
import logging
import threading
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO PARA PYINSTALLER E AMBIENTE
# ---------------------------------------------------------------------------

if getattr(sys, 'frozen', False):
    # Se rodando como .exe compilado
    BASE_DIR = sys._MEIPASS # Pasta temporária onde o oauth_client.json é extraído
    PERSISTENT_DIR = os.path.dirname(sys.executable) # Pasta real onde o .exe está (para salvar o token)
else:
    # Se rodando como script Python .py normal
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PERSISTENT_DIR = BASE_DIR

CLIENT_FILE      = os.path.join(BASE_DIR, "oauth_client.json")
TOKEN_FILE       = os.path.join(PERSISTENT_DIR, "token.json")

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

ID_PASTA_RAIZ = "1FxYNUvUBhw3uOLUEnpPCJTlu00c2Rswj"

# Cabeçalhos da planilha
CABECALHOS = ["STATUS", "SERIAL", "NOME", "LOJA", "DATA E HORA", "ORIGEM", "N° Auditoria"]

# ---------------------------------------------------------------------------
# Logging & Cache
# ---------------------------------------------------------------------------

log = logging.getLogger("gsheets")

_cache_pastas_loja: dict[str, str]   = {}
_cache_planilhas:   dict[tuple, str] = {}
_lock_cache                          = threading.Lock()

# ---------------------------------------------------------------------------
# Autenticação OAuth2
# ---------------------------------------------------------------------------

def _get_services():
    """
    Retorna (drive_service, sheets_service) autenticados via OAuth2.
    Na primeira execução abre o navegador para autorização.
    Nas execuções seguintes usa o token salvo em token.json.
    """
    creds = None

    # Carrega token salvo se existir
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # Se não tem credencial válida, faz o login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Salva o token na pasta persistente para próximas execuções
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        log.info(f"[Auth] Token OAuth2 salvo com sucesso em: {TOKEN_FILE}")

    drive_svc  = build("drive",  "v3", credentials=creds, cache_discovery=False)
    sheets_svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return drive_svc, sheets_svc

# ---------------------------------------------------------------------------
# Utilitários do Drive
# ---------------------------------------------------------------------------

def _buscar_item_por_nome(drive_svc, nome: str, pasta_pai_id: str, mime_type: str) -> str | None:
    """Procura um arquivo ou pasta pelo nome dentro de `pasta_pai_id`."""
    nome_escaped = nome.replace("'", "\\'")
    query = (
        f"name = '{nome_escaped}' "
        f"and '{pasta_pai_id}' in parents "
        f"and mimeType = '{mime_type}' "
        f"and trashed = false"
    )
    try:
        resultado = drive_svc.files().list(
            q=query,
            fields="files(id, name)",
            pageSize=1,
        ).execute()
        arquivos = resultado.get("files", [])
        return arquivos[0]["id"] if arquivos else None
    except HttpError as e:
        log.error(f"[Drive] Erro ao buscar '{nome}': {e}")
        return None

def _criar_pasta(drive_svc, nome: str, pasta_pai_id: str) -> str:
    """Cria uma pasta no Drive do usuário e retorna seu ID."""
    metadata = {
        "name":     nome,
        "mimeType": "application/vnd.google-apps.folder",
        "parents":  [pasta_pai_id],
    }
    pasta = drive_svc.files().create(
        body=metadata,
        fields="id",
    ).execute()
    log.info(f"[Drive] Pasta criada: '{nome}' (id={pasta['id']})")
    return pasta["id"]

def _criar_planilha_com_cabecalhos(drive_svc, sheets_svc, nome: str, pasta_pai_id: str) -> str:
    """
    Cria uma planilha nova via Sheets API no Drive do usuário,
    insere os cabeçalhos dinamicamente e move para `pasta_pai_id`.
    """
    # 1. Cria a planilha coletando o ID da aba gerada (evita o bug do sheetId=0)
    planilha = sheets_svc.spreadsheets().create(
        body={
            "properties": {"title": nome},
            "sheets": [{"properties": {"title": "Sheet1"}}],
        },
        fields="spreadsheetId,sheets(properties(sheetId))",
    ).execute()
    
    planilha_id = planilha["spreadsheetId"]
    sheet_id = planilha["sheets"][0]["properties"]["sheetId"]
    log.info(f"[Sheets] Planilha criada: '{nome}' (id={planilha_id})")

    # 2. Insere cabeçalhos
    sheets_svc.spreadsheets().values().update(
        spreadsheetId    = planilha_id,
        range            = "Sheet1!A1:G1",
        valueInputOption = "RAW",
        body             = {"values": [CABECALHOS]},
    ).execute()
    log.info(f"[Sheets] Cabeçalhos inseridos")

    # 3. Formata cabeçalhos em negrito com fundo escuro
    try:
        sheets_svc.spreadsheets().batchUpdate(
            spreadsheetId = planilha_id,
            body = {
                "requests": [{
                    "repeatCell": {
                        "range": {
                            "sheetId":       sheet_id, # Usando o ID dinâmico capturado
                            "startRowIndex": 0,
                            "endRowIndex":   1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat":          {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                                "backgroundColor":     {"red": 0.26, "green": 0.26, "blue": 0.26},
                                "horizontalAlignment": "CENTER",
                            }
                        },
                        "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment)",
                    }
                }]
            }
        ).execute()
        log.info(f"[Sheets] Formatação aplicada")
    except Exception as e:
        log.warning(f"[Sheets] Formatação falhou (não crítico): {e}")

    # 4. Move para a pasta da loja
    arquivo = drive_svc.files().get(fileId=planilha_id, fields="parents").execute()
    pais_anteriores = ",".join(arquivo.get("parents", []))

    drive_svc.files().update(
        fileId=planilha_id,
        addParents=pasta_pai_id,
        removeParents=pais_anteriores,
        fields="id, parents",
    ).execute()
    log.info(f"[Drive] Planilha movida para pasta id={pasta_pai_id}")

    return planilha_id

# ---------------------------------------------------------------------------
# Lógica principal — garantir pasta e planilha
# ---------------------------------------------------------------------------

def _garantir_pasta_loja(drive_svc, nome_loja: str) -> str:
    with _lock_cache:
        if nome_loja in _cache_pastas_loja:
            return _cache_pastas_loja[nome_loja]

    pasta_id = _buscar_item_por_nome(
        drive_svc,
        nome         = nome_loja,
        pasta_pai_id = ID_PASTA_RAIZ,
        mime_type    = "application/vnd.google-apps.folder",
    )

    if not pasta_id:
        pasta_id = _criar_pasta(drive_svc, nome_loja, ID_PASTA_RAIZ)

    with _lock_cache:
        _cache_pastas_loja[nome_loja] = pasta_id

    return pasta_id

def _garantir_planilha_auditoria(drive_svc, sheets_svc, nome_loja: str, num_auditoria: str, pasta_loja_id: str) -> str:
    chave_cache = (nome_loja, num_auditoria)

    with _lock_cache:
        if chave_cache in _cache_planilhas:
            return _cache_planilhas[chave_cache]

    data_hoje     = datetime.now().strftime("%d/%m")
    nome_planilha = f"Auditoria — {nome_loja} {num_auditoria} {data_hoje}"

    planilha_id = _buscar_item_por_nome(
        drive_svc,
        nome         = nome_planilha,
        pasta_pai_id = pasta_loja_id,
        mime_type    = "application/vnd.google-apps.spreadsheet",
    )

    if not planilha_id:
        log.info(f"[Sheets] Criando planilha '{nome_planilha}'...")
        planilha_id = _criar_planilha_com_cabecalhos(
            drive_svc    = drive_svc,
            sheets_svc   = sheets_svc,
            nome         = nome_planilha,
            pasta_pai_id = pasta_loja_id,
        )

    with _lock_cache:
        _cache_planilhas[chave_cache] = planilha_id

    return planilha_id

# ---------------------------------------------------------------------------
# Inserção de dados
# ---------------------------------------------------------------------------

def _inserir_linha(sheets_svc, planilha_id: str, linha: list):
    """
    Adiciona uma linha no final da aba Sheet1.
    Colunas: STATUS | SERIAL | NOME | LOJA | DATA E HORA | ORIGEM | N° Auditoria
    """
    body = {"values": [linha]}
    sheets_svc.spreadsheets().values().append(
        spreadsheetId    = planilha_id,
        range            = "Sheet1!A:G",
        valueInputOption = "USER_ENTERED",
        insertDataOption = "OVERWRITE",  
        body             = body,
    ).execute()
    log.info(f"[Sheets] Linha inserida: {linha}")

# ---------------------------------------------------------------------------
# Função pública — chamada pelo sistema de bipagem
# ---------------------------------------------------------------------------

def registrar_bipagem(serial: str, resultado: str, str_hora: str, loja: str, nome: str, origem: str, num_auditoria: str) -> None:
    nome_loja = loja.strip() if loja and loja not in ("N/A", "Loja não identificada") else "LOJA_NAO_IDENTIFICADA"

    status_map = {
        "ok":             "Bipado com sucesso✅",
        "nao_encontrado": "Não Encontrado ❌",
        "erro":           "Erro 💥",
    }
    status_legivel = status_map.get(resultado, resultado)

    try:
        drive_svc, sheets_svc = _get_services()
        pasta_loja_id = _garantir_pasta_loja(drive_svc, nome_loja)
        planilha_id = _garantir_planilha_auditoria(
            drive_svc     = drive_svc,
            sheets_svc    = sheets_svc,
            nome_loja     = nome_loja,
            num_auditoria = num_auditoria,
            pasta_loja_id = pasta_loja_id,
        )

        linha = [status_legivel, serial, nome, loja, str_hora, origem, num_auditoria]
        _inserir_linha(sheets_svc, planilha_id, linha)

    except HttpError as e:
        log.error(f"[gsheets] HttpError ao registrar bipagem (serial={serial}): {e}")
        raise
    except Exception as e:
        log.error(f"[gsheets] Erro inesperado ao registrar bipagem (serial={serial}): {e}")
        raise