"""
updater.py
──────────
Verifica se existe uma versão nova do sistema no GitHub e,
se existir, baixa e substitui o .exe automaticamente.

Como publicar uma atualização:
    1. Gere o novo .exe com PyInstaller
    2. Vá em github.com/Caixeta19/sistema-auditoria/releases/new
    3. Crie uma release com a tag "v1.3" (ou a versão nova)
    4. Faça upload do "Sistema de Auditoria.exe" como asset
    5. Publique — todas as máquinas detectam na próxima abertura
"""

import os
import sys
import threading
import requests
import subprocess
import tkinter.messagebox as messagebox

GITHUB_USUARIO = "Caixeta19"
GITHUB_REPO    = "sistema-auditoria"
NOME_EXE       = "SistemaAuditoria.exe"

API_URL = f"https://api.github.com/repos/{GITHUB_USUARIO}/{GITHUB_REPO}/releases/latest"


def _versao_para_tupla(versao: str) -> tuple:
    try:
        return tuple(int(x) for x in versao.strip("v").split("."))
    except:
        return (0,)


def verificar_atualizacao(versao_atual: str, parent_window=None) -> None:
    """
    Chame no __init__ do App:
        import updater
        updater.verificar_atualizacao(VERSAO_SISTEMA, self)
    """
    threading.Thread(
        target=_checar,
        args=(versao_atual, parent_window),
        daemon=True
    ).start()


def _checar(versao_atual: str, parent_window) -> None:
    try:
        resp = requests.get(API_URL, timeout=10)
        if resp.status_code != 200:
            return

        dados       = resp.json()
        versao_nova = dados.get("tag_name", "").strip("v")
        notas       = dados.get("body", "Sem notas de atualização.")
        assets      = dados.get("assets", [])

        if not versao_nova:
            return

        if _versao_para_tupla(versao_nova) <= _versao_para_tupla(versao_atual):
            print(f"[Updater] Sistema atualizado (v{versao_atual})")
            return

        print(f"[Updater] Nova versão encontrada: v{versao_nova}")

        url_download = None
        for asset in assets:
            if asset["name"] == NOME_EXE:
                url_download = asset["browser_download_url"]
                break

        if not url_download:
            print(f"[Updater] .exe '{NOME_EXE}' não encontrado na release.")
            return

        if parent_window:
            parent_window.after(0, lambda: _perguntar_e_atualizar(
                versao_atual, versao_nova, notas, url_download
            ))
        else:
            _perguntar_e_atualizar(versao_atual, versao_nova, notas, url_download)

    except Exception as e:
        print(f"[Updater] Erro ao verificar atualização: {e}")


def _perguntar_e_atualizar(versao_atual, versao_nova, notas, url_download):
    resposta = messagebox.askyesno(
        "Atualização disponível",
        f"Nova versão disponível: v{versao_nova}  (atual: v{versao_atual})\n\n"
        f"O que há de novo:\n{notas[:300]}\n\n"
        "Deseja atualizar agora?\n"
        "(O sistema será reiniciado automaticamente)"
    )
    if resposta:
        _baixar_e_substituir(url_download)


def _baixar_e_substituir(url_download: str) -> None:
    try:
        exe_atual = sys.executable
        exe_novo  = exe_atual + ".new"
        exe_bkp   = exe_atual + ".bkp"

        messagebox.showinfo("Atualizando", "Baixando atualização... Aguarde.")

        resp = requests.get(url_download, stream=True, timeout=120)
        resp.raise_for_status()

        with open(exe_novo, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        bat = exe_atual + "_update.bat"
        with open(bat, "w") as f:
            f.write(f"""@echo off
timeout /t 2 /nobreak >nul
move /y "{exe_atual}" "{exe_bkp}"
move /y "{exe_novo}" "{exe_atual}"
start "" "{exe_atual}"
del "%~f0"
""")

        subprocess.Popen(bat, shell=True)
        sys.exit(0)

    except Exception as e:
        messagebox.showerror(
            "Erro na atualização",
            f"Não foi possível atualizar.\n\nErro: {e}\n\nTente atualizar manualmente."
        )