import os
import sys
import threading
import urllib.request
import urllib.error

# ── CONFIGURAÇÃO ─────────────────────────────────────────────────────────────
ID_VERSION_TXT = "1ym5iNknJe8xDwBIEkyRQ-IkCgu29blEw"
ID_APP_PY      = "1wgBxVrKblCR49k7iZg6y4sQqy6OFYxjW"
# ─────────────────────────────────────────────────────────────────────────────

def _url_drive(file_id: str) -> str:
    # URL de download direto do Google Drive
    return f"https://drive.google.com/uc?export=download&id={file_id}"

def _dir_app() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def verificar_e_atualizar(versao_atual, on_atualizado=None, on_sem_atualizacao=None, on_erro=None):
    def _worker():
        try:
            # Configuração de Headers para evitar bloqueio "robot" do Google
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

            # ── 1. Lê versão remota ──────────────────────────────────────────
            req_version = urllib.request.Request(_url_drive(ID_VERSION_TXT), headers=headers)
            with urllib.request.urlopen(req_version, timeout=10) as resp:
                versao_remota = resp.read().decode("utf-8").strip()

            if versao_remota == versao_atual:
                if on_sem_atualizacao:
                    on_sem_atualizacao()
                return

            # ── 2. Baixa novo app.py ─────────────────────────────────────────
            dir_app = _dir_app()
            caminho_temp = os.path.join(dir_app, "_app_update.py")
            caminho_final = os.path.join(dir_app, "app.py")

            req_app = urllib.request.Request(_url_drive(ID_APP_PY), headers=headers)
            with urllib.request.urlopen(req_app, timeout=15) as resp:
                conteudo_baixado = resp.read()

            # Salva temporariamente para validar
            with open(caminho_temp, "wb") as f:
                f.write(conteudo_baixado)

            # ── 3. Validação Robusta ─────────────────────────────────────────
            with open(caminho_temp, "r", encoding="utf-8", errors="ignore") as f:
                inicio_do_arquivo = f.read(500) # Lê os primeiros 500 caracteres

            # Se contiver <html> ou não tiver 'import', o Google enviou lixo/bloqueio
            if "<html" in inicio_do_arquivo.lower() or "import " not in inicio_do_arquivo.lower():
                if os.path.exists(caminho_temp):
                    os.remove(caminho_temp)
                raise ValueError("O Google Drive bloqueou o download direto. Tente novamente em instantes.")

            # ── 4. Substituição ──────────────────────────────────────────────
            if os.path.exists(caminho_final):
                os.replace(caminho_temp, caminho_final)
            else:
                os.rename(caminho_temp, caminho_final)

            if on_atualizado:
                on_atualizado(versao_remota)

        except Exception as e:
            if on_erro:
                on_erro(str(e))

    threading.Thread(target=_worker, daemon=True).start()