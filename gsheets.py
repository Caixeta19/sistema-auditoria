import gspread
import os
import sys
import time
import tkinter.messagebox as messagebox

if getattr(sys, 'frozen', False):
    DIR_ATUAL = os.path.dirname(sys.executable)
else:
    DIR_ATUAL = os.path.dirname(__file__)

ARQUIVO_JSON = os.path.join(DIR_ATUAL, "sistemaauditoria-492914-84a65a922a10.json")

# E-mails que receberão acesso de editor em cada planilha criada.
# Adicione ou remova e-mails conforme necessário.
EMAILS_EDITORES = [
    "email1@gmail.com",   # <- substitua pelos e-mails reais
    "email2@gmail.com",
    "email3@gmail.com",
]

CABECALHO = ["Status", "Serial", "Nome", "Loja", "Data e Hora", "Origem", "Nº Auditoria"]

# ── Conexão e cache ───────────────────────────────────────────────────────────
_gc = None
_planilhas_cache: dict[str, gspread.Spreadsheet] = {}  # nome_loja → Spreadsheet


def _get_gc() -> gspread.Client:
    global _gc
    if _gc is None:
        _gc = gspread.service_account(filename=ARQUIVO_JSON)
    return _gc


def _get_planilha_loja(loja: str) -> gspread.Worksheet:
    """
    Retorna a sheet1 da planilha da loja.
    Se a planilha não existir, cria e compartilha com EMAIL_DONO.
    Usa cache em memória — a API só é chamada na primeira vez por loja.
    Compartilha com todos os e-mails de EMAILS_EDITORES ao criar.
    """
    nome = loja.strip()[:100]
    titulo = f"Auditoria — {nome}"   # ex: "Auditoria — TO - GURUPI"

    if nome in _planilhas_cache:
        return _planilhas_cache[nome].sheet1

    gc = _get_gc()

    # Tenta abrir planilha existente pelo título
    try:
        planilha = gc.open(titulo)
        print(f"[Sheets] Planilha existente: '{titulo}'")
    except gspread.exceptions.SpreadsheetNotFound:
        # Cria a planilha nova
        planilha = gc.create(titulo)

        # Compartilha com todos os e-mails da lista como editores
        for email in EMAILS_EDITORES:
            planilha.share(email, perm_type="user", role="writer", notify=False)

        # Formata o cabeçalho na primeira aba
        ws = planilha.sheet1
        ws.update_title(nome)                              # renomeia a aba
        ws.append_row(CABECALHO, value_input_option="RAW")
        ws.format("A1:G1", {
            "textFormat": {"bold": True},
            "backgroundColor": {"red": 0.88, "green": 0.88, "blue": 0.88}
        })
        print(f"[Sheets] Planilha criada e compartilhada: '{titulo}'")

    _planilhas_cache[nome] = planilha
    return planilha.sheet1


def registrar_bipagem(serial: str, status: str, horario: str, loja: str,
                      nome: str, origem: str, num_auditoria: str):

    loja_limpa = loja.strip()
    if not loja_limpa or loja_limpa.upper() in ("TODAS AS LOJAS", "LOJA NÃO IDENTIFICADA", "N/A"):
        print(f"[Sheets] Ignorado — nenhuma loja selecionada no filtro.")
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