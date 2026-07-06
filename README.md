# Bipagem de Chips — ClickHouse (sem banco local)

Sistema de bipagem que:
- Carrega todos os seriais do ClickHouse ao abrir (lista com ❌)
- Ao bipar, a linha do serial vira ✅ na mesma posição
- Gera Excel com os seriais não encontrados + horário da bipagem
- **Sem MySQL, sem Postgres, sem Docker** — tudo em memória

---

## Configuração — PRIMEIRO PASSO

Abra `app/config.py` e preencha:

```python
CLICKHOUSE = {
    "host":     "seu-host-clickhouse",
    "port":     8123,          # HTTP: 8123 | HTTPS: 8443
    "database": "seu_banco",
    "user":     "seu_usuario",
    "password": "sua_senha",
    "view":     "nome_da_view",
    "coluna":   "IMEI/Serial",  # nome exato da coluna na view
    "secure":   False,          # True se usar HTTPS
}
```

---

## Como rodar

### 1. Instalar dependências

```bash
pip install -r requirements.txt
```

### 2. Abrir a tela

```bash
python app/app.py
```

---

## Fluxo da tela

```
Abre o app
    │
    ▼
Carrega TODOS os seriais do ClickHouse
Exibe lista com ❌ em cada um
    │
    ▼
Bipa um chip
    │
    ├─ Serial está na lista → linha vira ✅ (verde)
    ├─ Serial já foi bipado → aviso laranja ⚠️
    ├─ Serial não existe   → registra no log 🚫
    └─ Erro de conexão     → aviso roxo 💥
    │
    ▼
Botão "Gerar Relatório Excel"
→ Salva .xlsx com seriais não encontrados + horário
```

---

## Tela

| Cor | Significado |
|-----|-------------|
| 🟢 Verde   | Serial bipado com sucesso |
| 🟠 Laranja | Serial já foi bipado nesta sessão |
| 🔴 Vermelho | Serial não existe no ClickHouse |
| 🟣 Roxo    | Erro de conexão |

- Campo de **filtro** para buscar serial na lista
- **Contador** no rodapé: total / bipados / pendentes / não encontrados

---

## Estrutura

```
chips/
├── requirements.txt
├── README.md
└── app/
    ├── config.py    ← edite as credenciais aqui
    ├── db.py        ← lógica ClickHouse
    ├── relatorio.py ← geração do Excel
    └── app.py       ← interface Tkinter
```
