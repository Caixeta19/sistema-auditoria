import gspread
import os
import sys
import time
import threading
import tkinter.messagebox as messagebox

if getattr(sys, 'frozen', False):
    DIR_ATUAL = os.path.dirname(sys.executable)
else:
    DIR_ATUAL = os.path.dirname(__file__)

ARQUIVO_JSON = os.path.join(DIR_ATUAL, "sistemaauditoria-492914-84a65a922a10.json")
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1u7t9yQ7B8thedV8hOWWaul97w57jUpFalansk_4mye4/edit?gid=0#gid=0"

# ── Conexão reutilizada ───────────────────────────────────────────────────────
_gc  = None
_aba = None

# ── Lock global — garante que só uma thread grava por vez ────────────────────
_lock = threading.Lock()


def _get_aba():
    """Retorna a aba da planilha, reutilizando a conexão existente."""
    global _gc, _aba
    if _gc is None:
        _gc = gspread.service_account(filename=ARQUIVO_JSON)
    if _aba is None:
        planilha = _gc.open_by_url(URL_PLANILHA)
        _aba = planilha.sheet1
    return _aba


def registrar_bipagem(serial: str, status: str, horario: str, loja: str,
                      nome: str, origem: str, num_auditoria: str):
    status_legivel = {
        "ok":             "✅ Bipado com Sucesso",
        "ja_bipado":      "⚠️ Serial já bipado",
        "nao_encontrado": "❌ Não Encontrado",
        "erro":           "💥 Erro no Sistema",
    }
    status_final = status_legivel.get(status, status)
    linha = [status_final, serial, nome, loja, horario, origem, num_auditoria]

    # Lock garante que apenas uma thread grava por vez — sem sobreescrita
    with _lock:
        for tentativa in range(5):
            try:
                aba = _get_aba()
                aba.append_row(linha)
                return
            except gspread.exceptions.APIError as e:
                if e.response.status_code == 429:
                    espera = 2 ** tentativa
                    print(f"[Quota] Aguardando {espera}s antes de tentar novamente...")
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