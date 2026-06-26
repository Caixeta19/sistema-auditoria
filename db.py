import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from config import CLICKHOUSE

def _conectar():
    import clickhouse_connect
    return clickhouse_connect.get_client(
        host     = CLICKHOUSE["host"],
        port     = CLICKHOUSE["port"],
        database = CLICKHOUSE["database"],
        username = CLICKHOUSE["user"],
        password = CLICKHOUSE["password"],
        secure   = CLICKHOUSE["secure"]
    )

def carregar_todos_seriais() -> list[tuple]:
    view   = CLICKHOUSE["view"]
    coluna = CLICKHOUSE["coluna"]
    col_loja = CLICKHOUSE.get("coluna_loja", "Loja")
    col_nome = CLICKHOUSE.get("coluna_nome", "Nome")

    client = _conectar()
    # Puxa Serial, Loja e Nome
    resultado = client.query(f'SELECT `{coluna}`, `{col_loja}`, `{col_nome}` FROM `{view}`')
    
    dados = []
    for row in resultado.result_rows:
        if row[0] is not None:
            serial = str(row[0]).strip()
            loja = str(row[1]).strip() if row[1] is not None else "Sem Loja"
            nome = str(row[2]).strip() if row[2] is not None else "Sem Nome"
            dados.append((serial, loja, nome)) # Retorna os 3
    return dados

def serial_existe(serial: str) -> bool:
    view   = CLICKHOUSE["view"]
    coluna = CLICKHOUSE["coluna"]

    client = _conectar()
    resultado = client.query(
        f'SELECT 1 FROM `{view}` WHERE `{coluna}` = %(s)s LIMIT 1',
        parameters={"s": serial}
    )
    return len(resultado.result_rows) > 0

def testar_conexao() -> tuple[bool, str]:
    try:
        client = _conectar()
        client.query("SELECT 1")
        return True, ""
    except Exception as e:
        return False, str(e)