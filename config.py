# ---------------------------------------------------------------------------
# config.py
# ---------------------------------------------------------------------------

CLICKHOUSE = {
    "host":     "clickhouse-vivogo-4r.before.com.br", 
    "port":     8123,                     # <-- Porta HTTP
    "database": "syscor_geral",
    "user":     "4redes_user_bi",
    "password": "ptJwWr8s63A7hIWJ",
    "view":     "chview_estoque_mt_4redes",    # <-- O nome da sua view!
    "coluna":   "IMEI/Serial",    
    "coluna_loja": "Nome da loja do estoque", 
    "coluna_nome": "Modelo Comercial",      
    "secure":   False,                    # <-- OBRIGATÓRIO SER FALSE
}