"""
lote.py — Módulo de bipagem em lote por faixa de ICCID
Usa o algoritmo de Luhn para calcular o dígito verificador de cada serial.
"""


def _luhn_digito(numero_sem_dv: str) -> str:
    """
    Recebe o ICCID sem o último dígito (dígito verificador) e retorna o DV correto.
    Algoritmo conforme modelo da planilha:
      1. Inverte os dígitos (sem o DV)
      2. Multiplica alternadamente por 2 e 1 começando pelo primeiro (após inversão)
      3. Para cada produto >= 10, soma os dígitos (ou: parte_inteira/10 + resto/10)
      4. Soma tudo
      5. DV = resto((10 – resto(soma / 10)) / 10)
         → Se soma % 10 == 0 → DV = 0; senão DV = 10 - (soma % 10)
    """
    digits = [int(d) for d in reversed(numero_sem_dv)]
    total = 0
    for i, d in enumerate(digits):
        if i % 2 == 0:          # posições pares (0,2,4…) → fator 2
            produto = d * 2
            total += produto // 10 + produto % 10
        else:                    # posições ímpares → fator 1
            total += d
    dv = (10 - (total % 10)) % 10
    return str(dv)


def iccid_valido(iccid: str) -> bool:
    """Verifica se um ICCID completo tem DV correto."""
    if len(iccid) < 2 or not iccid.isdigit():
        return False
    esperado = _luhn_digito(iccid[:-1])
    return iccid[-1] == esperado


def gerar_iccid(base_sem_dv: str) -> str:
    """Dado o corpo do ICCID (sem DV), retorna o ICCID completo com DV."""
    return base_sem_dv + _luhn_digito(base_sem_dv)


def gerar_faixa(primeiro: str, ultimo: str) -> tuple[list[str], str | None]:
    """
    Gera todos os ICCIDs entre `primeiro` e `ultimo` (inclusive), recalculando
    o dígito verificador para cada número intermediário.

    Retorna (lista_de_seriais, erro_ou_None).
    """
    primeiro = primeiro.strip()
    ultimo   = ultimo.strip()

    # ── Validações básicas ────────────────────────────────────────────────────
    if not primeiro.isdigit() or not ultimo.isdigit():
        return [], "Os seriais devem conter apenas dígitos."

    if len(primeiro) != len(ultimo):
        return [], "Os seriais devem ter o mesmo número de dígitos."

    tamanho = len(primeiro)
    if tamanho < 2:
        return [], "Serial muito curto."

    # Nota: a validação do DV dos seriais informados foi removida intencionalmente.
    # Operadoras podem usar variações do Luhn. O sistema confia no que o leitor bipou
    # e apenas recalcula o DV dos seriais intermediários usando o Luhn padrão.

    # ── Corpo numérico (sem DV) ───────────────────────────────────────────────
    corpo_inicio = int(primeiro[:-1])
    corpo_fim    = int(ultimo[:-1])

    if corpo_inicio > corpo_fim:
        return [], "O primeiro serial deve ser menor ou igual ao último."

    quantidade = corpo_fim - corpo_inicio + 1
    if quantidade > 10_000:
        return [], f"Faixa muito grande ({quantidade} seriais). Máximo permitido: 10.000."

    # ── Geração ──────────────────────────────────────────────────────────────
    largura_corpo = tamanho - 1          # dígitos do corpo (sem DV)
    seriais = []
    for n in range(corpo_inicio, corpo_fim + 1):
        corpo = str(n).zfill(largura_corpo)
        seriais.append(gerar_iccid(corpo))

    return seriais, None

def gerar_faixa_recarga(primeiro: str, ultimo: str):
    """
    Gera a sequência de seriais de recarga (sequência direta, sem Luhn).
    Retorna: (lista_de_seriais, mensagem_de_erro)
    """
    primeiro = primeiro.strip()
    ultimo = ultimo.strip()

    if not primeiro.isdigit() or not ultimo.isdigit():
        return [], "Os seriais de recarga devem conter apenas números."

    if len(primeiro) != len(ultimo):
        return [], "O serial inicial e o final devem ter a mesma quantidade de dígitos."

    try:
        num_ini = int(primeiro)
        num_fim = int(ultimo)

        if num_ini > num_fim:
            return [], "O serial inicial não pode ser maior que o final."

        if (num_fim - num_ini) > 2000:
            return [], "Lote muito grande! O máximo permitido é 2000 por vez."

        seriais = []
        for i in range(num_ini, num_fim + 1):
            serial_str = str(i).zfill(len(primeiro))
            seriais.append(serial_str)

        return seriais, None

    except Exception as e:
        return [], f"Erro ao calcular lote de recargas: {e}"