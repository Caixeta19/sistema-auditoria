"""
diagnostico_drive.py
──────────────────────────────────────────────────────────────────────────────
Confirma, de forma definitiva, se ID_PASTA_RAIZ está realmente dentro de um
Shared Drive (Drive Compartilhado) e se a Service Account tem acesso correto
a ele — a causa mais provável do erro storageQuotaExceeded.

Como usar:
  1) Coloque este arquivo na mesma pasta do gsheets.py (precisa do mesmo
     arquivo de credenciais da Service Account, sistemaauditoria-...json).
  2) Rode:  python diagnostico_drive.py
  3) Leia o resultado — ele te diz exatamente o que corrigir, se precisar.
──────────────────────────────────────────────────────────────────────────────
"""

import os
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.service_account import Credentials

BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "sistemaauditoria-492914-84a65a922a10.json")
ID_PASTA_RAIZ    = "1FxYNUvUBhw3uOLUEnpPCJTlu00c2Rswj"

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


def main():
    creds     = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    drive_svc = build("drive", "v3", credentials=creds, cache_discovery=False)

    print(f"Service Account: {creds.service_account_email}")
    print("=" * 72)

    # 1) A pasta raiz está DENTRO de um Shared Drive de verdade?
    print(f"[1] Verificando a pasta raiz (ID_PASTA_RAIZ = {ID_PASTA_RAIZ})")
    drive_id = None
    try:
        info = drive_svc.files().get(
            fileId=ID_PASTA_RAIZ,
            fields="id, name, driveId, mimeType, capabilities",
            supportsAllDrives=True,
        ).execute()

        print(f"    Nome.......: {info.get('name')}")
        print(f"    Tipo.......: {info.get('mimeType')}")

        drive_id = info.get("driveId")
        if drive_id:
            print(f"    ✅ ESTÁ dentro de um Shared Drive real.  driveId = {drive_id}")
        else:
            print("    ❌ NÃO está dentro de um Shared Drive — é uma pasta comum")
            print("       (do 'Meu Drive' de alguém, mesmo que compartilhada).")
            print("       ISSO explica o storageQuotaExceeded: a Service Account")
            print("       não tem cota própria e não pode ser dona de arquivos")
            print("       fora de um Shared Drive de verdade.")

        pode_criar = info.get("capabilities", {}).get("canAddChildren")
        print(f"    Permissão para criar arquivos aqui: {pode_criar}")

    except HttpError as e:
        print(f"    💥 Erro ao consultar a pasta: {e}")

    print("-" * 72)

    # 2) De quais Shared Drives a Service Account é MEMBRO de fato?
    print("[2] Shared Drives dos quais esta Service Account é membro:")
    try:
        resultado = drive_svc.drives().list(pageSize=50).execute()
        drives = resultado.get("drives", [])

        if not drives:
            print("    ⚠️  NENHUM Shared Drive encontrado para esta conta.")
            print("       Se a pasta do passo [1] pertence a um Shared Drive,")
            print("       a Service Account provavelmente só recebeu acesso a")
            print("       uma SUBPASTA, e não foi adicionada como MEMBRA do")
            print("       Shared Drive em si — o que não é a mesma coisa.")
        else:
            for d in drives:
                marcador = "👉" if d["id"] == drive_id else "  "
                print(f"    {marcador} {d['name']}   (id={d['id']})")

    except HttpError as e:
        print(f"    💥 Erro ao listar Shared Drives: {e}")

    print("=" * 72)
    print("O QUE FAZER a partir do resultado acima:")
    print()
    print("Se [1] mostrou '❌ NÃO está dentro de um Shared Drive', ou se o")
    print("Shared Drive dela não apareceu na lista do [2], o caminho é:")
    print()
    print("  a) No Google Drive, crie (ou identifique) um Shared Drive de")
    print("     verdade — no menu lateral esquerdo, em 'Drives compartilhados'")
    print("     (não em 'Meu Drive', mesmo que a pasta lá pareça compartilhada).")
    print(f"  b) Adicione {creds.service_account_email} como MEMBRA desse")
    print("     Shared Drive (não só compartilhe uma subpasta com ela).")
    print("  c) Crie a pasta raiz do sistema DENTRO desse Shared Drive e")
    print("     atualize ID_PASTA_RAIZ no gsheets.py com o novo ID.")


if __name__ == "__main__":
    main()