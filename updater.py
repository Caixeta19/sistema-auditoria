"""
updater.py
──────────
Verifica automaticamente se há nova versão no GitHub e atualiza o sistema.

Como publicar uma atualização:
    1. Atualize VERSAO_SISTEMA em main.py (ex: "1.2" → "1.3")
    2. Gere o novo .exe:
       pyinstaller --onefile --windowed --name "Sistema de Auditoria" main.py
    3. No GitHub: Releases → New Release
       - Tag: v1.3
       - Título: Versão 1.3
       - Faça upload do "Sistema de Auditoria.exe" da pasta dist/
       - Publique
    4. Todas as máquinas com versão anterior vão receber o popup na próxima abertura
"""

import os
import sys
import threading
import subprocess
import requests
import tkinter.messagebox as messagebox

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO
# ──────────────────────────────────────────────────────────────────────────────

GITHUB_USUARIO = "Caixeta19"
GITHUB_REPO    = "sistema-auditoria"
NOME_EXE       = "Sistema de Auditoria.exe"

API_URL = f"https://api.github.com/repos/{GITHUB_USUARIO}/{GITHUB_REPO}/releases/latest"

# ──────────────────────────────────────────────────────────────────────────────


def _versao_para_tupla(versao: str) -> tuple:
    try:
        return tuple(int(x) for x in versao.strip("v").split("."))
    except:
        return (0,)


def verificar_atualizacao(versao_atual: str, parent_window=None) -> None:
    """
    Chame no __init__ do App:
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
        notas       = dados.get("body", "Correções e melhorias.")
        assets      = dados.get("assets", [])

        if not versao_nova:
            return

        if _versao_para_tupla(versao_nova) <= _versao_para_tupla(versao_atual):
            print(f"[Updater] Sistema atualizado (v{versao_atual})")
            return

        print(f"[Updater] Nova versão disponível: v{versao_nova}")

        url_download = None
        for asset in assets:
            if asset["name"] == NOME_EXE:
                url_download = asset["browser_download_url"]
                break

        if not url_download:
            print(f"[Updater] .exe não encontrado na release.")
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

        # Script batch que substitui o .exe após o processo fechar
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
            f"Não foi possível atualizar automaticamente.\n\nErro: {e}\n\n"
            "Baixe manualmente em:\n"
            f"https://github.com/{GITHUB_USUARIO}/{GITHUB_REPO}/releases/latest"
        )