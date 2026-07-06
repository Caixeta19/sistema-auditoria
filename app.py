import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import sys
import os
import time
import json
from datetime import datetime
sys.path.insert(0, os.path.dirname(__file__))
import db
import relatorio as rel
import gsheets
import lote as lote_mod
import updater

# ==============================================================================
# VERSÃO DO SISTEMA (Altere aqui toda vez que for gerar um .exe novo)
VERSAO_SISTEMA = "1.4"
# ==============================================================================

COR_FUNDO      = "#1e1e1e"
COR_FUNDO_2    = "#141414"
COR_FUNDO_ITEM = "#2d2d2d"
COR_TEXTO      = "#cccccc"
COR_VERDE      = "#4cff4c"
COR_VERMELHO   = "#ff5555"
COR_LARANJA    = "#ffaa00"
COR_ROXO       = "#cc88ff"
COR_CINZA      = "#888888"

ICONE_OK      = "✅"
ICONE_NAO     = "❌"
ICONE_BIPANDO = "⏳"

PREFIXOS_NUMERICOS_INVALIDOS = ("79", "78", "2202", "080","00")


class App(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title(f"Sistema de Auditoria — ClickHouse (v{VERSAO_SISTEMA})")
        self.geometry("1150x660")
        self.centralizar_janela()
        self.resizable(True, True)
        self.configure(bg=COR_FUNDO)

        if getattr(sys, 'frozen', False):
            DIR_ATUAL = os.path.dirname(sys.executable)
        else:
            DIR_ATUAL = os.path.dirname(__file__)

        self.ARQUIVO_CACHE      = os.path.join(DIR_ATUAL, "sessao_cache.json")
        self.ARQUIVO_CONCLUIDAS = os.path.join(DIR_ATUAL, "auditorias_concluidas.json")

        self._seriais_status: dict[str, str]  = {}
        self._nao_encontrados: list[dict]     = []
        self._cache_bipados: dict[str, dict]  = {}
        self._iids: dict[str, str]            = {}
        self._ordem: list[str]                = []
        self._inicio_digitacao                = 0.0
        self._auditorias_concluidas: list[str]= []
        self._lote_em_andamento               = False
        self._atualizando_estoque             = False

        self._carregar_auditorias_concluidas()
        self._construir_ui()
        self.after(100, self._carregar_seriais)
        self.after(200, lambda: self.entry_serial.focus_set())
        updater.verificar_atualizacao(VERSAO_SISTEMA, self)

        # Revalida o estoque contra a view periodicamente (a cada 20 minutos),
        # para sistemas que ficam abertos o turno inteiro.
        self.after(20 * 60 * 1000, self._atualizar_estoque_automatico)

        
    def centralizar_janela(self, largura=1150, altura=660):
        self.update_idletasks()
        largura_tela = self.winfo_screenwidth()
        altura_tela  = self.winfo_screenheight()
        x = (largura_tela // 2) - (largura // 2)
        y = (altura_tela  // 2) - (altura  // 2)
        self.geometry(f"{largura}x{altura}+{x}+{y}")

    # ──────────────────────────────────────────────────────────────────────────
    # AUDITORIAS CONCLUÍDAS
    # ──────────────────────────────────────────────────────────────────────────

    def _carregar_auditorias_concluidas(self):
        if os.path.exists(self.ARQUIVO_CONCLUIDAS):
            try:
                with open(self.ARQUIVO_CONCLUIDAS, "r", encoding="utf-8") as f:
                    self._auditorias_concluidas = json.load(f)
            except:
                self._auditorias_concluidas = []
        else:
            self._auditorias_concluidas = []

    def _salvar_auditorias_concluidas(self):
        try:
            with open(self.ARQUIVO_CONCLUIDAS, "w", encoding="utf-8") as f:
                json.dump(self._auditorias_concluidas, f)
        except Exception as e:
            print(f"Erro salvar concluidas: {e}")

    def _atualizar_lista_auditorias(self):
        valores_base = ["1","2","3","4","5","6","7","8","9","10",
                        "11","12","13","14","15","16","17","18","19","20"]
        disponiveis = [v for v in valores_base if v not in self._auditorias_concluidas]

        if not disponiveis:
            disponiveis = ["Todas Concluídas!"]
            self.entry_serial.configure(state="disabled")

        self.combo_auditoria.configure(values=disponiveis)
        self.combo_auditoria.current(0)

    # ──────────────────────────────────────────────────────────────────────────
    # CONSTRUÇÃO DA INTERFACE
    # ──────────────────────────────────────────────────────────────────────────

    def _construir_ui(self):
        # ── Cabeçalho ─────────────────────────────────────────────────────────
        frame_top = tk.Frame(self, bg=COR_FUNDO)
        frame_top.pack(fill="x", padx=20, pady=(14, 0))

        tk.Label(
            frame_top, text="🔍  Sistema de Auditoria",
            font=("Segoe UI", 17, "bold"), bg=COR_FUNDO, fg="#ffffff"
        ).pack(side="left")

        self.lbl_conexao = tk.Label(
            frame_top, text="⬤  Conectando...",
            font=("Segoe UI", 9), bg=COR_FUNDO, fg=COR_CINZA
        )
        self.lbl_conexao.pack(side="right", padx=4)

        # ── Entry serial ──────────────────────────────────────────────────────
        frame_entry = tk.Frame(self, bg=COR_FUNDO)
        frame_entry.pack(fill="x", padx=20, pady=10)

        frame_auditoria = tk.Frame(frame_entry, bg=COR_FUNDO)
        frame_auditoria.pack(fill="x", pady=(0, 8))

        tk.Label(
            frame_auditoria, text="Selecione o Nº da Auditoria:",
            font=("Segoe UI", 9, "bold"), bg=COR_FUNDO, fg=COR_TEXTO
        ).pack(side="left")

        self.var_num_auditoria = tk.StringVar()
        self.combo_auditoria = ttk.Combobox(
            frame_auditoria, textvariable=self.var_num_auditoria,
            state="readonly", width=15, font=("Segoe UI", 9)
        )
        self.combo_auditoria.pack(side="left", padx=10)
        self._atualizar_lista_auditorias()

        tk.Label(
            frame_entry, text="Bipe o chip/recarga ou digite o serial e pressione Enter:",
            font=("Segoe UI", 9), bg=COR_FUNDO, fg=COR_CINZA
        ).pack(anchor="w")

        self.entry_serial = tk.Entry(
            frame_entry, font=("Consolas", 15, "bold"), justify="center",
            bg="#2d2d2d", fg="#ffffff", insertbackground="#ffffff",
            relief="flat", bd=0, state="disabled"
        )
        self.entry_serial.pack(fill="x", ipady=9, pady=(4, 0))
        self.entry_serial.bind("<Return>", self._on_bipar)

        self.entry_serial.bind("<Control-v>", lambda e: "break")
        self.entry_serial.bind("<Control-c>", lambda e: "break")
        self.entry_serial.bind("<<Paste>>",   lambda e: "break")
        self.entry_serial.bind("<<Copy>>",    lambda e: "break")
        self.entry_serial.bind("<Button-3>",  lambda e: "break")
        self.entry_serial.bind("<Key>",       self._registrar_inicio_teclado)

        tk.Frame(frame_entry, bg="#444444", height=2).pack(fill="x")

        # ── Painel de resultado ───────────────────────────────────────────────
        self.frame_resultado = tk.Frame(self, bg="#2b2b2b", height=70)
        self.frame_resultado.pack(fill="x", padx=20, pady=(4, 8))
        self.frame_resultado.pack_propagate(False)

        self.lbl_icone_res = tk.Label(
            self.frame_resultado, text="📡",
            font=("Segoe UI", 26), bg="#2b2b2b", fg=COR_CINZA
        )
        self.lbl_icone_res.pack(side="left", padx=14)

        frame_txt = tk.Frame(self.frame_resultado, bg="#2b2b2b")
        frame_txt.pack(side="left", fill="both", expand=True, pady=8)

        self.lbl_serial_res = tk.Label(
            frame_txt, text="Aguardando bipagem...",
            font=("Consolas", 12, "bold"), bg="#2b2b2b", fg=COR_CINZA, anchor="w"
        )
        self.lbl_serial_res.pack(fill="x")

        self.lbl_msg_res = tk.Label(
            frame_txt, text="",
            font=("Segoe UI", 9), bg="#2b2b2b", fg=COR_CINZA,
            anchor="w", wraplength=600, justify="left"
        )
        self.lbl_msg_res.pack(fill="x", pady=(2, 0))

        # ── Barra de filtros ──────────────────────────────────────────────────
        frame_busca = tk.Frame(self, bg=COR_FUNDO)
        frame_busca.pack(fill="x", padx=20, pady=(0, 4))

        tk.Label(
            frame_busca, text="Filtrar serial:",
            font=("Segoe UI", 9), bg=COR_FUNDO, fg=COR_CINZA
        ).pack(side="left")

        self.var_busca = tk.StringVar()
        self.var_busca.trace_add("write", self._filtrar)
        entry_busca = tk.Entry(
            frame_busca, textvariable=self.var_busca, font=("Consolas", 10),
            bg="#2d2d2d", fg="#ffffff", insertbackground="#ffffff",
            relief="flat", bd=0, width=20
        )
        entry_busca.pack(side="left", ipady=4, padx=(6, 15))

        tk.Label(
            frame_busca, text="Loja:",
            font=("Segoe UI", 9), bg=COR_FUNDO, fg=COR_CINZA
        ).pack(side="left", padx=(0, 6))

        self.var_loja = tk.StringVar()
        self.combo_loja = ttk.Combobox(
            frame_busca, textvariable=self.var_loja, state="readonly", width=25
        )
        self.combo_loja.pack(side="left")
        self.combo_loja.bind("<<ComboboxSelected>>", self._filtrar)

        self.lbl_contador = tk.Label(
            frame_busca, text="", font=("Segoe UI", 9), bg=COR_FUNDO, fg=COR_CINZA
        )
        self.lbl_contador.pack(side="right")

        # ── Lista (Treeview) ──────────────────────────────────────────────────
        frame_lista = tk.Frame(self, bg=COR_FUNDO)
        frame_lista.pack(fill="both", expand=True, padx=20)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Chips.Treeview",
                        background=COR_FUNDO_ITEM, foreground=COR_TEXTO,
                        rowheight=22, fieldbackground=COR_FUNDO_ITEM,
                        borderwidth=0, font=("Consolas", 10))
        style.configure("Chips.Treeview.Heading",
                        background="#3a3a3a", foreground="#ffffff",
                        font=("Segoe UI", 9, "bold"))
        style.map("Chips.Treeview", background=[("selected", "#3a3a3a")])

        cols = ("status", "serial", "nome", "loja", "horario", "origem", "auditoria")
        self.tree = ttk.Treeview(frame_lista, columns=cols, show="headings",
                                 style="Chips.Treeview")

        self.tree.heading("status",    text="Status")
        self.tree.heading("serial",    text="Serial")
        self.tree.heading("nome",      text="Nome")
        self.tree.heading("loja",      text="Loja")
        self.tree.heading("horario",   text="Data e Hora")
        self.tree.heading("origem",    text="Origem")
        self.tree.heading("auditoria", text="Nº Auditoria")

        self.tree.column("status",    width=60,  anchor="center", stretch=False)
        self.tree.column("serial",    width=170, anchor="w")
        self.tree.column("nome",      width=230, anchor="w")
        self.tree.column("loja",      width=130, anchor="w")
        self.tree.column("horario",   width=150, anchor="center")
        self.tree.column("origem",    width=100, anchor="center")
        self.tree.column("auditoria", width=100, anchor="center")

        self.tree.tag_configure("ok",             foreground=COR_VERDE)
        self.tree.tag_configure("pendente",       foreground=COR_VERMELHO)
        self.tree.tag_configure("nao_encontrado", foreground=COR_LARANJA)
        self.tree.tag_configure("loading",        foreground=COR_CINZA)

        scroll = ttk.Scrollbar(frame_lista, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # ── Rodapé ────────────────────────────────────────────────────────────
        frame_rodape = tk.Frame(self, bg=COR_FUNDO_2)
        frame_rodape.pack(fill="x", pady=(6, 0))

        self.lbl_stats = tk.Label(
            frame_rodape, text="Carregando lista...",
            font=("Segoe UI", 8), bg=COR_FUNDO_2, fg=COR_CINZA
        )
        self.lbl_stats.pack(side="left", padx=12, pady=6)

        btn_finalizar = tk.Button(
            frame_rodape, text="🛑  Finalizar Auditoria",
            font=("Segoe UI", 9, "bold"),
            bg="#005ce6", fg="#ffffff",
            activebackground="#3385ff", activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", padx=12,
            command=self._finalizar_auditoria
        )
        btn_finalizar.pack(side="right", padx=(0, 12), pady=5)

        btn_rel = tk.Button(
            frame_rodape, text="📥  Gerar Relatório Excel",
            font=("Segoe UI", 9, "bold"),
            bg="#8b0000", fg="#ffffff",
            activebackground="#aa0000", activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", padx=12,
            command=self._gerar_relatorio
        )
        btn_rel.pack(side="right", padx=12, pady=5)

        btn_lote = tk.Button(
            frame_rodape, text="📦  Bipar em Lote",
            font=("Segoe UI", 9, "bold"),
            bg="#1a6b3a", fg="#ffffff",
            activebackground="#28a05a", activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", padx=12,
            command=self._abrir_lote
        )
        btn_lote.pack(side="right", padx=12, pady=5)

        btn_atualizar = tk.Button(
            frame_rodape, text="🔄  Atualizar Estoque",
            font=("Segoe UI", 9, "bold"),
            bg="#555555", fg="#ffffff",
            activebackground="#787878", activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", padx=12,
            command=self._atualizar_estoque
        )
        btn_atualizar.pack(side="right", padx=12, pady=5)

    # ──────────────────────────────────────────────────────────────────────────
    # CARREGAMENTO DE SERIAIS
    # ──────────────────────────────────────────────────────────────────────────

    def _registrar_inicio_teclado(self, event):
        if not self.entry_serial.get():
            self._inicio_digitacao = time.time()

    def _carregar_seriais(self):
        self.tree.insert("", "end",
                         values=("⏳", "Carregando seriais...", "", "", "", "", ""),
                         tags=("loading",))
        self.lbl_conexao.configure(text="⬤  Conectando...", fg=COR_CINZA)
        threading.Thread(target=self._thread_carregar, daemon=True).start()

    def _thread_carregar(self):
        try:
            dados = db.carregar_todos_seriais()
            self.after(0, self._popular_lista, dados)
        except Exception as e:
            self.after(0, self._erro_carregar, str(e))

    def _popular_lista(self, dados: list):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._iids            = {}
        self._ordem           = []
        self._seriais_status  = {}
        todas_as_lojas        = set()

        for serial, loja, nome in dados:
            key = serial.upper()
            self._seriais_status[key] = "pendente"
            todas_as_lojas.add(loja.strip())

            serial_ecra = serial[:4] + "****" if len(serial) > 4 else serial
            iid = self.tree.insert("", "end",
                                   values=(ICONE_NAO, serial_ecra, nome, loja.strip(), "", "", ""),
                                   tags=("pendente",))
            self._iids[key] = iid
            self._ordem.append(key)

        lista_lojas = ["Todas as Lojas"] + sorted(list(todas_as_lojas))
        self.combo_loja.configure(values=lista_lojas)
        self.combo_loja.current(0)

        self.lbl_conexao.configure(text="⬤  ClickHouse: conectado", fg=COR_VERDE)

        if "Todas Concluídas!" not in self.combo_auditoria.cget("values"):
            self.entry_serial.configure(state="normal")
            self.entry_serial.focus_set()

        self._recuperar_sessao_local()
        self._atualizar_contador()
        self._filtrar()

    def _erro_carregar(self, erro: str):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.tree.insert("", "end",
                         values=("💥", f"Erro: {erro[:120]}", "", "", "", "", ""),
                         tags=("pendente",))
        self.lbl_conexao.configure(text=f"⬤  Erro: {erro[:60]}", fg=COR_VERMELHO)

    # ──────────────────────────────────────────────────────────────────────────
    # ATUALIZAÇÃO DE ESTOQUE (revalida a lista contra a view sem perder progresso)
    # ──────────────────────────────────────────────────────────────────────────

    def _atualizar_estoque_automatico(self):
        """Chamado periodicamente (a cada 20 min) para revalidar a lista contra
        a view, sem interromper o usuário com pop-ups desnecessários."""
        self._atualizar_estoque(silencioso=True)
        self.after(20 * 60 * 1000, self._atualizar_estoque_automatico)

    def _atualizar_estoque(self, silencioso: bool = False):
        if self._lote_em_andamento:
            if not silencioso:
                messagebox.showwarning("Lote em andamento",
                                       "Aguarde o lote atual terminar antes de atualizar o estoque.")
            return

        if self._atualizando_estoque:
            return

        self._atualizando_estoque = True
        self.lbl_conexao.configure(text="⬤  Atualizando estoque...", fg=COR_CINZA)
        threading.Thread(target=self._thread_atualizar_estoque,
                         args=(silencioso,), daemon=True).start()

    def _thread_atualizar_estoque(self, silencioso: bool):
        try:
            dados = db.carregar_todos_seriais()
            self.after(0, self._reconciliar_estoque, dados, silencioso)
        except Exception as e:
            self.after(0, self._erro_atualizar_estoque, str(e))

    def _erro_atualizar_estoque(self, erro: str):
        self._atualizando_estoque = False
        self.lbl_conexao.configure(text=f"⬤  Erro ao atualizar: {erro[:60]}", fg=COR_VERMELHO)
        messagebox.showerror("Erro ao atualizar estoque",
                             f"Não foi possível atualizar o estoque.\n\nDetalhe técnico:\n{erro}")

    def _reconciliar_estoque(self, dados: list, silencioso: bool):
        """Compara a lista atual com o que veio fresco do ClickHouse:
        - Remove da tela os PENDENTES que saíram da view (não precisam mais ser bipados)
        - Adiciona os seriais novos que entraram na view
        - Atualiza loja/nome de quem já existia
        - NUNCA remove quem já foi bipado nesta sessão (preserva o progresso)
        """
        novos_seriais = {}
        todas_as_lojas = set()
        for serial, loja, nome in dados:
            key = serial.upper()
            novos_seriais[key] = (serial, loja.strip(), nome)
            todas_as_lojas.add(loja.strip())

        removidos    = 0
        adicionados  = 0

        for key in list(self._seriais_status.keys()):
            if key not in novos_seriais and self._seriais_status.get(key) == "pendente":
                iid = self._iids.pop(key, None)
                if iid is not None:
                    try:
                        self.tree.delete(iid)
                    except tk.TclError:
                        pass
                if key in self._ordem:
                    self._ordem.remove(key)
                del self._seriais_status[key]
                removidos += 1

        for key, (serial, loja, nome) in novos_seriais.items():
            if key not in self._seriais_status:
                self._seriais_status[key] = "pendente"
                serial_ecra = serial[:4] + "****" if len(serial) > 4 else serial
                iid = self.tree.insert("", "end",
                                       values=(ICONE_NAO, serial_ecra, nome, loja, "", "", ""),
                                       tags=("pendente",))
                self._iids[key] = iid
                self._ordem.append(key)
                adicionados += 1
            else:
                iid = self._iids.get(key)
                if iid is not None:
                    valores = list(self.tree.item(iid, "values"))
                    if len(valores) >= 4:
                        valores[2], valores[3] = nome, loja
                        self.tree.item(iid, values=tuple(valores))

        loja_atual = self.var_loja.get()
        lista_lojas = ["Todas as Lojas"] + sorted(list(todas_as_lojas))
        self.combo_loja.configure(values=lista_lojas)
        if loja_atual in lista_lojas:
            self.var_loja.set(loja_atual)
        else:
            self.combo_loja.current(0)

        self.lbl_conexao.configure(text="⬤  ClickHouse: conectado", fg=COR_VERDE)
        self._atualizando_estoque = False

        self._atualizar_contador()
        self._salvar_sessao_local()
        self._filtrar()

        if not silencioso:
            if removidos or adicionados:
                messagebox.showinfo(
                    "Estoque atualizado",
                    f"Estoque atualizado com sucesso!\n\n"
                    f"➕  {adicionados} serial(is) novo(s) na base\n"
                    f"➖  {removidos} serial(is) que saíram da base (removido(s) da lista de pendentes)"
                )
            else:
                messagebox.showinfo("Estoque atualizado", "Estoque já estava atualizado — nenhuma mudança encontrada.")

    # ──────────────────────────────────────────────────────────────────────────
    # VALIDAÇÃO DE PREFIXO INVÁLIDO
    # ──────────────────────────────────────────────────────────────────────────

    def _prefixo_invalido(self, serial: str) -> bool:
        if not serial:
            return False

        if serial[0].isalpha():
            return True

        s = serial.upper()
        for p in PREFIXOS_NUMERICOS_INVALIDOS:
            if s.startswith(p):
                if p == "2202":
                    if len(serial) == 8:
                        return True
                else:
                    return True

        return False

    def _resultado_codigo_errado(self, serial: str):
        serial_ecra = serial[:4] + "****" if len(serial) > 4 else serial

        self.frame_resultado.configure(bg="#7a0000")
        self.lbl_icone_res.configure(bg="#7a0000", text="⛔")
        self.lbl_serial_res.configure(bg="#7a0000", fg="#ffffff", text=serial_ecra)
        self.lbl_msg_res.configure(bg="#7a0000", fg="#ffaaaa", text="⛔  CÓDIGO INCORRETO")

        messagebox.showerror(
            "Codigo Incorreto",
            "O codigo bipado e INVALIDO!\n\n"
            "Serial: " + serial_ecra + "\n\n"
            "Localize o serial correto no produto e bipe novamente.\n"
        )

        if not self._lote_em_andamento:
            self.entry_serial.configure(state="normal")
            self.after(0, self._resetar_painel)

    # ──────────────────────────────────────────────────────────────────────────
    # BIPAGEM MANUAL
    # ──────────────────────────────────────────────────────────────────────────

    def _on_bipar(self, event=None):
        if self._lote_em_andamento:
            return

        tempo_total = time.time() - self._inicio_digitacao
        origem = "Bipado" if tempo_total < 0.1 else "Digitado"

        serial        = self.entry_serial.get().strip()
        num_auditoria = self.var_num_auditoria.get()

        self.entry_serial.delete(0, tk.END)
        self._inicio_digitacao = 0.0

        if not serial:
            return

        self.entry_serial.configure(state="disabled")
        self._exibir_processando(serial)
        threading.Thread(target=self._thread_bipar,
                         args=(serial, origem, num_auditoria), daemon=True).start()

    def _thread_bipar(self, serial: str, origem: str, num_auditoria: str):
        if self._prefixo_invalido(serial):
            self.after(0, self._resultado_codigo_errado, serial)
            return

        key = serial.upper()
        if key in self._seriais_status:
            if self._seriais_status[key] == "ok":
                self.after(0, self._resultado_bipagem, serial, "ja_bipado",
                           "Serial já havia sido bipado nesta sessão.", origem, num_auditoria)
            else:
                self.after(0, self._resultado_bipagem, serial, "ok",
                           "Serial encontrado e marcado como bipado! ✅", origem, num_auditoria)
        else:
            try:
                existe = db.serial_existe(serial)
                if existe:
                    self.after(0, self._resultado_bipagem, serial, "ok",
                               "Encontrado no banco.", origem, num_auditoria)
                else:
                    self.after(0, self._resultado_bipagem, serial, "nao_encontrado",
                               "NÃO encontrado na base de dados.", origem, num_auditoria)
            except Exception as e:
                self.after(0, self._resultado_bipagem, serial, "erro",
                           f"Erro ClickHouse: {e}", origem, num_auditoria)

    def _exibir_processando(self, serial: str):
        self.frame_resultado.configure(bg="#2b2b2b")
        self.lbl_icone_res.configure(bg="#2b2b2b", text=ICONE_BIPANDO)
        serial_oculto = serial[:4] + "****" if len(serial) > 4 else serial
        self.lbl_serial_res.configure(bg="#2b2b2b", fg="#ffffff", text=serial_oculto)
        self.lbl_msg_res.configure(bg="#2b2b2b", fg=COR_CINZA, text="Consultando...")

    def _resultado_bipagem(self, serial: str, resultado: str, mensagem: str,
                           origem: str, num_auditoria: str):
        agora    = datetime.now()
        str_hora = agora.strftime("%d/%m/%Y %H:%M:%S")
        key      = serial.upper()

        nome_orig, loja_orig = "N/A", "N/A"

        if key in self._iids:
            valores = self.tree.item(self._iids[key], "values")
            if len(valores) >= 4:
                nome_orig, loja_orig = valores[2], valores[3]
        else:
            loja_combo = self.var_loja.get().strip()
            if loja_combo and loja_combo != "Todas as Lojas":
                loja_orig = loja_combo
            else:
                loja_orig = "Loja não identificada"
            if resultado == "nao_encontrado":
                mensagem = f"NÃO encontrado na base de dados. Loja: {loja_orig}"

        cores = {
            "ok":             ("#1a7a1a", COR_VERDE,    ICONE_OK),
            "ja_bipado":      ("#b85c00", COR_LARANJA,  "⚠️"),
            "nao_encontrado": ("#8b0000", COR_VERMELHO, "🔍"),
            "erro":           ("#4a0080", COR_ROXO,     "💥"),
        }
        bg, fg, icone = cores.get(resultado, cores["erro"])
        serial_ecra = serial[:4] + "****" if len(serial) > 4 else serial

        self.frame_resultado.configure(bg=bg)
        self.lbl_icone_res.configure(bg=bg, text=icone)
        self.lbl_serial_res.configure(bg=bg, fg="#ffffff",
                                      text=f"{serial_ecra}  |  Loja: {loja_orig}")
        self.lbl_msg_res.configure(bg=bg, fg="#ffffff", text=mensagem)

        if resultado not in ("ja_bipado", "erro"):
            threading.Thread(
                target=gsheets.registrar_bipagem,
                args=(serial, resultado, str_hora, loja_orig, nome_orig, origem, num_auditoria),
                daemon=True
            ).start()

        if resultado == "ok":
            self._seriais_status[key] = "ok"
            self._cache_bipados[key]  = {
                "horario":   str_hora,
                "origem":    origem,
                "auditoria": num_auditoria,
            }
            self.combo_auditoria.configure(state="disabled")

            if key in self._iids:
                iid = self._iids[key]
                self.tree.item(iid,
                               values=(ICONE_OK, serial_ecra, nome_orig, loja_orig,
                                       str_hora, origem, num_auditoria),
                               tags=("ok",))
            else:
                iid = self.tree.insert("", "end",
                                       values=(ICONE_OK, serial_ecra, "N/A", loja_orig,
                                               str_hora, origem, num_auditoria),
                                       tags=("ok",))
                self._iids[key] = iid
                self._ordem.append(key)

        elif resultado == "nao_encontrado":
            self._nao_encontrados.append({
                "serial":    serial,
                "bipado_em": agora,
                "loja":      loja_orig,
            })

        self._atualizar_contador()
        self._salvar_sessao_local()
        self._filtrar()

        if key in self._iids:
            self.tree.see(self._iids[key])

        if not self._lote_em_andamento:
            self.entry_serial.configure(state="normal")
            self.after(3000, self._resetar_painel)

    # ──────────────────────────────────────────────────────────────────────────
    # BIPAGEM EM LOTE
    # ──────────────────────────────────────────────────────────────────────────

    def _abrir_lote(self):
        if self._lote_em_andamento:
            messagebox.showwarning("Lote em andamento",
                                   "Aguarde o lote atual terminar antes de iniciar outro.")
            return

        win = tk.Toplevel(self)
        win.title("📦 Bipagem em Lote")
        win.geometry("500x420")
        win.configure(bg=COR_FUNDO)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="📦  Bipagem em Lote",
                 font=("Segoe UI", 14, "bold"), bg=COR_FUNDO, fg="#ffffff").pack(pady=(16, 4))

        tk.Label(win,
                 text="Selecione o tipo, bipe o PRIMEIRO e o ÚLTIMO serial do lote.\n"
                      "O sistema calculará todos os intermediários automaticamente.",
                 font=("Segoe UI", 9), bg=COR_FUNDO, fg=COR_CINZA, justify="center").pack()

        tk.Frame(win, bg="#444444", height=1).pack(fill="x", padx=20, pady=10)

        frame_tipo = tk.Frame(win, bg=COR_FUNDO)
        frame_tipo.pack(fill="x", padx=30, pady=5)

        tk.Label(frame_tipo, text="Tipo de Produto:", font=("Segoe UI", 9, "bold"),
                 bg=COR_FUNDO, fg=COR_TEXTO, width=16, anchor="w").pack(side="left")

        var_tipo_lote = tk.StringVar(value="chip")

        tk.Radiobutton(frame_tipo, text="Chips (Luhn)", variable=var_tipo_lote, value="chip",
                       bg=COR_FUNDO, fg=COR_TEXTO, selectcolor=COR_FUNDO_ITEM,
                       activebackground=COR_FUNDO, activeforeground="#ffffff",
                       font=("Segoe UI", 9)).pack(side="left", padx=10)

        tk.Radiobutton(frame_tipo, text="Recargas", variable=var_tipo_lote, value="recarga",
                       bg=COR_FUNDO, fg=COR_TEXTO, selectcolor=COR_FUNDO_ITEM,
                       activebackground=COR_FUNDO, activeforeground="#ffffff",
                       font=("Segoe UI", 9)).pack(side="left")

        def _campo(label_txt):
            fr = tk.Frame(win, bg=COR_FUNDO)
            fr.pack(fill="x", padx=30, pady=5)
            tk.Label(fr, text=label_txt, font=("Segoe UI", 9),
                     bg=COR_FUNDO, fg=COR_TEXTO, width=16, anchor="w").pack(side="left")
            var   = tk.StringVar()
            entry = tk.Entry(fr, textvariable=var, font=("Consolas", 11, "bold"),
                             bg="#2d2d2d", fg="#ffffff", insertbackground="#ffffff",
                             relief="flat", bd=0, justify="center")
            entry.pack(side="left", fill="x", expand=True, ipady=7)
            for seq in ("<Control-v>", "<Control-c>", "<<Paste>>", "<<Copy>>", "<Button-3>"):
                entry.bind(seq, lambda e: "break")
            return var, entry

        var_primeiro, entry_primeiro = _campo("Primeiro serial:")
        var_ultimo,   entry_ultimo   = _campo("Último serial:")

        lbl_preview = tk.Label(win, text="", font=("Segoe UI", 9),
                               bg=COR_FUNDO, fg=COR_CINZA, justify="center")
        lbl_preview.pack(pady=(8, 0))

        def _atualizar_preview(*_):
            p, u, tipo = var_primeiro.get().strip(), var_ultimo.get().strip(), var_tipo_lote.get()
            if not p or not u:
                lbl_preview.configure(text="", fg=COR_CINZA)
                return
            if self._prefixo_invalido(p) or self._prefixo_invalido(u):
                lbl_preview.configure(text="⛔  Serial com prefixo inválido!", fg=COR_VERMELHO)
                return
            seriais, erro = lote_mod.gerar_faixa(p, u) if tipo == "chip" else lote_mod.gerar_faixa_recarga(p, u)
            if erro:
                lbl_preview.configure(text=f"⚠  {erro}", fg=COR_VERMELHO)
            else:
                lbl_preview.configure(text=f"✅  {len(seriais)} serial(is) gerado(s).", fg=COR_VERDE)

        var_primeiro.trace_add("write",  _atualizar_preview)
        var_ultimo.trace_add("write",    _atualizar_preview)
        var_tipo_lote.trace_add("write", _atualizar_preview)

        tk.Frame(win, bg="#444444", height=1).pack(fill="x", padx=20, pady=10)

        def _confirmar():
            p, u, tipo = var_primeiro.get().strip(), var_ultimo.get().strip(), var_tipo_lote.get()
            if self._prefixo_invalido(p) or self._prefixo_invalido(u):
                messagebox.showerror("Código inválido",
                                     "Um ou mais seriais possuem prefixo inválido.", parent=win)
                return
            seriais, erro = lote_mod.gerar_faixa(p, u) if tipo == "chip" else lote_mod.gerar_faixa_recarga(p, u)
            if erro:
                messagebox.showerror("Erro na faixa", erro, parent=win)
                return
            if not messagebox.askyesno("Confirmar lote",
                                       f"Serão processados {len(seriais)} seriais.\nDeseja continuar?",
                                       parent=win):
                return
            win.destroy()
            self._processar_lote(seriais)

        tk.Button(win, text="▶  Bipar Lote", font=("Segoe UI", 10, "bold"),
                  bg="#1a6b3a", fg="#ffffff", activebackground="#28a05a",
                  activeforeground="#ffffff", relief="flat", bd=0,
                  cursor="hand2", padx=16, command=_confirmar).pack(pady=4)

        entry_primeiro.focus_set()
        entry_primeiro.bind("<Tab>",    lambda e: (entry_ultimo.focus_set(), "break"))
        entry_primeiro.bind("<Return>", lambda e: entry_ultimo.focus_set())
        entry_ultimo.bind("<Return>",   lambda e: _confirmar())

    def _processar_lote(self, seriais: list[str]):
        num_auditoria = self.var_num_auditoria.get()
        total         = len(seriais)
        origem        = "Lote"

        self._lote_em_andamento = True
        self.entry_serial.configure(state="disabled")
        self.frame_resultado.configure(bg="#1a3a5c")
        self.lbl_icone_res.configure(bg="#1a3a5c", text="📦")
        self.lbl_serial_res.configure(bg="#1a3a5c", fg="#ffffff",
                                      text=f"Processando lote — 0 / {total}")
        self.lbl_msg_res.configure(bg="#1a3a5c", fg=COR_CINZA,
                                   text="Aguarde, bipando seriais automaticamente...")

        def _atualizar_progresso(i, serial, resultado_str):
            serial_ecra = serial[:4] + "****" if len(serial) > 4 else serial
            icones = {"ok":"✅","ja_bipado":"⚠️","nao_encontrado":"🔍","erro":"💥","invalido":"⛔"}
            self.lbl_serial_res.configure(text=f"Processando lote — {i} / {total}  {icones.get(resultado_str,'')}")
            self.lbl_msg_res.configure(text=f"Último: {serial_ecra}  ({'encontrado' if resultado_str=='ok' else resultado_str})")

        def _registrar_com_retry(serial, resultado_str, str_hora, loja_orig, nome_orig, origem, num_auditoria, tentativas=3):
            for tentativa in range(1, tentativas + 1):
                try:
                    gsheets.registrar_bipagem(serial, resultado_str, str_hora, loja_orig, nome_orig, origem, num_auditoria)
                    return True
                except Exception as e:
                    print(f"[Sheets] Tentativa {tentativa}/{tentativas} falhou: {e}")
                    if tentativa < tentativas:
                        time.sleep(1.0 * tentativa)
            return False

        def _worker():
            ok_count = nao_count = ja_count = err_count = invalido_count = 0
            sheets_falhos = []

            for i, serial in enumerate(seriais, 1):
                key = serial.upper()

                if self._prefixo_invalido(serial):
                    invalido_count += 1
                    self.after(0, _atualizar_progresso, i, serial, "invalido")
                    time.sleep(0.05)
                    continue

                if self._seriais_status.get(key) == "ok":
                    ja_count += 1
                    self.after(0, _atualizar_progresso, i, serial, "ja_bipado")
                    time.sleep(0.05)
                    continue

                try:
                    resultado_str = "ok" if self._seriais_status.get(key) == "pendente" else ("ok" if db.serial_existe(serial) else "nao_encontrado")
                except Exception as e:
                    err_count += 1
                    print(f"[Lote] Erro: {e}")
                    self.after(0, _atualizar_progresso, i, serial, "erro")
                    time.sleep(0.05)
                    continue

                str_hora_serial = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

                if resultado_str == "ok":
                    ok_count += 1
                    self._seriais_status[key] = "ok"
                    self._cache_bipados[key]  = {"horario": str_hora_serial, "origem": origem, "auditoria": num_auditoria}

                    nome_orig, loja_orig = "N/A", "N/A"
                    if key in self._iids:
                        valores = self.tree.item(self._iids[key], "values")
                        if len(valores) >= 4:
                            nome_orig, loja_orig = valores[2], valores[3]

                    if not _registrar_com_retry(serial, resultado_str, str_hora_serial, loja_orig, nome_orig, origem, num_auditoria):
                        sheets_falhos.append(serial)

                    self.after(0, self._atualizar_item_tree, key, serial, str_hora_serial, origem, num_auditoria)
                    time.sleep(1.1)
                else:
                    nao_count += 1
                    loja_combo = self.var_loja.get().strip()
                    loja_orig  = loja_combo if loja_combo and loja_combo != "Todas as Lojas" else "Loja não identificada"
                    self._nao_encontrados.append({"serial": serial, "bipado_em": datetime.now(), "loja": loja_orig})
                    time.sleep(0.05)

                self.after(0, _atualizar_progresso, i, serial, resultado_str)

            self._lote_em_andamento = False
            self.after(0, self._salvar_sessao_local)
            self.after(0, self._atualizar_contador)
            self.after(0, self._filtrar)

            aviso_sheets = ""
            if sheets_falhos:
                aviso_sheets = f"\n\n⚠️  {len(sheets_falhos)} serial(is) NÃO gravados:\n" + "\n".join(sheets_falhos[:10]) + ("\n..." if len(sheets_falhos) > 10 else "")

            resumo = (f"Lote concluído!\n\n✅  Bipados: {ok_count}\n⚠️  Já bipados: {ja_count}\n"
                      f"🔍  Não encontrados: {nao_count}\n⛔  Inválidos: {invalido_count}\n"
                      + (f"💥  Erros: {err_count}\n" if err_count else "")
                      + f"\nTotal: {total}" + aviso_sheets)
            self.after(0, lambda: messagebox.showinfo("Lote concluído", resumo))
            self.after(0, self._resetar_painel)
            self.after(0, lambda: self.entry_serial.configure(state="normal"))
            self.after(0, lambda: self.entry_serial.focus_set())

        threading.Thread(target=_worker, daemon=True).start()

    def _atualizar_item_tree(self, key, serial, str_hora, origem, num_auditoria):
        serial_ecra = serial[:4] + "****" if len(serial) > 4 else serial
        if key in self._iids:
            iid     = self._iids[key]
            valores = self.tree.item(iid, "values")
            self.tree.item(iid, values=(ICONE_OK, valores[1], valores[2], valores[3],
                                        str_hora, origem, num_auditoria), tags=("ok",))
            self.tree.see(iid)
        else:
            iid = self.tree.insert("", "end",
                                   values=(ICONE_OK, serial_ecra, "N/A", "N/A",
                                           str_hora, origem, num_auditoria), tags=("ok",))
            self._iids[key] = iid
            self._ordem.append(key)

    # ──────────────────────────────────────────────────────────────────────────
    # SESSÃO LOCAL
    # ──────────────────────────────────────────────────────────────────────────

    def _salvar_sessao_local(self):
        dados = {
            "bipados": self._cache_bipados,
            "nao_encontrados": [{"serial": d["serial"], "bipado_em": d["bipado_em"].strftime("%Y-%m-%d %H:%M:%S"), "loja": d.get("loja", "Desconhecida")} for d in self._nao_encontrados]
        }
        try:
            with open(self.ARQUIVO_CACHE, "w", encoding="utf-8") as f:
                json.dump(dados, f)
        except Exception as e:
            print(f"Erro salvar cache: {e}")

    def _recuperar_sessao_local(self):
        if not os.path.exists(self.ARQUIVO_CACHE):
            return
        try:
            with open(self.ARQUIVO_CACHE, "r", encoding="utf-8") as f:
                dados = json.load(f)
            self._cache_bipados = dados.get("bipados", {})
            cache_nao           = dados.get("nao_encontrados", [])

            if self._cache_bipados:
                primeira_chave  = list(self._cache_bipados.keys())[0]
                auditoria_salva = self._cache_bipados[primeira_chave].get("auditoria", "1")
                self.var_num_auditoria.set(auditoria_salva)
                self.combo_auditoria.configure(state="disabled")

            for key, info in self._cache_bipados.items():
                self._seriais_status[key] = "ok"
                auditoria_salva = info.get("auditoria", "")
                if key in self._iids:
                    iid     = self._iids[key]
                    valores = self.tree.item(iid, "values")
                    self.tree.item(iid, values=(ICONE_OK, valores[1], valores[2], valores[3],
                                                info["horario"], info["origem"], auditoria_salva), tags=("ok",))
                else:
                    serial_ecra = key[:4] + "****" if len(key) > 4 else key
                    iid = self.tree.insert("", "end",
                                           values=(ICONE_OK, serial_ecra, "N/A", "N/A",
                                                   info["horario"], info["origem"], auditoria_salva), tags=("ok",))
                    self._iids[key] = iid

            for d in cache_nao:
                self._nao_encontrados.append({"serial": d["serial"], "bipado_em": datetime.strptime(d["bipado_em"], "%Y-%m-%d %H:%M:%S"), "loja": d.get("loja", "Desconhecida")})
        except Exception as e:
            print(f"Erro recuperar cache: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # FINALIZAR / RESETAR
    # ──────────────────────────────────────────────────────────────────────────

    def _finalizar_auditoria(self):
        if self._lote_em_andamento:
            messagebox.showwarning("Lote em andamento", "Aguarde o lote terminar.")
            return

        if not messagebox.askyesno("Finalizar Auditoria", "Deseja FINALIZAR?\nIsso irá apagar o progresso da tela."):
            return

        pendentes_count = sum(1 for s in self._seriais_status.values() if s == "pendente")
        if pendentes_count > 0:
            if messagebox.askyesno("Relatório Pendente", f"Ainda restam {pendentes_count} seriais pendentes.\nDeseja gerar o relatório Excel antes de finalizar?"):
                self._gerar_relatorio()

        numero_atual = self.var_num_auditoria.get()
        if numero_atual and numero_atual != "Todas Concluídas!" and numero_atual not in self._auditorias_concluidas:
            self._auditorias_concluidas.append(numero_atual)
            self._salvar_auditorias_concluidas()

        if os.path.exists(self.ARQUIVO_CACHE):
            try:
                os.remove(self.ARQUIVO_CACHE)
            except:
                pass

        messagebox.showinfo("Sucesso", "Auditoria finalizada e sistema resetado!")
        self._seriais_status.clear()
        self._nao_encontrados.clear()
        self._iids.clear()
        self._ordem.clear()
        self._cache_bipados.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.combo_auditoria.configure(state="readonly")
        self._atualizar_lista_auditorias()
        self._carregar_seriais()

    def _resetar_painel(self):
        self.frame_resultado.configure(bg="#2b2b2b")
        self.lbl_icone_res.configure(bg="#2b2b2b", text="📡")
        self.lbl_serial_res.configure(bg="#2b2b2b", fg=COR_CINZA, text="Aguardando bipagem...")
        self.lbl_msg_res.configure(bg="#2b2b2b", fg=COR_CINZA, text="")
        self.entry_serial.focus_set()

    # ──────────────────────────────────────────────────────────────────────────
    # FILTRO / CONTADOR
    # ──────────────────────────────────────────────────────────────────────────

    def _filtrar(self, *_):
        termo            = self.var_busca.get().strip().upper()
        loja_selecionada = self.var_loja.get().strip().upper() or "TODAS AS LOJAS"

        for item in self.tree.get_children():
            self.tree.detach(item)

        visiveis_pendentes, visiveis_ok = [], []

        for serial_real in self._ordem:
            iid = self._iids.get(serial_real)
            if not iid:
                continue
            valores = self.tree.item(iid, "values")
            if not valores:
                continue
            loja_item = str(valores[3]).strip().upper()
            if (not termo or termo in serial_real) and (loja_selecionada == "TODAS AS LOJAS" or loja_selecionada == loja_item):
                (visiveis_ok if self._seriais_status.get(serial_real) == "ok" else visiveis_pendentes).append(iid)

        for iid in visiveis_pendentes + visiveis_ok:
            self.tree.reattach(iid, "", "end")

    def _atualizar_contador(self):
        total   = len(self._seriais_status)
        bipados = sum(1 for v in self._seriais_status.values() if v == "ok")
        self.lbl_stats.configure(text=f"Total: {total}  |  ✅ Bipados: {bipados}  |  ❌ Pendentes: {total - bipados}  |  🔍 Não encontrados: {len(self._nao_encontrados)}")
        self.lbl_contador.configure(text=f"{bipados}/{total} bipados")

    # ──────────────────────────────────────────────────────────────────────────
    # RELATÓRIO EXCEL
    # ──────────────────────────────────────────────────────────────────────────

    def _gerar_relatorio(self):
        pendentes        = []
        loja_selecionada = self.var_loja.get().strip().upper()

        for serial_real, status in self._seriais_status.items():
            if status != "pendente":
                continue
            nome, loja = "N/A", "N/A"
            iid = self._iids.get(serial_real)
            if iid:
                valores = self.tree.item(iid, "values")
                if len(valores) >= 4:
                    nome, loja = valores[2], valores[3]
            if loja_selecionada != "TODAS AS LOJAS" and loja.strip().upper() != loja_selecionada:
                continue
            pendentes.append({"Serial": serial_real, "Nome": nome, "Loja": loja, "Status": "Não Bipado"})

        if not pendentes:
            messagebox.showinfo("Relatório", "Nenhum chip pendente encontrado!")
            return

        ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_loja = self.var_loja.get().strip().replace(" ", "_")
        destino   = filedialog.asksaveasfilename(title="Salvar relatório", defaultextension=".xlsx",
                                                  initialfile=f"relatorio_{nome_loja}_{ts}.xlsx",
                                                  filetypes=[("Excel", "*.xlsx")])
        if not destino:
            return

        def _gerar():
            try:
                caminho = rel.gerar_excel(pendentes, destino)
                def _finalizado():
                    if messagebox.askyesno("Relatório gerado", f"Arquivo salvo em:\n\n{caminho}\n\nDeseja abrir agora?"):
                        if sys.platform == "win32":
                            os.startfile(caminho)
                self.after(0, _finalizado)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Erro", str(e)))

        threading.Thread(target=_gerar, daemon=True).start()

if __name__ == "__main__":
    app = App()
    app.mainloop()