import gspread
import os
import sys
import time
import tkinter.messagebox as messagebox
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

if getattr(sys, 'frozen', False):
    DIR_ATUAL = os.path.dirname(sys.executable)
else:
    DIR_ATUAL = os.path.dirname(__file__)

ARQUIVO_OAUTH = os.path.join(DIR_ATUAL, "oauth_client.json")
ARQUIVO_TOKEN = os.path.join(DIR_ATUAL, "token.json")

EMAILS_EDITORES = [
    "auxiliar.auditoriaa03@gmail.com",
    "auxiliar.auditoriaa02@gmail.com",
    "auxiliar.auditoriaa04@gmail.com",
]

CABECALHO = ["Status", "Serial", "Nome", "Loja", "Data e Hora", "Origem", "Nº Auditoria"]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ── Conexão e cache ───────────────────────────────────────────────────────────
_gc = None
_planilhas_cache: dict[str, gspread.Spreadsheet] = {}


def _get_gc() -> gspread.Client:
    global _gc
    if _gc is not None:
        return _gc

    creds = None

    if os.path.exists(ARQUIVO_TOKEN):
        creds = Credentials.from_authorized_user_file(ARQUIVO_TOKEN, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(ARQUIVO_OAUTH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(ARQUIVO_TOKEN, "w") as f:
            f.write(creds.to_json())

    _gc = gspread.authorize(creds)
    return _gc


def _get_planilha_loja(loja: str) -> gspread.Worksheet:
    nome   = loja.strip()[:100]
    titulo = f"Auditoria — {nome}"

    if nome in _planilhas_cache:
        return _planilhas_cache[nome].sheet1

    gc = _get_gc()

    try:
        planilha = gc.open(titulo)
        print(f"[Sheets] Planilha existente: '{titulo}'")
    except gspread.exceptions.SpreadsheetNotFound:
        planilha = gc.create(titulo)

        for email in EMAILS_EDITORES:
            try:
                planilha.share(email, perm_type="user", role="writer", notify=False)
            except Exception as e:
                print(f"[Sheets] Não compartilhou com {email}: {e}")

        ws = planilha.sheet1
        ws.update_title(nome)
        ws.append_row(CABECALHO, value_input_option="RAW")
        ws.format("A1:G1", {
            "textFormat": {"bold": True},
            "backgroundColor": {"red": 0.88, "green": 0.88, "blue": 0.88}
        })
        print(f"[Sheets] Planilha criada: '{titulo}'")

    _planilhas_cache[nome] = planilha
    return planilha.sheet1


def registrar_bipagem(serial: str, status: str, horario: str, loja: str,
                      nome: str, origem: str, num_auditoria: str):

    loja_limpa = loja.strip()
    if not loja_limpa or loja_limpa.upper() in ("TODAS AS LOJAS", "LOJA NÃO IDENTIFICADA", "N/A"):
        print(f"[Sheets] Ignorado — nenhuma loja selecionada.")
        return

    status_legivel = {
        "ok":             "✅ Bipado com Sucesso",
        "ja_bipado":      "⚠️ Serial já bipado",
        "nao_encontrado": "❌ Não Encontrado",
        "erro":           "💥 Erro no Sistema",
    }
    status_final = status_legivel.get(status, status)
    linha = [status_final, serial, nome, loja_limpa, horario, origem, num_auditoria]

    for tentativa in range(5):
        try:
            ws = _get_planilha_loja(loja_limpa)
            ws.append_row(linha)
            return
        except gspread.exceptions.APIError as e:
            if e.response.status_code == 429:
                espera = 2 ** tentativa
                print(f"[Quota] Aguardando {espera}s...")
                time.sleep(espera)
            else:
                messagebox.showerror(
                    "Falha ao enviar para o Google Sheets",
                    f"Não foi possível salvar o serial {serial}.\n\nDetalhe técnico:\n{e}"
                )
                return
        except Exception as e:
            messagebox.showerror(
                "Falha ao enviar para o Google Sheets",
                f"Não foi possível salvar o serial {serial}.\n\nDetalhe técnico:\n{e}"
            )
            return

    messagebox.showerror(
        "Falha ao enviar para o Google Sheets",
        f"Não foi possível salvar o serial {serial} após várias tentativas.\n"
        "Tente novamente em alguns segundos."
    )