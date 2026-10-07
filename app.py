# -*- coding: utf-8 -*-
"""FUTURE - controle financeiro pessoal (Streamlit >= 1.40).

REQUISITOS:
    streamlit>=1.40
    cryptography
    openpyxl

PERSISTÊNCIA:
    - O app salva localmente em future_db.json.
    - Se Supabase estiver configurado, salva também na nuvem.
    - Se a nuvem falhar, o app continua funcionando usando o armazenamento local.
    - O backup do navegador é opcional e usa uma chave privada em st.secrets.

IMPORTANTE:
    Nunca coloque senhas, PINs, backup_key ou dados financeiros reais neste arquivo.
    Configure-os nos Secrets do Streamlit.

Secrets esperados:

    supabase_url = "https://SEU-PROJETO.supabase.co"
    supabase_key = "SUA_CHAVE_SERVER_SIDE"

    seed_codigo = "..."
    seed_pin = "..."
    seed_user = "..."
    seed_nome = "..."

    backup_key = "uma-chave-grande-e-aleatoria"

No Supabase:

    create table future (
        id text primary key,
        dados jsonb not null
    );

A chave usada pelo app deve ser uma chave server-side mantida apenas nos
Secrets do Streamlit.
"""

import csv
import io
import json
import random
import time
import html
import hmac
import hashlib
import base64
import secrets
import threading
import urllib.request
import urllib.error
import unicodedata

from datetime import datetime, date, timedelta
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st
import streamlit.components.v1 as components


# ================================================================
# DEPENDÊNCIAS OPCIONAIS
# ================================================================

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, padding

    HAS_CRYPTO = True
except Exception:
    HAS_CRYPTO = False


try:
    from zoneinfo import ZoneInfo

    TZ = ZoneInfo("America/Sao_Paulo")
except Exception:
    TZ = None


# ================================================================
# CONFIGURAÇÃO
# ================================================================

st.set_page_config(
    page_title="FUTURE",
    page_icon="🚀",
    layout="centered",
    initial_sidebar_state="collapsed",
)


# ----------------------------------------------------------------
# SEGREDOS
# ----------------------------------------------------------------

def secret_str(nome, padrao=""):
    """Lê um secret sem quebrar o app quando ele não existe."""
    try:
        valor = st.secrets.get(nome, padrao)
        if valor is None:
            return padrao
        return str(valor)
    except Exception:
        return padrao


CODIGO = secret_str("seed_codigo")
PIN_PAIS = secret_str("seed_pin")
SEED = secret_str("seed_user", "joao")
SEED_NOME = secret_str("seed_nome", "João")

SB_URL = secret_str("supabase_url").rstrip("/")
SB_KEY = secret_str("supabase_key")

BACKUP_SECRET = secret_str("backup_key")

if BACKUP_SECRET:
    BK = hashlib.sha256(BACKUP_SECRET.encode("utf-8")).digest()
else:
    BK = None


ARQ = Path(__file__).with_name("future_db.json")

XL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ================================================================
# CONSTANTES
# ================================================================

TIPOS = {
    "in": ("📥", "Recebi dinheiro"),
    "out": ("💸", "Gastei dinheiro"),
    "save": ("🔒", "Guardar na caixinha"),
    "take": ("🔓", "Resgatar da caixinha"),
    "yld": ("📈", "Rendimento / juros"),
    "mov": ("🔁", "Mover entre caixinhas"),
    "del": ("🗑️", "Caixinha excluída"),
}

CURTO = {
    "in": "📥 Receber",
    "out": "💸 Gastar",
    "save": "🔒 Guardar",
    "take": "🔓 Resgatar",
    "yld": "📈 Juros",
    "mov": "🔁 Mover",
}

ABAS = [
    "🏠 Início",
    "🧾 Extrato",
    "📈 Projeção",
    "💡 Ideias",
]

TITULOS = [
    "Início",
    "Extrato",
    "Projeção",
    "Ideias",
]

DIAS = [
    "segunda",
    "terça",
    "quarta",
    "quinta",
    "sexta",
    "sábado",
    "domingo",
]

MESES = [
    "jan",
    "fev",
    "mar",
    "abr",
    "mai",
    "jun",
    "jul",
    "ago",
    "set",
    "out",
    "nov",
    "dez",
]

PALETAS = {
    "Padrão": {
        "pur": "#b57bff",
        "blue": "#4aa3ff",
        "gold": "#f0c24b",
        "grn": "#3fdc78",
        "red": "#ff6b62",
    },
    "Neon": {
        "pur": "#ff00ff",
        "blue": "#00ffff",
        "gold": "#ffff00",
        "grn": "#00ff00",
        "red": "#ff0000",
    },
    "Oceano": {
        "pur": "#3a0ca3",
        "blue": "#4361ee",
        "gold": "#4cc9f0",
        "grn": "#2ec4b6",
        "red": "#e71d36",
    },
    "Outono": {
        "pur": "#6a4c93",
        "blue": "#1982c4",
        "gold": "#ffca3a",
        "grn": "#8ac926",
        "red": "#ff595e",
    },
}


# ================================================================
# SESSION STATE
# ================================================================

DEFAULT_SESSION = {
    "u": None,
    "modo": None,
    "tela": "login",
    "tema": "dark",
    "paleta": "Padrão",
    "tab": 0,
    "nav": False,
    "dir": "R",
    "fx": None,
    "msg": None,
    "warn": None,
    "tent": 0,
    "bloq": 0.0,
    "chal": secrets.token_urlsafe(32),
    "fid_done": None,
    "bak_done": None,
    "launch": False,
    "ideias_ok": None,
    "ideias_no": False,
    "storage_mode": "local",
}

for _key, _value in DEFAULT_SESSION.items():
    st.session_state.setdefault(_key, _value)


# ================================================================
# UTILIDADES
# ================================================================

def agora():
    return datetime.now(TZ) if TZ else datetime.now()


def hoje_txt():
    h = agora()
    return f"{DIAS[h.weekday()]}, {h.day} {MESES[h.month - 1]}"


def brl(v):
    try:
        v = float(v)
    except Exception:
        v = 0.0

    s = (
        f"{abs(v):,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )

    return ("-" if v < 0 else "") + "R$ " + s


def kf(v):
    return f"{v / 1000:.1f}".replace(".", ",") + "k"


def fmt_dt(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return "data inválida"


def chave(n):
    n = "".join(
        c
        for c in unicodedata.normalize("NFD", str(n))
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(n.lower().split())


def b64d(s):
    return base64.urlsafe_b64decode(
        s + "=" * (-len(s) % 4)
    )


def b64d_js_safe(s):
    """Mesma lógica do JS, mas com padding garantido."""
    return base64.urlsafe_b64decode(
        str(s) + "=" * (-len(str(s)) % 4)
    )


def mk(txt):
    salt = secrets.token_bytes(16)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        str(txt).encode(),
        salt,
        150000,
    ).hex()

    return salt.hex(), digest


def confere(txt, salt_hex, digest):
    try:
        novo = hashlib.pbkdf2_hmac(
            "sha256",
            str(txt).encode(),
            bytes.fromhex(salt_hex),
            150000,
        ).hex()

        return hmac.compare_digest(novo, digest)
    except Exception:
        return False


def _th(t):
    return hashlib.sha256(
        (t or "").encode()
    ).hexdigest()


def safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def iso_mes(ano, mes):
    return f"{ano}-{mes:02d}"


def add_months(ano, mes, quantidade):
    total = ano * 12 + (mes - 1) + quantidade
    novo_ano, novo_mes = divmod(total, 12)
    return novo_ano, novo_mes + 1


# ================================================================
# CONTAS
# ================================================================

def nova_conta(
    nome,
    senha,
    pin,
    nasc="2014-01-01",
    seed=False,
):
    s, h = mk(senha)
    ps, ph = mk(pin)

    a = agora()

    d = {
        "livre": 0.0,
        "caixas": {},
        "caixas_meta": {},
        "extrato": [],
        "tema": "dark",
        "paleta": "Padrão",
        "nasc": nasc,
        "_v": time.time(),
        "cfg": {
            "renda": 0.0,
            "guardar": 0.0,
            "gastos": 0.0,
            "cdi": 9.5,
            "sonho_data": None,
            "meta": 10000.0,
            "reserva": 100.0,
            "tutorial": not seed,
            "ajustado": False,
        },
        "ultimo_credito": f"{a.year}-{a.month:02d}",
    }

    # ------------------------------------------------------------
    # Conta inicial opcional.
    #
    # Os valores NÃO ficam mais escritos no código.
    # O seed real deve ser configurado pelos Secrets.
    # ------------------------------------------------------------

    if seed:
        d["livre"] = safe_float(
            secret_str("seed_livre", "0")
        )

        seed_caixas = {}

        try:
            bruto = secret_str("seed_caixas_json", "{}")
            seed_caixas = json.loads(bruto)

            if not isinstance(seed_caixas, dict):
                seed_caixas = {}
        except Exception:
            seed_caixas = {}

        for k, v in seed_caixas.items():
            seed_caixas[str(k)] = round(
                safe_float(v),
                2,
            )

        d["caixas"] = seed_caixas

        try:
            meta_bruta = secret_str(
                "seed_caixas_meta_json",
                "{}",
            )
            meta = json.loads(meta_bruta)

            if isinstance(meta, dict):
                d["caixas_meta"] = meta
        except Exception:
            d["caixas_meta"] = {}

        d["cfg"].update(
            renda=safe_float(
                secret_str("seed_renda", "0")
            ),
            guardar=safe_float(
                secret_str("seed_guardar", "0")
            ),
            gastos=safe_float(
                secret_str("seed_gastos", "0")
            ),
            meta=safe_float(
                secret_str("seed_meta", "10000")
            ),
            reserva=safe_float(
                secret_str("seed_reserva", "100")
            ),
            tutorial=False,
        )

    return {
        "nome": nome,
        "s": s,
        "h": h,
        "ps": ps,
        "ph": ph,
        "fid": {},
        "d": d,
    }


# ================================================================
# SUPABASE
# ================================================================

def supabase_configurado():
    return bool(SB_URL and SB_KEY)


def _sb(metodo, path="", corpo=None):
    if not supabase_configurado():
        raise RuntimeError("Supabase não configurado.")

    headers = {
        "apikey": SB_KEY,
        "Authorization": "Bearer " + SB_KEY,
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }

    url = SB_URL + "/rest/v1/future" + path

    req = urllib.request.Request(
        url,
        headers=headers,
        method=metodo,
        data=(
            None
            if corpo is None
            else json.dumps(
                corpo,
                ensure_ascii=False,
            ).encode()
        ),
    )

    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read()


def carregar_local():
    try:
        if not ARQ.exists():
            return {}

        texto = ARQ.read_text(
            encoding="utf-8"
        )

        if not texto.strip():
            return {}

        d = json.loads(texto)

        return d if isinstance(d, dict) else {}

    except Exception:
        return {}


def salvar_local(dados):
    """Escrita atômica para reduzir risco de arquivo corrompido."""
    temporario = ARQ.with_name(
        ARQ.name + ".tmp"
    )

    try:
        texto = json.dumps(
            dados,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        temporario.write_text(
            texto,
            encoding="utf-8",
        )

        temporario.replace(ARQ)

        return True

    except Exception:
        try:
            if temporario.exists():
                temporario.unlink()
        except Exception:
            pass

        return False


def carregar_nuvem():
    if not supabase_configurado():
        return None

    try:
        resultado = json.loads(
            _sb(
                "GET",
                "?id=eq.db&select=dados",
            )
        )

        if resultado:
            dados = resultado[0].get("dados")

            if isinstance(dados, dict):
                return dados

    except Exception:
        pass

    return None


@st.cache_resource
def trava():
    return threading.RLock()


@st.cache_resource
def db():
    """
    Banco em memória compartilhado pelo processo do Streamlit.

    Prioridade:
        1. Supabase, quando disponível.
        2. Arquivo local.

    O arquivo local NÃO sobrescreve automaticamente a nuvem
    quando a nuvem está funcionando. Isso evita que um arquivo
    antigo apague dados mais recentes.
    """

    dados_nuvem = carregar_nuvem()

    if dados_nuvem is not None:
        d = dados_nuvem
        st.session_state["storage_mode"] = "cloud"

        # Mantém cópia local de segurança.
        salvar_local(d)

    else:
        d = carregar_local()

        if supabase_configurado():
            st.session_state["storage_mode"] = "local-fallback"
        else:
            st.session_state["storage_mode"] = "local"

    if not isinstance(d, dict):
        d = {}

    contas = d.setdefault("contas", {})
    d.setdefault("sessoes", {})

    # ------------------------------------------------------------
    # Conta seed só é criada quando os Secrets necessários existem.
    # ------------------------------------------------------------

    if (
        SEED
        and CODIGO
        and PIN_PAIS
        and SEED not in contas
    ):
        contas[SEED] = nova_conta(
            SEED_NOME,
            CODIGO,
            PIN_PAIS,
            seed=True,
        )

        salvar_local(d)

        if supabase_configurado():
            try:
                _sb(
                    "POST",
                    "",
                    [{
                        "id": "db",
                        "dados": d,
                    }],
                )
                st.session_state["storage_mode"] = "cloud"
            except Exception:
                st.session_state["storage_mode"] = "local-fallback"

    return d


def sessoes():
    return db().setdefault(
        "sessoes",
        {},
    )


def salvar():
    """
    Persiste localmente SEMPRE.

    Depois tenta sincronizar com Supabase.
    Assim uma falha temporária da nuvem não interrompe
    o funcionamento do app.
    """

    u = st.session_state.get("u")

    dados = db()

    if (
        u
        and u in dados.get("contas", {})
    ):
        dados["contas"][u]["d"]["_v"] = time.time()

    local_ok = False
    cloud_ok = False

    with trava():
        local_ok = salvar_local(dados)

        if supabase_configurado():
            try:
                _sb(
                    "POST",
                    "",
                    [{
                        "id": "db",
                        "dados": dados,
                    }],
                )

                cloud_ok = True
                st.session_state["storage_mode"] = "cloud"

            except Exception:
                cloud_ok = False
                st.session_state["storage_mode"] = "local-fallback"

        else:
            cloud_ok = True
            st.session_state["storage_mode"] = "local"

    if not local_ok:
        st.session_state["warn"] = (
            "⚠️ Não consegui gravar o arquivo local."
        )

    elif supabase_configurado() and not cloud_ok:
        st.session_state["warn"] = (
            "☁️ A nuvem está indisponível no momento. "
            "Seus dados continuam salvos localmente."
        )


# ================================================================
# VISUAL
# ================================================================

def get_css(tema, nome):
    p = PALETAS.get(
        nome,
        PALETAS["Padrão"],
    )

    if tema == "light":
        p = {
            k: "color-mix(in srgb," + v + " 70%,#000)"
            for k, v in p.items()
        }

    cores = (
        f"--blue:{p['blue']};"
        f"--pur:{p['pur']};"
        f"--gold:{p['gold']};"
        f"--grn:{p['grn']};"
        f"--red:{p['red']}"
    )

    if tema == "light":
        return (
            ":root{"
            "--bg:#f2f2f7;"
            "--c1:rgba(255,255,255,.82);"
            "--c2:rgba(245,245,250,.86);"
            "--tx:#15151b;"
            "--mu:#6d6d78;"
            "--ln:rgba(0,0,0,.08);"
            "--s1:rgba(0,0,0,.10);"
            "--s2:rgba(255,255,255,.8);"
            "--glass:rgba(255,255,255,.68);"
            "color-scheme:light;"
            + cores
            + "}"
        )

    return (
        ":root{"
        "--bg:#07070b;"
        "--c1:rgba(23,23,31,.92);"
        "--c2:rgba(14,14,21,.88);"
        "--tx:#f4f4f8;"
        "--mu:#8b8b9a;"
        "--ln:rgba(255,255,255,.09);"
        "--s1:rgba(0,0,0,.42);"
        "--s2:rgba(255,255,255,.035);"
        "--glass:rgba(32,32,45,.64);"
        "color-scheme:dark;"
        + cores
        + "}"
    )


CSS_BASE = """
html,body,[data-testid="stApp"],[data-testid="stMain"],
[data-testid="stMainBlockContainer"]{
    background:var(--bg)!important;
    overscroll-behavior-y:none;
    margin:0;
    padding:0;
}

.stApp{
    color:var(--tx);
    overflow-x:hidden;
    transition:background .35s ease;
}

header[data-testid="stHeader"],#MainMenu,footer{
    display:none!important;
}

.block-container{
    max-width:480px!important;
    padding:1.2rem 1rem 10rem!important;
    margin:0 auto!important;
}

.stApp p,
.stApp label,
.stApp h1,
.stApp li,
[data-testid="stDialog"] *{
    color:var(--tx);
}

.stApp input,
[data-baseweb="select"]>div,
[data-baseweb="input"],
[data-baseweb="base-input"]{
    background:var(--c2)!important;
    color:var(--tx)!important;
    border-radius:15px!important;
    transition:
        border-color .22s ease,
        box-shadow .22s ease,
        background .22s ease!important;
}

.stApp input:focus{
    box-shadow:0 0 0 3px color-mix(
        in srgb,
        var(--pur) 18%,
        transparent
    )!important;
}

div[role="dialog"]{
    background:var(--c1)!important;
    border-radius:28px!important;
    border:1px solid var(--ln)!important;
    box-shadow:
        0 24px 80px rgba(0,0,0,.32),
        inset 0 1px 0 rgba(255,255,255,.06)!important;
    animation:dialogIn .28s cubic-bezier(.16,1,.3,1) both;
}

@keyframes dialogIn{
    from{
        opacity:0;
        transform:translateY(12px) scale(.985);
    }
    to{
        opacity:1;
        transform:none;
    }
}

button[kind="secondary"],
[data-testid="stBaseButton-secondary"]{
    background:var(--c2);
    border:1px solid var(--ln);
    border-radius:16px;
}

button[kind="secondary"] p,
[data-testid="stBaseButton-secondary"] p{
    color:var(--tx);
}

button[kind="primary"],
[data-testid="stBaseButton-primary"]{
    background:
        linear-gradient(
            135deg,
            var(--pur),
            var(--blue)
        )!important;
    border:0!important;
    border-radius:16px!important;
    box-shadow:
        0 7px 20px color-mix(
            in srgb,
            var(--pur) 18%,
            transparent
        );
}

button[kind="primary"] *,
[data-testid="stBaseButton-primary"] *{
    color:#fff!important;
}

button,
label{
    transition:
        transform .18s cubic-bezier(.2,.8,.2,1),
        background .25s ease,
        border-color .25s ease,
        box-shadow .25s ease,
        opacity .25s ease!important;
}

button:active,
label:active{
    transform:scale(.975)!important;
}

button:hover{
    transform:translateY(-1px);
}

[data-testid="stForm"]{
    border:0;
    padding:0;
    background:transparent;
}

.st-key-bak{
    position:fixed;
    left:0;
    bottom:0;
    width:0;
    height:0;
    overflow:hidden;
    opacity:0;
    pointer-events:none;
}

.hd h1{
    margin:0;
    font-size:26px;
    letter-spacing:-.035em;
    padding:0;
}

.hd{
    margin-bottom:16px;
}

.rkw{
    position:relative;
    display:inline-block;
}

.rkw::before{
    content:"";
    position:absolute;
    inset:-20px;
    border-radius:50%;
    background:
        radial-gradient(
            circle,
            color-mix(
                in srgb,
                var(--pur) 30%,
                transparent
            ),
            transparent 68%
        );
    animation:halo 4s ease-in-out infinite;
}

.logo{
    position:relative;
    font-size:64px;
    line-height:1;
    display:inline-block;
    animation:
        rocketLaunch .7s cubic-bezier(.175,.885,.32,1.275) both,
        bob 4.2s ease-in-out .8s infinite;
}

@keyframes rocketLaunch{
    0%{
        transform:translateY(24px) scale(.88);
        opacity:0;
    }
    70%{
        transform:translateY(-3px) scale(1.02);
        opacity:1;
    }
    100%{
        transform:none;
        opacity:1;
    }
}

@keyframes bob{
    50%{
        transform:translateY(-4px) rotate(-1.5deg);
    }
}

@keyframes halo{
    50%{
        opacity:.58;
        transform:scale(1.05);
    }
}

.card{
    background:
        linear-gradient(
            145deg,
            var(--c1),
            var(--c2)
        );
    border:1px solid color-mix(
        in srgb,
        var(--c,var(--ln)) 50%,
        transparent
    );
    border-radius:25px;
    padding:18px;
    box-shadow:
        8px 9px 24px var(--s1),
        -4px -4px 16px var(--s2);
    margin-bottom:16px;
    transition:
        transform .25s ease,
        box-shadow .25s ease,
        border-color .25s ease;
}

.card:hover{
    transform:translateY(-1px);
}

.k{
    color:var(--mu);
    font-size:13px;
}

.lb{
    font-size:14px;
    font-weight:600;
}

.big{
    font-size:34px;
    font-weight:700;
    letter-spacing:-.04em;
    margin:2px 0 8px;
    font-variant-numeric:tabular-nums;
}

.pg{
    height:8px;
    border-radius:9px;
    background:var(--ln);
    overflow:hidden;
    margin:6px 0;
}

.pg i{
    display:block;
    height:100%;
    border-radius:9px;
    background:
        linear-gradient(
            90deg,
            var(--blue),
            var(--grn)
        );
    animation:grow .8s cubic-bezier(.25,1,.5,1) both;
}

@keyframes grow{
    from{
        width:0;
    }
}

.rkbar{
    position:relative;
    padding-top:14px;
}

.rkbar s{
    position:absolute;
    top:-6px;
    margin-left:-9px;
    font-size:17px;
    text-decoration:none;
    animation:
        fly .8s cubic-bezier(.25,1,.5,1) both,
        bob 4s ease-in-out .8s infinite;
}

@keyframes fly{
    from{
        left:0;
        opacity:.2;
    }
}

.as{
    font-size:15px;
    border-style:dashed;
}

.sup{
    background:
        color-mix(
            in srgb,
            var(--gold) 16%,
            transparent
        );
    border:1px solid var(--gold);
    border-radius:18px;
    padding:12px 14px;
    margin-bottom:16px;
    font-size:14px;
}

.sp{
    display:flex;
    gap:10px;
    align-items:flex-start;
    padding:7px 0;
}

.sp>span{
    font-size:18px;
    line-height:1.3;
}

.sp.ok b{
    text-decoration:line-through;
    opacity:.5;
}

.tx{
    display:flex;
    align-items:center;
    gap:12px;
    padding:13px 0;
    border-bottom:1px solid var(--ln);
}

.tx:last-child{
    border:0;
}

.tx .g{
    flex:1;
    min-width:0;
}

.ic{
    width:40px;
    height:40px;
    border-radius:14px;
    background:var(--c2);
    display:grid;
    place-items:center;
    font-size:19px;
    flex:none;
    border:1px solid var(--ln);
}

table{
    width:100%;
    border-collapse:collapse;
    font-size:13.5px;
}

th{
    color:var(--mu);
    font-weight:500;
    text-align:right;
    padding:6px 0;
}

td{
    padding:10px 0;
    text-align:right;
    border-top:1px solid var(--ln);
}

th:first-child,
td:first-child{
    text-align:left;
}

.bar{
    fill:var(--grn);
    opacity:.9;
}

.bt{
    fill:var(--mu);
    font-size:10px;
    text-anchor:middle;
}

.tl{
    stroke:var(--gold);
    stroke-dasharray:4 4;
    stroke-width:1.2;
}

.al{
    display:flex;
    justify-content:space-between;
    align-items:baseline;
}

.al b{
    font-size:20px;
}

.st-key-nav,
.st-key-bolha{
    position:fixed;
    left:16px;
    bottom:
        calc(
            66px +
            env(safe-area-inset-bottom,0px)
        );
    z-index:999;
    width:auto!important;
}

.st-key-nav{
    width:min(
        calc(100vw - 32px),
        420px
    )!important;

    display:flex!important;
    flex-direction:row!important;
    align-items:center;

    gap:4px!important;
    padding:6px;

    overflow:hidden;

    background:var(--glass);
    backdrop-filter:blur(28px) saturate(180%);
    -webkit-backdrop-filter:blur(28px) saturate(180%);

    border:1px solid var(--ln);
    border-radius:34px;

    box-shadow:
        0 14px 40px var(--s1),
        inset 0 1px 0 rgba(255,255,255,.14);

    animation:
        navIn .28s cubic-bezier(.16,1,.3,1) both;
}

@keyframes navIn{
    from{
        opacity:0;
        transform:translateY(10px) scale(.98);
    }
    to{
        opacity:1;
        transform:none;
    }
}

.st-key-nav>div{
    width:auto!important;
}

.st-key-aba{
    flex:1!important;
}

.st-key-nav [role="radiogroup"]{
    display:flex;
    flex-wrap:nowrap;
    gap:2px;
    width:100%;
}

.st-key-nav label{
    flex:1;
    justify-content:center;
    margin:0;
    padding:8px 0;
    border-radius:26px;
    cursor:pointer;
}

.st-key-nav label>div:first-child{
    display:none;
}

.st-key-nav label p{
    font-size:10px;
    line-height:1.3;
    font-weight:600;
    text-align:center;
    word-spacing:100vw;
    margin:0;
    opacity:.55;
    transition:opacity .25s ease;
}

.st-key-nav label p::first-line{
    font-size:21px;
}

.st-key-nav label:has(input:checked){
    background:
        color-mix(
            in srgb,
            var(--pur) 24%,
            transparent
        );
}

.st-key-nav label:has(input:checked) p{
    opacity:1;
}

.st-key-b_min button,
.st-key-b_plus button,
.st-key-bolha button,
.st-key-b_tema button,
.st-key-b_ajustes_top button,
.st-key-b_sair button{
    border-radius:50%;
    padding:0;
    background:var(--glass);
    backdrop-filter:blur(20px);
    -webkit-backdrop-filter:blur(20px);
    border:1px solid var(--ln);
}

.st-key-b_min button{
    width:34px;
    height:34px;
}

.st-key-b_plus button{
    width:46px;
    height:46px;
    border:0;
    background:
        linear-gradient(
            135deg,
            var(--pur),
            var(--blue)
        );
}

.st-key-b_plus button p{
    color:#fff;
    font-size:24px;
    line-height:1;
}

.st-key-bolha{
    animation:
        popin .3s cubic-bezier(.2,1.2,.4,1) both;
}

.st-key-bolha button{
    width:58px;
    height:58px;
    font-size:24px;
    box-shadow:
        0 10px 30px var(--s1);
}

@keyframes popin{
    from{
        transform:scale(.92);
        opacity:0;
    }
}

.st-key-b_tema,
.st-key-b_ajustes_top,
.st-key-b_sair{
    position:fixed;
    z-index:1000;
    width:auto!important;
    top:
        calc(
            12px +
            env(safe-area-inset-top,0px)
        );
}

.st-key-b_tema{
    right:118px;
}

.st-key-b_ajustes_top{
    right:66px;
}

.st-key-b_sair{
    right:14px;
}

.st-key-b_tema button,
.st-key-b_ajustes_top button,
.st-key-b_sair button{
    width:44px;
    height:44px;
    font-size:18px;
}

[class*="_fromR"]{
    animation:
        slR .28s cubic-bezier(.25,1,.5,1) both;
}

[class*="_fromL"]{
    animation:
        slL .28s cubic-bezier(.25,1,.5,1) both;
}

@keyframes slR{
    from{
        transform:translateX(12px);
        opacity:.25;
    }
    to{
        transform:none;
        opacity:1;
    }
}

@keyframes slL{
    from{
        transform:translateX(-12px);
        opacity:.25;
    }
    to{
        transform:none;
        opacity:1;
    }
}

.fx,
.lift{
    position:fixed;
    inset:0;
    pointer-events:none;
    z-index:2000;
    overflow:hidden;
}

.fx i{
    position:absolute;
    bottom:-50px;
    font-style:normal;
    opacity:0;
    animation:
        rise 2.4s ease-out forwards;
}

.fx b{
    position:absolute;
    left:50%;
    top:36%;
    font-size:36px;
    color:var(--grn);
    opacity:0;
    animation:
        pop 2.4s ease forwards;
    text-shadow:
        0 4px 24px rgba(0,0,0,.35);
}

@keyframes rise{
    0%{
        transform:translateY(0) scale(.6);
        opacity:0;
    }
    15%{
        opacity:1;
    }
    100%{
        transform:
            translateY(-90vh)
            rotate(25deg)
            scale(1.1);
        opacity:0;
    }
}

@keyframes pop{
    0%{
        opacity:0;
        transform:
            translate(-50%,30px)
            scale(.7);
    }
    20%{
        opacity:1;
        transform:
            translate(-50%,0)
            scale(1.05);
    }
    80%{
        opacity:1;
    }
    100%{
        opacity:0;
        transform:
            translate(-50%,-40px);
    }
}

.lift i{
    position:absolute;
    left:6%;
    bottom:-70px;
    font-size:56px;
    font-style:normal;
    filter:
        drop-shadow(
            0 0 18px var(--gold)
        );
    animation:
        blast 1.2s cubic-bezier(.5,0,.9,.4) forwards;
}

@keyframes blast{
    to{
        transform:
            translate(78vw,-118vh)
            scale(.6);
    }
}

html,
body,
.stApp,
.stApp p,
.stApp label,
.stApp input,
.stApp textarea,
.stApp button,
.stApp [data-baseweb],
div[role="dialog"] p{
    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "SF Pro Text",
        system-ui,
        sans-serif!important;
}

.big,
.hd h1,
.al b,
.lb{
    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "SF Pro Display",
        system-ui,
        sans-serif!important;
}

.dh{
    font-size:11.5px;
    font-weight:600;
    letter-spacing:.07em;
    text-transform:uppercase;
    color:var(--mu);
    padding:12px 0 2px;
}

.dh:first-child{
    padding-top:8px;
}

.mes{
    display:flex;
    gap:8px;
    margin-top:8px;
}

.mes>div{
    flex:1;
}

.mes b{
    font-size:16px;
    font-variant-numeric:tabular-nums;
}

[class*="st-key-conf"] [data-testid="stHorizontalBlock"],
[class*="st-key-dl"] [data-testid="stHorizontalBlock"]{
    flex-direction:row!important;
    flex-wrap:nowrap!important;
    gap:10px!important;
}

[class*="st-key-conf"] [data-testid="stColumn"],
[class*="st-key-dl"] [data-testid="stColumn"],
[class*="st-key-conf"] [data-testid="column"],
[class*="st-key-dl"] [data-testid="column"]{
    min-width:0!important;
    flex:1 1 0!important;
    width:auto!important;
}

.bar{
    transform-box:fill-box;
    transform-origin:50% 100%;
    animation:
        barUp .65s cubic-bezier(.25,1,.5,1) both;
}

@keyframes barUp{
    from{
        transform:scaleY(0);
    }
}

[data-baseweb="popover"],
[data-baseweb="popover"]>div,
[data-baseweb="menu"],
ul[role="listbox"]{
    background:var(--c1)!important;
    border-radius:16px!important;
}

[data-baseweb="popover"] *,
ul[role="listbox"] *{
    color:var(--tx)!important;
}

li[role="option"]:hover,
li[aria-selected="true"]{
    background:var(--c2)!important;
}

[data-baseweb="calendar"],
[data-baseweb="calendar"] *{
    background-color:var(--c1)!important;
    color:var(--tx)!important;
}

[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] *{
    color:var(--mu)!important;
}

[data-testid="stAlert"]{
    background:
        color-mix(
            in srgb,
            var(--pur) 12%,
            var(--c1)
        )!important;
    border:1px solid var(--ln)!important;
    border-radius:16px!important;
}

[data-testid="stAlert"] *,
[data-testid="stToast"] *{
    color:var(--tx)!important;
}

[data-testid="stToast"]{
    background:var(--c1)!important;
    border:1px solid var(--ln)!important;
    border-radius:16px!important;
}

[data-testid="stNumberInput"] button,
[data-testid="stDownloadButton"] button{
    background:var(--c2)!important;
    color:var(--tx)!important;
    border-color:var(--ln)!important;
}

[data-testid="stDownloadButton"] button p{
    color:var(--tx)!important;
}

button[data-baseweb="tab"] p{
    color:var(--mu)!important;
}

button[data-baseweb="tab"][aria-selected="true"] p{
    color:var(--tx)!important;
}

[data-baseweb="tab-border"]{
    background:var(--ln)!important;
}

[data-baseweb="tab-highlight"]{
    background:var(--pur)!important;
}

hr{
    border-color:var(--ln)!important;
}

input::placeholder{
    color:var(--mu)!important;
    opacity:1;
}

[data-baseweb="select"] *{
    color:var(--tx)!important;
}

[data-baseweb="select"] svg{
    fill:var(--mu)!important;
}

[data-testid="stSlider"] *,
[data-testid="stSliderThumbValue"],
[data-testid="stTickBarMin"],
[data-testid="stTickBarMax"],
[data-testid="stCheckbox"] *{
    color:var(--tx)!important;
}

[data-baseweb="slider"] [role="slider"]{
    background:var(--pur)!important;
}

@media (prefers-reduced-motion:reduce){
    *,
    ::before,
    ::after{
        animation:none!important;
        transition:none!important;
        scroll-behavior:auto!important;
    }
}
"""


st.markdown(
    "<style>"
    + get_css(
        st.session_state["tema"],
        st.session_state["paleta"],
    )
    + CSS_BASE
    + "</style>",
    unsafe_allow_html=True,
)


# ================================================================
# INICIALIZA BANCO
# ================================================================

try:
    db()
except Exception:
    st.error(
        "Não foi possível carregar os dados. "
        "Tente atualizar a página."
    )
    st.stop()


# ================================================================
# COMPONENTES
# ================================================================

def _componente(nome, html_src):
    d = Path(__file__).with_name("_" + nome)

    try:
        d.mkdir(exist_ok=True)

        (d / "index.html").write_text(
            html_src,
            encoding="utf-8",
        )

    except Exception:
        pass

    return components.declare_component(
        nome,
        path=str(d),
    )


# ----------------------------------------------------------------
# BACKUP
# ----------------------------------------------------------------

BAK_HTML = r"""
<!DOCTYPE html>
<html>
<body>
<script>

const P = (t,d) =>
    parent.postMessage(
        Object.assign(
            {
                isStreamlitMessage:true,
                type:t
            },
            d
        ),
        "*"
    );

let first = true;
let last = "";

addEventListener("message", ev => {

    if(ev.data.type !== "streamlit:render")
        return;

    const A = ev.data.args || {};

    let m = {};

    try{
        m = JSON.parse(
            localStorage.getItem("future_bak") || "{}"
        );
    }catch(e){
        m = {};
    }

    if(A.save && A.save !== last){

        last = A.save;

        try{
            const o = JSON.parse(A.save);

            if(o && o.u){
                m[o.u] = o;

                localStorage.setItem(
                    "future_bak",
                    JSON.stringify(m)
                );
            }

        }catch(e){}
    }

    if(first){

        first = false;

        P(
            "streamlit:setComponentValue",
            {
                value:{
                    n:Date.now()+Math.random(),
                    itens:Object.values(m)
                },
                dataType:"json"
            }
        );
    }

    P(
        "streamlit:setFrameHeight",
        {
            height:0
        }
    );

});

P(
    "streamlit:componentReady",
    {
        apiVersion:1
    }
);

</script>
</body>
</html>
"""


# ----------------------------------------------------------------
# FACE ID
# ----------------------------------------------------------------

FACEID_HTML = r"""
<!DOCTYPE html>
<html>
<body
style="
margin:0;
font-family:-apple-system,system-ui,sans-serif;
">

<button id="b"></button>

<div id="m"></div>

<script>

const P = (t,d) =>
    parent.postMessage(
        Object.assign(
            {
                isStreamlitMessage:true,
                type:t
            },
            d
        ),
        "*"
    );

const e64 = b =>
    btoa(
        String.fromCharCode(
            ...new Uint8Array(b)
        )
    )
    .replace(/\+/g,"-")
    .replace(/\//g,"_")
    .replace(/=+$/,"");

const d64 = s => {

    s = String(s || "");

    s = s
        .replace(/-/g,"+")
        .replace(/_/g,"/");

    s += "=".repeat(
        (4 - s.length % 4) % 4
    );

    return Uint8Array.from(
        atob(s),
        c => c.charCodeAt(0)
    );
};

const B = document.getElementById("b");
const M = document.getElementById("m");

let A = {};

const done = v =>
    P(
        "streamlit:setComponentValue",
        {
            value:Object.assign(
                {
                    n:Date.now()+Math.random()
                },
                v
            ),
            dataType:"json"
        }
    );


async function reg(){

    try{

        const c =
            await navigator.credentials.create({
                publicKey:{
                    challenge:d64(A.chal),

                    rp:{
                        name:"FUTURE",
                        id:location.hostname
                    },

                    user:{
                        id:new TextEncoder().encode(A.user),
                        name:A.user,
                        displayName:A.user
                    },

                    pubKeyCredParams:[
                        {
                            type:"public-key",
                            alg:-7
                        },
                        {
                            type:"public-key",
                            alg:-257
                        }
                    ],

                    authenticatorSelection:{
                        authenticatorAttachment:"platform",
                        userVerification:"required"
                    },

                    timeout:60000
                }
            });

        const r = c.response;

        const L =
            JSON.parse(
                localStorage.getItem("future_auth") || "[]"
            )
            .filter(x => x.id !== c.id);

        L.push({
            id:c.id,
            user:A.user
        });

        localStorage.setItem(
            "future_auth",
            JSON.stringify(L)
        );

        done({
            kind:"reg",
            id:c.id,
            pk:e64(r.getPublicKey()),
            alg:r.getPublicKeyAlgorithm(),
            cd:e64(r.clientDataJSON)
        });

    }catch(e){

        M.textContent =
            "Não foi possível ativar (" +
            e.name +
            ")";

    }
}


async function get(){

    try{

        const L =
            JSON.parse(
                localStorage.getItem("future_auth") || "[]"
            );

        if(!L.length){

            M.textContent =
                "Ative o Face ID nos Ajustes depois de entrar.";

            return;
        }

        const c =
            await navigator.credentials.get({
                publicKey:{
                    challenge:d64(A.chal),

                    rpId:location.hostname,

                    allowCredentials:
                        L.map(x => ({
                            type:"public-key",
                            id:d64(x.id)
                        })),

                    userVerification:"required",

                    timeout:60000
                }
            });

        const r = c.response;

        const u =
            (
                L.find(
                    x => x.id === c.id
                ) || {}
            ).user;

        done({
            kind:"get",
            id:c.id,
            user:u,
            ad:e64(r.authenticatorData),
            cd:e64(r.clientDataJSON),
            sg:e64(r.signature)
        });

    }catch(e){

        M.textContent =
            "Face ID cancelado.";

    }
}


addEventListener("message", ev => {

    if(ev.data.type !== "streamlit:render")
        return;

    A = ev.data.args || {};

    const dark =
        A.tema === "dark";

    document.body.style.color =
        dark
        ? "#8b8b9a"
        : "#656575";

    M.style.cssText =
        "font-size:12px;" +
        "text-align:center;" +
        "margin-top:6px";

    B.style.cssText =
        "width:100%;" +
        "padding:14px;" +
        "border-radius:16px;" +
        "font-size:16px;" +
        "font-weight:600;" +
        "cursor:pointer;" +
        "border:1px solid " +
        (
            dark
            ? "rgba(255,255,255,.14)"
            : "rgba(0,0,0,.14)"
        ) +
        ";" +
        "background:" +
        (
            dark
            ? "#16161f"
            : "#fff"
        ) +
        ";" +
        "color:" +
        (
            dark
            ? "#f4f4f8"
            : "#14141c"
        );

    B.textContent =
        A.modo === "reg"
        ? "Ativar Face ID neste aparelho"
        : "Entrar com Face ID";

    B.onclick =
        A.modo === "reg"
        ? reg
        : get;

    P(
        "streamlit:setFrameHeight",
        {
            height:88
        }
    );

});

P(
    "streamlit:componentReady",
    {
        apiVersion:1
    }
);

</script>
</body>
</html>
"""


BACKUP = _componente(
    "bak",
    BAK_HTML,
)

FACEID = _componente(
    "faceid",
    FACEID_HTML,
)


# ================================================================
# BACKUP DO NAVEGADOR
# ================================================================

def _payload():
    if not BK:
        return None

    u = st.session_state.get("u")

    if u not in db()["contas"]:
        return None

    token_hash = _th(
        st.query_params.get("s", "")
    )

    corpo_sessao = {}

    if token_hash in sessoes():
        corpo_sessao[token_hash] = sessoes()[
            token_hash
        ]

    body = json.dumps(
        {
            "c": db()["contas"][u],
            "s": corpo_sessao,
        },
        sort_keys=True,
        ensure_ascii=False,
    )

    assinatura = hmac.new(
        BK,
        body.encode(),
        "sha256",
    ).hexdigest()

    return json.dumps(
        {
            "u": u,
            "body": body,
            "sig": assinatura,
        }
    )


def restaurar(itens):
    """
    Restaura apenas backups assinados com a chave privada
    configurada nos Secrets.

    O backup do navegador nunca deve ser considerado
    a fonte principal quando a nuvem está disponível.
    """

    if not BK:
        return False

    mudou = False

    for it in itens or []:

        try:
            body = it["body"]
            sig = it["sig"]

            esperado = hmac.new(
                BK,
                body.encode(),
                "sha256",
            ).hexdigest()

            if not hmac.compare_digest(
                esperado,
                sig,
            ):
                continue

            b = json.loads(body)
            u = b["u"]

            atual = db()["contas"].get(u)

            backup_conta = b["c"]

            backup_v = safe_float(
                backup_conta.get(
                    "d",
                    {}
                ).get("_v", 0)
            )

            atual_v = (
                safe_float(
                    atual.get(
                        "d",
                        {}
                    ).get("_v", 0)
                )
                if atual
                else 0
            )

            # Só restaura se:
            # - conta não existe; ou
            # - backup é realmente mais novo.
            if (
                atual is None
                or (
                    backup_v > atual_v
                    and atual_v <= 0
                )
            ):
                db()["contas"][u] = backup_conta

                for h, r in b.get("s", {}).items():

                    try:
                        if (
                            time.time() - r[2]
                            < 30 * 86400
                        ):
                            sessoes()[h] = r
                    except Exception:
                        pass

                mudou = True

        except Exception:
            continue

    if mudou:
        salvar()

    return mudou


if BK:

    _bk_val = BACKUP(
        save=_payload(),
        key="bak",
        default=None,
    )

    if (
        _bk_val
        and _bk_val.get("n")
        != st.session_state["bak_done"]
    ):
        st.session_state["bak_done"] = _bk_val["n"]

        if restaurar(
            _bk_val.get("itens")
        ):
            st.rerun()


# ================================================================
# FACE ID
# ================================================================

def _cd(p, tipo):
    try:
        cd = json.loads(
            b64d_js_safe(
                p["cd"]
            )
        )
    except Exception:
        return None

    if (
        cd.get("type") == tipo
        and cd.get("challenge")
        == st.session_state["chal"]
    ):
        return cd

    return None


def fid_registrar(u, p):

    cd = _cd(
        p,
        "webauthn.create",
    )

    st.session_state["chal"] = (
        secrets.token_urlsafe(32)
    )

    if cd:

        db()["contas"][u].setdefault(
            "fid",
            {},
        )

        db()["contas"][u]["fid"][
            p["id"]
        ] = {
            "pk": p["pk"],
            "alg": p["alg"],
        }

        salvar()

    return bool(cd)


def fid_entrar(p):

    cd = _cd(
        p,
        "webauthn.get",
    )

    st.session_state["chal"] = (
        secrets.token_urlsafe(32)
    )

    c = db()["contas"].get(
        p.get("user") or ""
    )

    cr = (
        c.get("fid", {}).get(
            p.get("id")
        )
        if c
        else None
    )

    if not (
        cd
        and cr
        and HAS_CRYPTO
    ):
        return None

    try:

        ad = b64d_js_safe(
            p["ad"]
        )

        host = (
            urlparse(
                cd["origin"]
            ).hostname
            or ""
        )

        rp_hash = hashlib.sha256(
            host.encode()
        ).digest()

        if ad[:32] != rp_hash:
            return None

        # UP flag = 0x01
        # UV flag = 0x04
        flags = ad[32]

        if not (
            flags & 1
            and flags & 4
        ):
            return None

        msg = (
            ad
            + hashlib.sha256(
                b64d_js_safe(
                    p["cd"]
                )
            ).digest()
        )

        pub = serialization.load_der_public_key(
            b64d_js_safe(
                cr["pk"]
            )
        )

        sig = b64d_js_safe(
            p["sg"]
        )

        if cr["alg"] == -7:

            pub.verify(
                sig,
                msg,
                ec.ECDSA(
                    hashes.SHA256()
                ),
            )

        else:

            pub.verify(
                sig,
                msg,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )

        return p["user"]

    except Exception:
        return None


# ================================================================
# LOGIN / SESSÃO
# ================================================================

def entrar(u, modo):

    tok = secrets.token_urlsafe(24)

    sessoes()[
        _th(tok)
    ] = [
        u,
        modo,
        time.time(),
    ]

    st.query_params["s"] = tok

    salvar()

    d = db()["contas"][u]["d"]

    st.session_state.update(
        u=u,
        modo=modo,
        tela="login",
        tent=0,
        launch=True,
        tema=d.get(
            "tema",
            "dark",
        ),
        paleta=d.get(
            "paleta",
            "Padrão",
        ),
    )

    st.rerun()


def _ir(t):
    st.session_state["tela"] = t


def _falha():
    st.session_state["tent"] += 1

    if st.session_state["tent"] >= 3:

        st.session_state.update(
            bloq=time.time() + 60,
            tent=0,
        )

    st.error(
        "Dados incorretos. "
        "Após 3 erros o acesso é bloqueado "
        "por 1 minuto."
    )


def _espera():

    e = (
        st.session_state["bloq"]
        - time.time()
    )

    if e > 0:

        st.error(
            "Segurança ativada. "
            f"Aguarde {int(e) + 1}s "
            "para tentar novamente."
        )

    return e > 0


# ================================================================
# LOGIN
# ================================================================

def tela_login():

    t = st.session_state["tela"]

    sub = {
        "login": "INICIAR SESSÃO",
        "criar": "CRIAR CONTA",
        "pais": "CONTROLE PARENTAL",
    }[t]

    st.markdown(
        """
        <div
            style="
            display:flex;
            flex-direction:column;
            align-items:center;
            width:100%;
            text-align:center;
            padding:5vh 0 2vh;
            "
        >
            <div class="rkw">
                <div class="logo">🚀</div>
            </div>

            <h1
                style="
                font-size:36px;
                margin:14px 0 5px;
                padding:0;
                font-weight:800;
                letter-spacing:-1px;
                width:100%;
                text-align:center;
                "
            >
                FUTURE
            </h1>

            <div
                style="
                color:var(--mu);
                font-size:13px;
                letter-spacing:.2em;
                width:100%;
                text-align:center;
                "
            >
        """
        + sub
        + """
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if t == "login":

        with st.form("f_login"):

            n = st.text_input(
                "Nome",
                placeholder="Nome da conta",
                label_visibility="collapsed",
                max_chars=24,
            )

            p = st.text_input(
                "Senha",
                type="password",
                placeholder="Senha",
                label_visibility="collapsed",
            )

            go = st.form_submit_button(
                "Entrar",
                type="primary",
                use_container_width=True,
            )

        if go and not _espera():

            usuario = chave(n)

            c = db()["contas"].get(
                usuario
            )

            if (
                c
                and confere(
                    p,
                    c["s"],
                    c["h"],
                )
            ):
                entrar(
                    usuario,
                    "filho",
                )
            else:
                _falha()

        if HAS_CRYPTO:

            r = FACEID(
                modo="get",
                chal=st.session_state["chal"],
                user="",
                tema=st.session_state["tema"],
                key="fid_get",
                default=None,
            )

            if (
                r
                and r.get("kind") == "get"
                and r["n"]
                != st.session_state["fid_done"]
            ):

                st.session_state["fid_done"] = r["n"]

                u = fid_entrar(r)

                if u:
                    entrar(
                        u,
                        "filho",
                    )
                else:
                    st.error(
                        "Face ID não reconhecido."
                    )

        st.button(
            "🛡️ Controle parental",
            key="b_pais",
            use_container_width=True,
            on_click=_ir,
            args=("pais",),
        )

        st.button(
            "Criar nova conta",
            key="b_criar",
            use_container_width=True,
            on_click=_ir,
            args=("criar",),
        )

        storage_msg = (
            "☁️ Dados sincronizados na nuvem."
            if supabase_configurado()
            else
            "💾 Dados salvos automaticamente neste servidor."
        )

        st.caption(storage_msg)

        return

    if t == "criar":

        with st.form("f_criar"):

            n = st.text_input(
                "Nome da conta",
                max_chars=24,
            )

            p = st.text_input(
                "Senha (mín. 4 caracteres)",
                type="password",
            )

            pin = st.text_input(
                "PIN dos pais (4 números)",
                type="password",
                max_chars=4,
            )

            nasc = st.date_input(
                "Data de nascimento",
                value=date(
                    2014,
                    1,
                    1,
                ),
                min_value=date(
                    1950,
                    1,
                    1,
                ),
                max_value=agora().date(),
                format="DD/MM/YYYY",
            )

            go = st.form_submit_button(
                "Criar conta",
                type="primary",
                use_container_width=True,
            )

        if go:

            k = chave(n)

            if not 2 <= len(k) <= 24:

                st.error(
                    "Use um nome entre 2 e 24 caracteres."
                )

            elif k in db()["contas"]:

                st.error(
                    "Esse nome já existe."
                )

            elif len(p) < 4:

                st.error(
                    "A senha precisa ter no mínimo 4 caracteres."
                )

            elif not (
                pin.isdigit()
                and len(pin) == 4
            ):

                st.error(
                    "O PIN dos pais precisa ter exatamente 4 números."
                )

            else:

                db()["contas"][k] = nova_conta(
                    n.strip(),
                    p,
                    pin,
                    nasc=nasc.isoformat(),
                )

                salvar()

                entrar(
                    k,
                    "filho",
                )

    else:

        with st.form("f_pais"):

            n = st.text_input(
                "Nome da conta supervisionada",
                max_chars=24,
            )

            pin = st.text_input(
                "PIN dos pais",
                type="password",
                max_chars=4,
            )

            go = st.form_submit_button(
                "Entrar em supervisão",
                type="primary",
                use_container_width=True,
            )

        if go and not _espera():

            usuario = chave(n)

            c = db()["contas"].get(
                usuario
            )

            if (
                c
                and confere(
                    pin,
                    c["ps"],
                    c["ph"],
                )
            ):

                entrar(
                    usuario,
                    "pais",
                )

            else:
                _falha()

    st.button(
        "← Voltar",
        key="b_volta",
        use_container_width=True,
        on_click=_ir,
        args=("login",),
    )


# ================================================================
# RESTAURA SESSÃO
# ================================================================

if not st.session_state["u"]:

    token = st.query_params.get(
        "s",
        "",
    )

    r = sessoes().get(
        _th(token)
    )

    if (
        r
        and r[0] in db()["contas"]
        and time.time() - r[2] < 30 * 86400
    ):

        d = db()["contas"][
            r[0]
        ]["d"]

        st.session_state.update(
            u=r[0],
            modo=r[1],
            tema=d.get(
                "tema",
                "dark",
            ),
            paleta=d.get(
                "paleta",
                "Padrão",
            ),
        )

if not st.session_state["u"]:

    tela_login()
    st.stop()


# ================================================================
# CONTA ATUAL
# ================================================================

U = st.session_state["u"]

SUP = (
    st.session_state["modo"]
    == "pais"
)

CONTA = db()["contas"][U]

S = CONTA["d"]

S.setdefault(
    "livre",
    0.0,
)

S.setdefault(
    "caixas",
    {},
)

S.setdefault(
    "caixas_meta",
    {},
)

S.setdefault(
    "extrato",
    [],
)

S.setdefault(
    "cfg",
    {},
)

S.setdefault(
    "ultimo_credito",
    f"{agora().year}-{agora().month:02d}",
)

for _k, _v in {
    "meta": 62000.0,
    "reserva": 100.0,
    "tutorial": False,
    "ajustado": True,
    "cdi": 9.5,
    "gastos": 0.0,
    "renda": 0.0,
    "guardar": 0.0,
    "sonho_data": None,
}.items():

    S["cfg"].setdefault(
        _k,
        _v,
    )

for _k, _t in (
    (
        "futuro",
        [
            "Caixinha Futuro",
            "pur",
            "Principal · rende 100% do CDI",
        ],
    ),
    (
        "sonho",
        [
            "Caixinha Sonho",
            "gold",
            "Rende 100% do CDI · resgate imediato",
        ],
    ),
):

    if _k in S["caixas"]:

        S["caixas_meta"].setdefault(
            _k,
            _t,
        )


# ================================================================
# REGRAS DE NEGÓCIO
# ================================================================

def total():
    return round(
        safe_float(S["livre"])
        + sum(
            safe_float(v)
            for v in S["caixas"].values()
        ),
        2,
    )


def idade_info():

    try:
        n = date.fromisoformat(
            S.get(
                "nasc",
                "2014-01-01",
            )
        )
    except Exception:
        n = date(
            2014,
            1,
            1,
        )

    h = agora().date()

    idade = (
        h.year
        - n.year
        - (
            (h.month, h.day)
            < (n.month, n.day)
        )
    )

    try:
        b18 = n.replace(
            year=n.year + 18
        )
    except ValueError:
        b18 = date(
            n.year + 18,
            3,
            1,
        )

    if h >= b18:
        meses = 0
    else:

        meses = (
            (b18.year - h.year) * 12
            + b18.month
            - h.month
        )

        if b18.day < h.day:
            meses -= 1

        meses = max(
            0,
            meses,
        )

    return idade, b18, meses


def prazo_txt(m):

    a, mm = divmod(
        max(0, int(m)),
        12,
    )

    p = []

    if a:
        p.append(
            f"{a} ano"
            + ("s" if a > 1 else "")
        )

    if mm:
        p.append(
            f"{mm} "
            + (
                "mês"
                if mm == 1
                else "meses"
            )
        )

    return " e ".join(p) or "menos de 1 mês"


def reg(
    t,
    v,
    cx,
    obs,
    ts=None,
    dest=None,
):

    M = S["caixas_meta"]

    S["extrato"].append(
        {
            "t": t,
            "v": round(
                safe_float(v),
                2,
            ),
            "c": cx,
            "d": dest,
            "o": obs,
            "ts": (
                ts or agora()
            ).isoformat(),
            "cn": (
                M.get(
                    cx,
                    [None],
                )[0]
                if cx
                else None
            ),
            "dn": (
                M.get(
                    dest,
                    [None],
                )[0]
                if dest
                else None
            ),
        }
    )


def fx(valor):

    st.session_state["fx"] = {
        "txt": "+" + brl(valor),
        "n": int(
            time.time() * 1000
        ),
    }


def fecha(msg=None):

    S["livre"] = round(
        safe_float(S["livre"]),
        2,
    )

    for k in list(S["caixas"]):
        S["caixas"][k] = round(
            safe_float(
                S["caixas"][k]
            ),
            2,
        )

    if msg:

        st.session_state["msg"] = msg

    elif S["extrato"]:

        st.session_state["msg"] = (
            "Lançado em "
            + fmt_dt(
                S["extrato"][-1]["ts"]
            )
        )

    salvar()


def visivel(k):
    return (
        S["caixas"][k] > 0.004
        or not any(
            x.get("c") == k
            or x.get("d") == k
            for x in S["extrato"]
        )
    )


def nome_cx(k):
    return S["caixas_meta"].get(
        k,
        ["Caixinha"],
    )[0]


def aplicar(
    t,
    v,
    cx=None,
    obs="",
):

    v = round(
        safe_float(v),
        2,
    )

    reserva = safe_float(
        S["cfg"]["reserva"]
    )

    cxs = S["caixas"]

    if v <= 0:
        return (
            "Informe um valor maior que zero."
        )

    if t == "save":

        if not cx:
            return "Escolha uma caixinha."

        if cx not in cxs:
            return "Essa caixinha não existe."

        if (
            S["livre"] - v
            < reserva - 1e-9
        ):

            return (
                f"A reserva fixa de {brl(reserva)} "
                f"está protegida. "
                f"Você pode guardar até "
                f"{brl(max(0, S['livre'] - reserva))}."
            )

        S["livre"] -= v
        cxs[cx] += v

    elif t == "take":

        if not cx or cx not in cxs:
            return "Escolha uma caixinha."

        if v > cxs[cx] + 1e-9:

            return (
                f"Essa caixinha tem só "
                f"{brl(cxs[cx])}."
            )

        cxs[cx] -= v
        S["livre"] += v

    elif t == "yld":

        if not cx or cx not in cxs:
            return "Escolha uma caixinha."

        if cxs[cx] <= 0:
            return (
                "Essa caixinha não tem saldo para render."
            )

        cxs[cx] += v

    elif t == "out":

        if v > S["livre"] + 1e-9:

            return (
                f"Saldo livre insuficiente "
                f"({brl(S['livre'])})."
            )

        S["livre"] -= v

    elif t == "in":

        S["livre"] += v

    else:
        return "Tipo de lançamento inválido."

    reg(
        t,
        v,
        cx
        if t in (
            "save",
            "take",
            "yld",
        )
        else None,
        obs,
    )

    if t in (
        "in",
        "yld",
    ):
        fx(v)

    fecha()

    return ""


def mover(
    o,
    d,
    v,
    obs="",
):

    v = round(
        safe_float(v),
        2,
    )

    if v <= 0:
        return (
            "Informe um valor maior que zero."
        )

    if o not in S["caixas"]:
        return "Caixinha de origem inválida."

    if d not in S["caixas"]:
        return "Caixinha de destino inválida."

    if o == d:
        return (
            "Escolha caixinhas diferentes."
        )

    if v > S["caixas"][o] + 1e-9:
        return (
            f"{nome_cx(o)} tem só "
            f"{brl(S['caixas'][o])}."
        )

    S["caixas"][o] -= v
    S["caixas"][d] += v

    reg(
        "mov",
        v,
        o,
        obs,
        dest=d,
    )

    fecha()

    return ""


def excluir_caixinha(
    cx,
    resgatar,
):

    if cx not in S["caixas"]:
        return

    v = S["caixas"][cx]
    nome = nome_cx(cx)

    if resgatar:

        S["livre"] += v

        reg(
            "take",
            v,
            cx,
            "Resgate por exclusão",
        )

    else:

        reg(
            "del",
            v,
            cx,
            "Saldo removido do patrimônio",
        )

    S["caixas"].pop(
        cx,
        None,
    )

    S["caixas_meta"].pop(
        cx,
        None,
    )

    fecha(
        f"{nome} excluída"
    )


def liberar_sonho():

    sd = S["cfg"].get(
        "sonho_data"
    )

    if (
        sd
        and agora().date().isoformat()
        >= sd
    ):

        if (
            "sonho" in S["caixas"]
            and "futuro" in S["caixas"]
            and S["caixas"]["sonho"]
            > 0.004
        ):

            mover(
                "sonho",
                "futuro",
                S["caixas"]["sonho"],
                "Sonho liberada → Futuro",
            )

        S["cfg"]["sonho_data"] = None

        salvar()


# ================================================================
# CRÉDITO MENSAL
# ================================================================

def creditar_mes():
    """
    Processa os meses que passaram desde ultimo_credito.

    Regra de segurança:
        gastos nunca podem empurrar o saldo para negativo.

    Se não houver saldo suficiente para pagar todos os gastos
    programados, apenas o valor disponível é lançado.
    """

    h = agora()
    c = S["cfg"]

    try:
        a, m = S[
            "ultimo_credito"
        ].split("-")

        ult = (
            int(a) * 12
            + int(m)
            - 1
        )

    except Exception:

        ult = (
            h.year * 12
            + h.month
            - 2
        )

    atual = (
        h.year * 12
        + h.month
        - 1
    )

    if atual <= ult:
        return

    renda = max(
        0.0,
        safe_float(
            c["renda"]
        ),
    )

    gastos = max(
        0.0,
        safe_float(
            c["gastos"]
        ),
    )

    guardar = max(
        0.0,
        safe_float(
            c["guardar"]
        ),
    )

    cx = next(
        iter(S["caixas"]),
        None,
    )

    n = 0

    for k in range(
        ult + 1,
        atual + 1,
    ):

        ano, mes = divmod(
            k,
            12,
        )

        mes += 1

        ts = datetime(
            ano,
            mes,
            1,
            0,
            0,
            0,
            tzinfo=TZ,
        )

        if renda > 0:

            S["livre"] += renda

            reg(
                "in",
                renda,
                None,
                "Renda mensal programada",
                ts,
            )

        # --------------------------------------------------------
        # GASTO SEM SALDO NEGATIVO
        # --------------------------------------------------------

        gasto_real = min(
            gastos,
            max(
                0.0,
                S["livre"],
            ),
        )

        if gasto_real > 0:

            S["livre"] -= gasto_real

            obs = (
                "Gastos fixos do mês"
                if gasto_real >= gastos - 1e-9
                else
                "Gastos fixos do mês "
                "(lançamento parcial por saldo insuficiente)"
            )

            reg(
                "out",
                gasto_real,
                None,
                obs,
                ts,
            )

        # --------------------------------------------------------
        # APORTE AUTOMÁTICO
        # --------------------------------------------------------

        capacidade = max(
            0.0,
            S["livre"],
        )

        guardar_real = min(
            guardar,
            capacidade,
        )

        if (
            guardar_real > 0
            and cx
        ):

            S["livre"] -= guardar_real
            S["caixas"][cx] += guardar_real

            reg(
                "save",
                guardar_real,
                cx,
                "Aporte automático mensal",
                ts,
            )

        n += 1

    S["ultimo_credito"] = (
        f"{h.year}-{h.month:02d}"
    )

    if n:

        if renda > 0:
            fx(renda)

        fecha(
            "Entradas e saídas do mês "
            "lançadas automaticamente."
        )

    else:
        salvar()


# ================================================================
# SIMULAÇÃO
# ================================================================

def _passos(
    extra=0.0,
    limite_meses=None,
):
    """
    Simula mês a mês.

    limite_meses:
        quando informado, a simulação termina exatamente
        nesse número de meses.
    """

    c = S["cfg"]
    h = agora()

    cdi = max(
        0.0,
        safe_float(c["cdi"]),
    )

    r = (
        (1 + cdi / 100)
        ** (1 / 12)
        - 1
    )

    cx = {
        k: max(
            0.0,
            safe_float(v),
        )
        for k, v in S["caixas"].items()
    }

    lv = max(
        0.0,
        safe_float(S["livre"]),
    )

    ap = total()

    main = next(
        iter(cx),
        None,
    )

    renda = max(
        0.0,
        safe_float(c["renda"]),
    )

    gastos = max(
        0.0,
        safe_float(c["gastos"]),
    )

    guard = max(
        0.0,
        safe_float(c["guardar"]),
    )

    net = (
        renda
        - gastos
        + safe_float(extra)
    )

    if main:
        g = (
            min(
                guard,
                max(
                    0.0,
                    renda - gastos,
                ),
            )
            + safe_float(extra)
        )
    else:
        g = 0.0

    ano = h.year
    mes = h.month

    passos = 0

    while True:

        if (
            limite_meses is not None
            and passos >= limite_meses
        ):
            break

        mes += 1

        if mes > 12:
            mes = 1
            ano += 1

        # --------------------------------------------------------
        # Rendimento do saldo livre.
        # --------------------------------------------------------

        lv = max(
            0.0,
            lv * (1 + r)
            + net
            - g,
        )

        # --------------------------------------------------------
        # Rendimento das caixinhas.
        # --------------------------------------------------------

        for k in list(cx):
            cx[k] *= 1 + r

        if main:
            cx[main] += g

        ap += net

        passos += 1

        yield (
            ano,
            mes,
            lv + sum(cx.values()),
            ap,
            lv,
            dict(cx),
        )


def projetar():

    h = agora()

    idade, b18, meses = idade_info()

    # ------------------------------------------------------------
    # Antes dos 18:
    # simulação exata até o mês do aniversário.
    #
    # Depois dos 18:
    # mantém uma janela de 10 anos.
    # ------------------------------------------------------------

    if meses > 0:

        limite = meses
        ano_fim = b18.year

    else:

        limite = 120
        ano_fim = h.year + 10

    atual = total()

    por_ano = {
        h.year: (
            atual,
            atual,
            S["livre"],
            dict(S["caixas"]),
        )
    }

    ultimo = None

    for (
        ano,
        mes,
        b,
        ap,
        lv,
        cx,
    ) in _passos(
        limite_meses=limite
    ):

        por_ano[ano] = (
            b,
            ap,
            lv,
            cx,
        )

        ultimo = (
            ano,
            mes,
        )

    # Garante que o ano final realmente existe.
    if ano_fim not in por_ano:

        if ultimo:

            por_ano[ano_fim] = (
                b,
                ap,
                lv,
                cx,
            )

        else:

            por_ano[ano_fim] = (
                atual,
                atual,
                S["livre"],
                dict(S["caixas"]),
            )

    linhas = [
        (
            a,
            v[1],
            v[0] - v[1],
            v[0],
        )
        for a, v in sorted(
            por_ano.items()
        )
    ]

    n = limite

    r = (
        1
        + max(
            0.0,
            safe_float(
                S["cfg"]["cdi"]
            ),
        )
        / 100
    ) ** (1 / 12) - 1

    meta = safe_float(
        S["cfg"]["meta"]
    )

    if n and r > 0:

        g = (
            (1 + r) ** n
        )

        falta = max(
            0.0,
            (
                meta
                - total() * g
            )
            / (
                (g - 1) / r
            ),
        )

    elif n:

        falta = max(
            0.0,
            (
                meta
                - total()
            )
            / n,
        )

    else:
        falta = 0.0

    final_state = por_ano[
        ano_fim
    ]

    return (
        linhas,
        falta,
        ano_fim,
        meta,
        final_state[2:],
    )


def final_com(extra):

    ano_fim = projetar()[2]

    idade, b18, meses = idade_info()

    limite = (
        meses
        if meses > 0
        else 120
    )

    ult = total()

    for (
        ano,
        mes,
        b,
        *_,
    ) in _passos(
        extra,
        limite_meses=limite,
    ):

        ult = b

    return ult


def mes_meta(extra=0.0):

    h = agora()

    if total() >= S["cfg"]["meta"]:
        return (
            h.year,
            h.month,
        )

    idade, b18, meses = idade_info()

    limite = (
        meses
        if meses > 0
        else 120
    )

    for i, (
        ano,
        mes,
        b,
        *_,
    ) in enumerate(
        _passos(
            extra,
            limite_meses=limite,
        )
    ):

        if b >= S["cfg"]["meta"]:
            return (
                ano,
                mes,
            )

        if i > 720:
            break

    return None


def fmt_mes(t):

    if not t:
        return "além do período projetado"

    return (
        f"{MESES[t[1] - 1]}"
        f"/{t[0]}"
    )


def destino(x):

    s = (
        x.get("cn")
        or (
            nome_cx(x["c"])
            if x.get("c")
            else ""
        )
    )

    d = (
        x.get("dn")
        or (
            nome_cx(x["d"])
            if x.get("d")
            else ""
        )
    )

    return (
        s
        + (
            " → " + d
            if d
            else ""
        )
    )


# ================================================================
# DOWNLOADS
# ================================================================

def _csv(
    cab,
    linhas,
):

    buf = io.StringIO()

    w = csv.writer(
        buf,
        delimiter=";",
    )

    w.writerow(cab)
    w.writerows(linhas)

    return (
        "\ufeff"
        + buf.getvalue()
    ).encode(
        "utf-8"
    )


def _xlsx(
    titulo,
    cab,
    linhas,
    fmts,
    larg,
    notas=(),
    grafico=False,
):

    try:

        from openpyxl import Workbook

        from openpyxl.styles import (
            Font,
            PatternFill,
            Alignment,
        )

        from openpyxl.chart import (
            BarChart,
            Reference,
        )

        from openpyxl.utils import (
            get_column_letter as col,
        )

    except Exception:

        return None

    wb = Workbook()

    ws = wb.active

    ws.title = titulo

    ws.sheet_view.showGridLines = False

    ws["A1"] = (
        "🚀 FUTURE · "
        + titulo
    )

    ws["A1"].font = Font(
        bold=True,
        size=16,
        color="5B2BE0",
    )

    ws["A2"] = (
        f"{CONTA['nome']} · "
        f"gerado em "
        f"{agora():%d/%m/%Y às %H:%M}"
    )

    ws["A2"].font = Font(
        size=10,
        color="888888",
    )

    for j, c in enumerate(
        cab,
        1,
    ):

        x = ws.cell(
            4,
            j,
            c,
        )

        x.font = Font(
            bold=True,
            color="FFFFFF",
        )

        x.fill = PatternFill(
            "solid",
            fgColor="5B2BE0",
        )

        x.alignment = Alignment(
            horizontal="center",
            vertical="center",
        )

        ws.column_dimensions[
            col(j)
        ].width = larg[j - 1]

    ws.row_dimensions[4].height = 24

    for i, lin in enumerate(
        linhas,
        1,
    ):

        for j, v in enumerate(
            lin,
            1,
        ):

            x = ws.cell(
                4 + i,
                j,
                v,
            )

            if fmts[j - 1]:
                x.number_format = (
                    fmts[j - 1]
                )

            if i % 2 == 0:

                x.fill = PatternFill(
                    "solid",
                    fgColor="F3EEFF",
                )

    ws.freeze_panes = "A5"

    n = len(linhas) + 6

    for k, (
        a,
        v,
        f,
    ) in enumerate(notas):

        ws.cell(
            n + k,
            1,
            a,
        ).font = Font(
            bold=True
        )

        x = ws.cell(
            n + k,
            2,
            v,
        )

        if f:
            x.number_format = f

    if grafico and linhas:

        ch = BarChart()

        ch.title = (
            "Patrimônio projetado"
        )

        ch.height = 8
        ch.width = 16
        ch.legend = None

        ch.add_data(
            Reference(
                ws,
                min_col=4,
                min_row=4,
                max_row=4 + len(linhas),
            ),
            titles_from_data=True,
        )

        ch.set_categories(
            Reference(
                ws,
                min_col=1,
                min_row=5,
                max_row=4 + len(linhas),
            )
        )

        ws.add_chart(
            ch,
            col(len(cab) + 2) + "4",
        )

    buf = io.BytesIO()

    wb.save(buf)

    return buf.getvalue()


MOEDA = (
    '"R$" #,##0.00;'
    '[Red]-"R$" #,##0.00'
)


def proj_dados():

    L, _, _, meta, _ = projetar()

    return [
        (
            a,
            p,
            j,
            b,
            b / meta
            if meta > 0
            else 0,
        )
        for a, p, j, b in L
    ]


def xlsx_proj():

    c = S["cfg"]

    return _xlsx(
        "Projeção",
        [
            "Ano",
            "Capital investido",
            "Juros acumulados",
            "Patrimônio total",
            "% da meta",
        ],
        proj_dados(),
        [
            None,
            MOEDA,
            MOEDA,
            MOEDA,
            "0.0%",
        ],
        [
            10,
            22,
            22,
            22,
            14,
        ],
        [
            (
                "Meta (R$)",
                c["meta"],
                MOEDA,
            ),
            (
                "Ponto de partida (R$)",
                total(),
                MOEDA,
            ),
            (
                "Aporte líquido mensal (R$)",
                max(
                    0.0,
                    c["renda"]
                    - c["gastos"],
                ),
                MOEDA,
            ),
            (
                "CDI estimado (% a.a.)",
                c["cdi"],
                None,
            ),
        ],
        True,
    )


def csv_proj():

    m = lambda v: (
        f"{v:.2f}".replace(
            ".",
            ",",
        )
    )

    return _csv(
        [
            "Ano",
            "Capital investido (R$)",
            "Juros acumulados (R$)",
            "Patrimônio total (R$)",
            "% da meta",
        ],
        [
            (
                a,
                m(p),
                m(j),
                m(b),
                f"{q * 100:.1f}".replace(
                    ".",
                    ",",
                )
                + "%",
            )
            for a, p, j, b, q
            in proj_dados()
        ],
    )


def _extrato_linhas():

    out = []

    for x in sorted(
        S["extrato"],
        key=lambda e: e["ts"],
        reverse=True,
    ):

        if x["t"] in (
            "in",
            "yld",
        ):
            v = x["v"]

        elif x["t"] in (
            "out",
            "del",
        ):
            v = -x["v"]

        else:
            v = x["v"]

        out.append(
            (
                datetime.fromisoformat(
                    x["ts"]
                ).replace(
                    tzinfo=None
                ),
                TIPOS[x["t"]][1],
                destino(x),
                x["o"],
                v,
            )
        )

    return out


def xlsx_ext():

    return _xlsx(
        "Extrato",
        [
            "Data e hora",
            "Tipo",
            "Caixinha",
            "Observação",
            "Valor (R$)",
        ],
        _extrato_linhas(),
        [
            "dd/mm/yyyy hh:mm",
            None,
            None,
            None,
            MOEDA,
        ],
        [
            20,
            26,
            34,
            32,
            18,
        ],
        [
            (
                "Patrimônio atual (R$)",
                total(),
                MOEDA,
            )
        ],
    )


def csv_ext():

    return _csv(
        [
            "Data",
            "Hora",
            "Tipo",
            "Caixinha",
            "Valor (R$)",
            "Observação",
        ],
        [
            (
                d.strftime("%d/%m/%Y"),
                d.strftime("%H:%M:%S"),
                t,
                c,
                f"{v:.2f}".replace(
                    ".",
                    ",",
                ),
                (
                    "'"
                    + o
                    if o[:1]
                    in "=+-@"
                    and o
                    else o
                ),
            )
            for d, t, c, o, v
            in _extrato_linhas()
        ],
    )


# ================================================================
# PDF
# ================================================================

_W = {
    **{
        str(i): 556
        for i in range(10)
    },
    ",": 278,
    ".": 278,
    " ": 278,
    "R": 722,
    "$": 556,
    "%": 889,
    "-": 333,
    "/": 278,
    "|": 260,
    "k": 500,
}


class _Pdf:

    def __init__(self):
        self.o = []

    @staticmethod
    def _c(c):
        return (
            "%.3f %.3f %.3f"
            % c
        )

    def rect(
        self,
        x,
        y,
        w,
        h,
        c,
    ):

        self.o.append(
            "%s rg %.1f %.1f %.1f %.1f re f"
            % (
                self._c(c),
                x,
                y,
                w,
                h,
            )
        )

    def line(
        self,
        x1,
        y1,
        x2,
        y2,
        c,
        lw=1.0,
        dash=False,
    ):

        self.o.append(
            "%s RG %.1f w %s %.1f %.1f m %.1f %.1f l S [] 0 d"
            % (
                self._c(c),
                lw,
                "[4 3] 0 d"
                if dash
                else "",
                x1,
                y1,
                x2,
                y2,
            )
        )

    def txt(
        self,
        x,
        y,
        t,
        sz=10,
        c=(0.1, 0.1, 0.15),
        bold=False,
        al="l",
    ):

        t = str(t)

        wd = (
            sum(
                _W.get(
                    ch,
                    520,
                )
                for ch in t
            )
            * sz
            / 1000
        )

        if al == "r":
            x -= wd

        elif al == "c":
            x -= wd / 2

        e = (
            t.encode(
                "cp1252",
                "replace",
            )
            .decode("latin-1")
            .replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )

        self.o.append(
            "BT /F%d %g Tf %s rg %.1f %.1f Td (%s) Tj ET"
            % (
                2 if bold else 1,
                sz,
                self._c(c),
                x,
                y,
                e,
            )
        )

    def pdf(self):

        ct = "\n".join(
            self.o
        ).encode(
            "latin-1"
        )

        objs = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
            b"<< /Length %d >>\nstream\n"
            % len(ct)
            + ct
            + b"\nendstream",
        ]

        out = b"%PDF-1.4\n"
        offs = []

        for i, o in enumerate(
            objs,
            1,
        ):

            offs.append(
                len(out)
            )

            out += (
                b"%d 0 obj\n"
                % i
                + o
                + b"\nendobj\n"
            )

        x = len(out)

        out += (
            b"xref\n0 %d\n"
            % (len(objs) + 1)
        )

        out += (
            b"0000000000 65535 f \n"
        )

        out += b"".join(
            b"%010d 00000 n \n"
            % o
            for o in offs
        )

        out += (
            b"trailer\n"
            b"<< /Size %d /Root 1 0 R >>\n"
            b"startxref\n"
            b"%d\n"
            b"%%%%EOF"
            % (
                len(objs) + 1,
                x,
            )
        )

        return out


def pdf_proj():

    (
        L,
        falta,
        ano_fim,
        meta,
        state,
    ) = projetar()

    lv, cxf = state

    fim = L[-1][3]

    c = S["cfg"]

    P = _Pdf()

    roxo = (
        0.43,
        0.25,
        0.88,
    )

    cinza = (
        0.45,
        0.43,
        0.55,
    )

    claro = (
        0.95,
        0.93,
        0.99,
    )

    ouro = (
        0.84,
        0.61,
        0.0,
    )

    P.rect(
        0,
        722,
        595,
        120,
        roxo,
    )

    P.txt(
        40,
        805,
        "FUTURE  |  Projeção financeira",
        10,
        (1, 1, 1),
        True,
    )

    P.txt(
        40,
        790,
        f"{CONTA['nome']}  ·  gerado em {agora():%d/%m/%Y}",
        9,
        (0.9, 0.85, 1),
    )

    P.txt(
        40,
        752,
        brl(fim),
        34,
        (1, 1, 1),
        True,
    )

    P.txt(
        40,
        735,
        (
            f"Projeção para {ano_fim}"
            f"  ·  meta de {brl(meta)}"
            + (
                " alcançada"
                if fim >= meta
                else
                f"  ·  faltam {brl(meta - fim)}"
            )
        ),
        10,
        (1, 1, 1),
    )

    P.txt(
        40,
        700,
        (
            f"Hoje: {brl(total())}"
            f"   |   Aporte líquido: "
            f"{brl(max(0.0, c['renda'] - c['gastos']))}/mês"
            f"   |   100% do CDI"
        ),
        9,
        cinza,
    )

    P.txt(
        40,
        672,
        "Evolução do patrimônio",
        11,
        bold=True,
    )

    mx = (
        max(
            [meta]
            + [x[3] for x in L]
        )
        * 1.1
    ) or 1

    slot = (
        515
        / len(L)
    )

    base = 470

    for i, (
        a,
        ap,
        j,
        b,
    ) in enumerate(L):

        h = (
            b / mx * 165
        )

        x = (
            40
            + i * slot
            + slot * .19
        )

        P.rect(
            x,
            base,
            slot * .62,
            max(
                h,
                0.5,
            ),
            roxo,
        )

        P.txt(
            x + slot * .31,
            base + h + 4,
            kf(b),
            8,
            cinza,
            al="c",
        )

        P.txt(
            x + slot * .31,
            base - 12,
            str(a),
            8,
            cinza,
            al="c",
        )

    ym = (
        base
        + meta / mx * 165
    )

    P.line(
        40,
        ym,
        555,
        ym,
        ouro,
        1,
        True,
    )

    P.txt(
        40,
        ym + 4,
        "Meta " + kf(meta),
        8,
        ouro,
        True,
    )

    y = 438

    P.txt(
        40,
        y,
        "Ano",
        9,
        cinza,
        True,
    )

    for xr, t in (
        (215, "Investido"),
        (335, "Juros"),
        (455, "Total"),
        (555, "% da meta"),
    ):

        P.txt(
            xr,
            y,
            t,
            9,
            cinza,
            True,
            "r",
        )

    y -= 8

    for i, (
        a,
        ap,
        j,
        b,
    ) in enumerate(L):

        y -= 17

        if i % 2 == 0:

            P.rect(
                34,
                y - 4,
                527,
                17,
                claro,
            )

        P.txt(
            40,
            y,
            str(a),
            9.5,
        )

        P.txt(
            215,
            y,
            brl(ap),
            9.5,
            al="r",
        )

        P.txt(
            335,
            y,
            brl(j),
            9.5,
            (
                0.07,
                0.52,
                0.25,
            ),
            al="r",
        )

        P.txt(
            455,
            y,
            brl(b),
            9.5,
            bold=True,
            al="r",
        )

        P.txt(
            555,
            y,
            (
                f"{b / meta * 100:.0f}%"
                if meta
                else "-"
            ),
            9.5,
            al="r",
        )

    y -= 30

    if y > 110:

        P.txt(
            40,
            y,
            f"Onde seu dinheiro estará em {ano_fim}",
            11,
            bold=True,
        )

        itens = [
            (
                "Saldo livre",
                S["livre"],
                lv,
            )
        ]

        itens += [
            (
                nome_cx(k),
                S["caixas"][k],
                cxf.get(
                    k,
                    0.0,
                ),
            )
            for k in S["caixas"]
        ]

        for nm, hoje, fut in itens[:5]:

            y -= 16

            if y < 60:
                break

            P.txt(
                40,
                y,
                nm,
                9.5,
            )

            P.txt(
                555,
                y,
                f"{brl(hoje)} hoje  >  {brl(fut)}",
                9.5,
                al="r",
            )

    P.txt(
        40,
        36,
        "Simulação educativa: rendimento de 100% do CDI estimado, bruto e sem impostos. Não é recomendação de investimento.",
        7.5,
        cinza,
    )

    return P.pdf()


# ================================================================
# TELAS
# ================================================================

def fx_html(d):

    random.seed(
        d["n"]
    )

    itens = "".join(
        '<i style="left:%d%%;font-size:%dpx;animation-delay:%.2fs;animation-duration:%.2fs">%s</i>'
        % (
            random.randint(
                4,
                90,
            ),
            random.randint(
                22,
                38,
            ),
            random.random() * .9,
            1.8
            + random.random()
            * 1.2,
            random.choice(
                [
                    "💵",
                    "💸",
                    "🪙",
                    "💰",
                ]
            ),
        )
        for _ in range(16)
    )

    return (
        '<div class="fx">'
        + itens
        + "<b>"
        + d["txt"]
        + "</b></div>"
    )


def card(
    cor,
    tit,
    val,
    sub="",
    extra="",
):
    return (
        '<div class="card" style="--c:var(--'
        + cor
        + ')">'
        '<div class="lb" style="color:var(--'
        + cor
        + ')">'
        + tit
        + "</div>"
        '<div class="big">'
        + val
        + "</div>"
        + extra
        + '<div class="k">'
        + sub
        + "</div>"
        "</div>"
    )


def passos():

    c = S["cfg"]

    p = [
        (
            "Definir sua meta e reserva",
            "Toque em ⚙️ no topo da tela",
            c["ajustado"],
        ),
        (
            "Cadastrar renda e gastos do mês",
            "⚙️ › Balanço mensal",
            c["renda"] > 0,
        ),
        (
            "Criar sua primeira caixinha",
            "＋ › Montar Caixinha",
            bool(S["caixas"]),
        ),
        (
            "Fazer seu primeiro lançamento",
            "＋ › Conta ou Caixinhas",
            bool(S["extrato"]),
        ),
    ]

    if HAS_CRYPTO:

        p.append(
            (
                "Ativar o Face ID",
                "⚙️ › Ativar Face ID neste aparelho",
                bool(CONTA.get("fid")),
            )
        )

    return p


def v_tutorial():

    idade, b18, meses = idade_info()

    ps = passos()

    feitos = sum(
        1
        for p in ps
        if p[2]
    )

    frase = (
        f"Faltam <b>{prazo_txt(meses)}</b> "
        "para os 18 anos. Cada mês conta!"
        if meses > 0
        else
        f"Você já tem {idade} anos, "
        "então a projeção olha 10 anos à frente."
    )

    lis = "".join(
        '<div class="sp'
        + (
            " ok"
            if f
            else ""
        )
        + '"><span>'
        + (
            "✅"
            if f
            else "⭕"
        )
        + "</span><div><b>"
        + a
        + "</b><div class=\"k\">"
        + b
        + "</div></div></div>"
        for a, b, f in ps
    )

    tit = (
        "🎉 Tudo pronto!"
        if feitos == len(ps)
        else
        "👋 Vamos começar, "
        + html.escape(
            CONTA["nome"]
        )
        + "?"
    )

    return (
        '<div class="card as" style="border-color:var(--pur)">'
        '<div class="lb" style="color:var(--pur);font-size:16px">'
        + tit
        + "</div>"
        '<div class="k" style="margin:4px 0 8px">'
        + frase
        + "</div>"
        '<div class="pg"><i style="width:'
        + str(
            feitos
            / len(ps)
            * 100
        )
        + '%"></i></div>'
        '<div class="k">'
        + str(feitos)
        + " de "
        + str(len(ps))
        + " passos</div>"
        '<div style="margin-top:8px">'
        + lis
        + "</div></div>"
    )


def v_home():

    t = total()

    f = S["livre"]

    c = S["cfg"]

    _, _, ano_fim, meta, _ = projetar()

    idade, b18, meses = idade_info()

    reserva = safe_float(
        c["reserva"]
    )

    pc = (
        min(
            100,
            t / meta * 100,
        )
        if meta > 0
        else 0
    )

    if f > reserva + .005:

        msg = (
            "Você tem <b>"
            + brl(
                f - reserva
            )
            + "</b> acima da reserva fixa. "
              "Veja onde aplicar na aba Ideias."
        )

    elif f < reserva - .005:

        msg = (
            "Atenção: faltam <b>"
            + brl(
                reserva - f
            )
            + "</b> para completar a sua reserva fixa."
        )

    else:

        msg = (
            "Sua reserva fixa está completa. "
            "Tudo em ordem."
        )

    h = agora()

    prox_ano, prox_mes = add_months(
        h.year,
        h.month,
        1,
    )

    prox = (
        f"01/{prox_mes:02d}/{prox_ano}"
    )

    mesada = (
        "<br>Próxima entrada automática: "
        + prox
        if (
            c["renda"] > 0
            or c["gastos"] > 0
        )
        else
        "<br>Configure renda e gastos em ⚙️."
    )

    pct = f"{pc:.1f}".replace(
        ".",
        ",",
    )

    prazo = (
        f"faltam {prazo_txt(meses)} para os 18 anos"
        if meses > 0
        else
        f"projeção até {ano_fim}"
    )

    out = card(
        "grn",
        "Patrimônio total",
        brl(t),
        f"{pct}% da meta de {brl(meta)} · {prazo}",
        '<div class="rkbar">'
        '<div class="pg"><i style="width:'
        + str(pc)
        + '%"></i></div>'
        '<s style="left:'
        + str(
            max(
                pc,
                2,
            )
        )
        + '%">🚀</s></div>',
    )

    out += (
        '<div class="card as">💡 '
        + msg
        + "</div>"
    )

    out += card(
        "blue",
        "Saldo livre",
        brl(f),
        "Reserva fixa: "
        + brl(reserva)
        + mesada,
    )

    out += v_mes()

    for k, v in S["caixas"].items():

        if visivel(k):

            m = S[
                "caixas_meta"
            ].get(
                k,
                [
                    "Caixinha",
                    "blue",
                    "",
                ],
            )

            out += card(
                m[1],
                html.escape(
                    m[0]
                ),
                brl(v),
                html.escape(
                    m[2]
                )
                or
                "Faça o primeiro aporte em ＋ › Caixinhas",
            )

    return out


def v_mes():

    h = agora()

    pre = (
        f"{h.year}-{h.month:02d}"
    )

    e = 0.0
    sd = 0.0
    r = 0.0

    for x in S["extrato"]:

        if x["ts"][:7] == pre:

            if x["t"] == "in":
                e += x["v"]

            elif x["t"] == "out":
                sd += x["v"]

            elif x["t"] == "yld":
                r += x["v"]

    rend = (
        sum(
            S["caixas"].values()
        )
        * (
            (
                1
                + S["cfg"]["cdi"]
                / 100
            )
            ** (1 / 252)
            - 1
        )
    )

    cel = (
        lambda t, v, cor:
        '<div><div class="k">'
        + t
        + '</div><b style="color:var(--'
        + cor
        + ')">'
        + brl(v)
        + "</b></div>"
    )

    nota = (
        f"Suas caixinhas rendem cerca de "
        f"{brl(rend)} por dia útil (100% do CDI)."
        if rend >= 0.005
        else
        "Guarde um valor em uma caixinha "
        "para começar a render."
    )

    return (
        '<div class="card">'
        '<div class="lb">Este mês · '
        + MESES[h.month - 1]
        + "/"
        + str(h.year)
        + "</div>"
        '<div class="mes">'
        + cel(
            "Entrou",
            e,
            "grn",
        )
        + cel(
            "Saiu",
            sd,
            "red",
        )
        + cel(
            "Rendeu",
            r,
            "pur",
        )
        + "</div>"
        '<div class="k" style="margin-top:10px">'
        + nota
        + "</div></div>"
    )


def dia_rotulo(iso):

    d = datetime.fromisoformat(
        iso
    ).date()

    h = agora().date()

    if d == h:
        return "Hoje"

    if (
        h - d
    ).days == 1:
        return "Ontem"

    return (
        f"{DIAS[d.weekday()]}, "
        f"{d.day} "
        f"{MESES[d.month - 1]}"
        + (
            f" {d.year}"
            if d.year != h.year
            else ""
        )
    )


def v_ext():

    if not S["extrato"]:

        return (
            '<div class="card">'
            '<div class="k">'
            "🌱 Nenhum lançamento ainda. "
            "Toque em ＋ para começar."
            "</div></div>"
        )

    rows = ""
    ult = None

    for _, x in sorted(
        enumerate(
            S["extrato"]
        ),
        key=lambda p: (
            p[1]["ts"],
            p[0],
        ),
        reverse=True,
    ):

        dia = dia_rotulo(
            x["ts"]
        )

        if dia != ult:

            rows += (
                '<div class="dh">'
                + dia
                + "</div>"
            )

            ult = dia

        ic, nome = TIPOS[
            x["t"]
        ]

        tr = x["t"] in (
            "save",
            "take",
            "mov",
        )

        ps = x["t"] in (
            "in",
            "yld",
        )

        cor = (
            "blue"
            if tr
            else "grn"
            if ps
            else "red"
        )

        sg = {
            "save": "→ ",
            "take": "← ",
            "mov": "↔ ",
        }.get(
            x["t"],
            "+"
            if ps
            else "−",
        )

        det = (
            (
                html.escape(
                    destino(x)
                )
                + " · "
            )
            if x.get("c")
            else ""
        )

        if x["o"]:

            det += (
                html.escape(
                    x["o"]
                )
                + " · "
            )

        det += fmt_dt(
            x["ts"]
        )

        rows += (
            '<div class="tx">'
            '<span class="ic">'
            + ic
            + "</span>"
            '<div class="g">'
            "<b>"
            + nome
            + "</b>"
            '<div class="k">'
            + det
            + "</div></div>"
            '<b style="color:var(--'
            + cor
            + ')">'
            + sg
            + brl(x["v"])
            + "</b></div>"
        )

    return (
        '<div class="card" style="padding:6px 16px">'
        + rows
        + "</div>"
    )


def svg_barras(
    L,
    meta,
):

    W = 340
    H = 210

    mx = (
        max(
            [meta]
            + [
                x[3]
                for x in L
            ]
        )
        * 1.12
        if meta > 0
        else 1000.0
    )

    bw = (
        W
        / max(
            1,
            len(L),
        )
    )

    ty = (
        H
        - 24
        - meta / mx
        * (
            H - 44
        )
    )

    s = (
        '<svg viewBox="0 0 '
        + str(W)
        + " "
        + str(H)
        + '" style="width:100%;height:auto;touch-action:pan-y">'
        '<line class="tl" x1="0" x2="'
        + str(W)
        + '" y1="'
        + f"{ty:.1f}"
        + '" y2="'
        + f"{ty:.1f}"
        + '"/>'
        '<text class="bt" style="fill:var(--gold);text-anchor:start" x="2" y="'
        + f"{ty - 5:.1f}"
        + '">Meta '
        + kf(meta)
        + "</text>"
    )

    for i, (
        ano,
        ap,
        j,
        b,
    ) in enumerate(L):

        h = (
            b / mx
            * (
                H - 44
            )
        )

        x = (
            i * bw
            + bw * .17
        )

        s += (
            '<rect class="bar" style="animation-delay:'
            + str(i * 70)
            + 'ms" x="'
            + f"{x:.1f}"
            + '" y="'
            + f"{H - 24 - h:.1f}"
            + '" width="'
            + f"{bw * .66:.1f}"
            + '" height="'
            + f"{h:.1f}"
            + '" rx="7"/>'
            '<text class="bt" x="'
            + f"{x + bw * .33:.1f}"
            + '" y="'
            + f"{H - 28 - h:.1f}"
            + '">'
            + kf(b)
            + "</text>"
            '<text class="bt" x="'
            + f"{x + bw * .33:.1f}"
            + '" y="'
            + str(H - 7)
            + '">'
            + str(ano)
            + "</text>"
        )

    return s + "</svg>"


def v_proj():

    (
        L,
        falta,
        ano_fim,
        meta,
        state,
    ) = projetar()

    lv, cxf = state

    fim = L[-1][3]

    c = S["cfg"]

    quando = fmt_mes(
        mes_meta()
    )

    if fim >= meta:

        sub = (
            f"Meta de {brl(meta)} "
            f"alcançada em {quando}, "
            f"com {brl(fim - meta)} "
            f"de folga até {ano_fim}."
        )

    else:

        sub = (
            f"No ritmo atual a meta chega em {quando}. "
            f"Para chegar até {ano_fim}, "
            f"o aporte mensal precisa ser de "
            f"cerca de {brl(falta)}."
        )

    topo = card(
        "grn"
        if fim >= meta
        else "gold",
        "Projeção até "
        + str(ano_fim),
        brl(fim),
        sub,
    )

    tab = (
        "<table>"
        "<tr>"
        "<th>Ano</th>"
        "<th>Investido</th>"
        "<th>Juros</th>"
        "<th>Total</th>"
        "</tr>"
    )

    for a, p, j, b in L:

        tab += (
            "<tr>"
            "<td>"
            + str(a)
            + "</td>"
            "<td>"
            + brl(p)
            + "</td>"
            '<td style="color:var(--grn)">'
            + brl(j)
            + "</td>"
            "<td><b>"
            + brl(b)
            + "</b></td>"
            "</tr>"
        )

    partes = [
        (
            "Saldo livre",
            S["livre"],
            lv,
            "blue",
        )
    ]

    partes += [
        (
            nome_cx(k),
            S["caixas"][k],
            cxf.get(
                k,
                0.0,
            ),
            S["caixas_meta"].get(
                k,
                [
                    "",
                    "pur",
                ],
            )[1],
        )
        for k in S["caixas"]
    ]

    onde = "".join(
        '<div class="al" style="padding:6px 0">'
        '<span class="lb" style="color:var(--'
        + cor
        + ')">'
        + html.escape(nm)
        + '</span><span class="k">'
        + brl(h0)
        + ' → <span style="color:var(--tx);font-weight:700">'
        + brl(h1)
        + "</span></span></div>"
        for nm, h0, h1, cor
        in partes
    )

    resto = (
        '<div class="card">'
        + svg_barras(
            L,
            meta,
        )
        + "</div>"
        '<div class="card">'
        '<div class="lb" style="margin-bottom:4px">'
        "Onde seu dinheiro estará em "
        + str(ano_fim)
        + "</div>"
        + onde
        + "</div>"
        '<div class="card">'
        + tab
        + "</table></div>"
        '<div class="k" style="padding:0 6px">'
        "Ponto de partida de hoje: "
        + brl(total())
        + " (saldo livre + caixinhas) · "
        "aporte líquido de "
        + brl(
            max(
                0.0,
                c["renda"]
                - c["gastos"],
            )
        )
        + "/mês · sempre 100% do CDI "
        "(estimado, bruto e sem garantia)."
        "</div>"
    )

    return topo, resto


def v_idea():

    reserva = safe_float(
        S["cfg"]["reserva"]
    )

    ex = round(
        max(
            0.0,
            S["livre"]
            - reserva,
        ),
        2,
    )

    main = next(
        iter(S["caixas"]),
        None,
    )

    out = ""

    for k, v in S["caixas"].items():

        if v <= 0.004:
            continue

        m = S[
            "caixas_meta"
        ].get(
            k,
            [
                "Caixinha",
                "blue",
                "",
            ],
        )

        if k == main:

            partes = [
                (
                    "Liquidez diária (100% do CDI)",
                    .4,
                ),
                (
                    "RDB de 2 a 5 anos",
                    .35,
                ),
                (
                    "Tesouro IPCA+",
                    .25,
                ),
            ]

            dica = (
                "Objetivo de longo prazo: "
                "mantenha uma parte com liquidez "
                "e deixe o resto trabalhando "
                "por mais tempo."
            )

        else:

            partes = [
                (
                    "Liquidez diária (100% do CDI)",
                    1.0,
                )
            ]

            dica = (
                "Objetivo mais próximo: "
                "o melhor é manter com "
                "resgate imediato."
            )

        linhas = "".join(
            '<div class="al" style="padding:4px 0">'
            '<span class="k">'
            + n
            + " · "
            + str(
                round(
                    p * 100
                )
            )
            + '%</span><b style="font-size:15px">'
            + brl(
                v * p
            )
            + "</b></div>"
            for n, p in partes
        )

        out += card(
            m[1],
            html.escape(
                m[0]
            ),
            brl(v),
            dica,
            linhas,
        )

    sub = (
        "Esse valor pode ir para a sua caixinha "
        "principal e começar a render."
        if ex
        else
        "Seu saldo livre precisa passar de "
        + brl(
            reserva + 1
        )
        + " para sobrar algo além da reserva."
    )

    out += card(
        "blue",
        "Saldo livre acima da reserva",
        brl(ex),
        sub,
    )

    return (
        out
        + '<div class="k" style="padding:0 6px">'
        "As ideias acima são educativas e "
        "não constituem recomendação de investimento."
        "</div>"
    )


def tela_ideias():

    ks = list(
        S["caixas"]
    )

    sig = "|".join(
        sorted(ks)
    )

    if not ks:

        st.markdown(
            card(
                "blue",
                "Ideias sob medida",
                "Sem caixinhas",
                "Crie sua primeira caixinha "
                "para receber ideias.",
            ),
            unsafe_allow_html=True,
        )

        if (
            not SUP
            and st.button(
                "➕ Criar caixinha",
                key="b_ic",
                use_container_width=True,
            )
        ):
            dlg_novo()

        return

    if (
        st.session_state.get(
            "ideias_ok"
        )
        != sig
    ):

        n = len(ks)

        nomes = ", ".join(
            nome_cx(k).replace(
                "Caixinha ",
                "",
            )
            for k in ks
        )

        st.markdown(
            '<div class="card as" style="padding:14px 16px">'
            "🤔 Você tem <b>"
            + str(n)
            + (
                " caixinha"
                if n == 1
                else " caixinhas"
            )
            + "</b> ("
            + html.escape(nomes)
            + "), está correto?"
            "</div>",
            unsafe_allow_html=True,
        )

        with st.container(
            key="conf"
        ):

            a, b = st.columns(
                2
            )

            if a.button(
                "Sim",
                key="ok_s",
                type="primary",
                use_container_width=True,
            ):

                st.session_state.update(
                    ideias_ok=sig,
                    ideias_no=False,
                )

                st.rerun()

            if b.button(
                "Não",
                key="ok_n",
                use_container_width=True,
            ):

                st.session_state[
                    "ideias_no"
                ] = True

        if st.session_state.get(
            "ideias_no"
        ):

            st.caption(
                "Sem problemas! Ajuste suas caixinhas "
                "e volte aqui."
                if not SUP
                else
                "Peça ao titular para ajustar as caixinhas."
            )

            if not SUP:

                with st.container(
                    key="conf2"
                ):

                    c1, c2 = st.columns(
                        2
                    )

                    if c1.button(
                        "➕ Criar",
                        key="b_ic2",
                        use_container_width=True,
                    ):
                        dlg_novo()

                    if c2.button(
                        "🗑️ Excluir",
                        key="b_ie2",
                        use_container_width=True,
                    ):
                        dlg_excluir()

        return

    st.markdown(
        v_idea(),
        unsafe_allow_html=True,
    )

    ex = round(
        max(
            0.0,
            S["livre"]
            - S["cfg"]["reserva"],
        ),
        2,
    )

    if (
        ex >= 1
        and not SUP
        and st.button(
            "🔒 Guardar "
            + brl(ex)
            + " na "
            + nome_cx(ks[0]),
            key="b_ex",
            use_container_width=True,
        )
    ):

        e = aplicar(
            "save",
            ex,
            ks[0],
            "Excedente guardado",
        )

        if e:
            st.error(e)
        else:
            st.rerun()

    if st.button(
        "Revisar minhas caixinhas",
        key="b_rev",
        use_container_width=True,
    ):

        st.session_state[
            "ideias_ok"
        ] = None

        st.rerun()


# ================================================================
# DIÁLOGOS
# ================================================================

@st.dialog("⚙️ Ajustes da conta")
def dlg_ajustes():

    c = S["cfg"]

    tem_sonho = (
        "sonho" in S["caixas"]
        and "futuro" in S["caixas"]
    )

    pal = list(
        PALETAS
    )

    with st.form(
        "f_ajustes"
    ):

        nome = st.text_input(
            "Nome da conta",
            CONTA["nome"],
            max_chars=24,
        )

        paleta = st.selectbox(
            "Cores do app",
            pal,
            index=(
                pal.index(
                    S["paleta"]
                )
                if S.get(
                    "paleta"
                ) in pal
                else 0
            ),
        )

        tutorial = st.checkbox(
            "Mostrar tutorial na tela Início",
            value=c["tutorial"],
        )

        st.caption(
            "🎯 META E RESERVA"
        )

        meta = st.number_input(
            "Meta financeira (R$)",
            min_value=0.0,
            value=float(
                c["meta"]
            ),
            step=1000.0,
            format="%.2f",
        )

        reserva = st.number_input(
            "Reserva fixa protegida no Saldo Livre (R$)",
            min_value=0.0,
            value=float(
                c["reserva"]
            ),
            step=50.0,
            format="%.2f",
        )

        st.caption(
            "💰 BALANÇO MENSAL"
        )

        renda = st.number_input(
            "Renda mensal (R$)",
            min_value=0.0,
            value=float(
                c["renda"]
            ),
            step=50.0,
            format="%.2f",
        )

        gast = st.number_input(
            "Gastos fixos do mês (R$)",
            min_value=0.0,
            value=float(
                c["gastos"]
            ),
            step=10.0,
            format="%.2f",
        )

        guard = st.number_input(
            "Guardar automático na primeira caixinha (R$)",
            min_value=0.0,
            value=float(
                c["guardar"]
            ),
            step=50.0,
            format="%.2f",
        )

        cdi = st.number_input(
            "CDI estimado (% ao ano)",
            min_value=0.0,
            max_value=100.0,
            value=float(
                c["cdi"]
            ),
            step=0.1,
            format="%.2f",
        )

        sd = (
            st.date_input(
                "Liberar a Sonho para a Futuro em (opcional)",
                value=(
                    date.fromisoformat(
                        c["sonho_data"]
                    )
                    if c.get(
                        "sonho_data"
                    )
                    else None
                ),
                format="DD/MM/YYYY",
            )
            if tem_sonho
            else None
        )

        if st.form_submit_button(
            "Salvar",
            type="primary",
            use_container_width=True,
        ):

            CONTA["nome"] = (
                nome.strip()
                or CONTA["nome"]
            )

            S["paleta"] = (
                st.session_state["paleta"]
                if False
                else paleta
            )

            st.session_state[
                "paleta"
            ] = paleta

            S["cfg"].update(
                renda=renda,
                gastos=gast,
                guardar=min(
                    guard,
                    max(
                        0.0,
                        renda - gast,
                    ),
                ),
                cdi=cdi,
                meta=meta,
                reserva=reserva,
                tutorial=tutorial,
                ajustado=True,
            )

            if tem_sonho:

                S["cfg"][
                    "sonho_data"
                ] = (
                    sd.isoformat()
                    if sd
                    else None
                )

            fecha(
                "Ajustes salvos!"
            )

            st.rerun()

    if HAS_CRYPTO:

        st.divider()

        r = FACEID(
            modo="reg",
            chal=st.session_state["chal"],
            user=U,
            tema=st.session_state["tema"],
            key="fid_reg",
            default=None,
        )

        if (
            r
            and r.get("kind") == "reg"
            and r["n"]
            != st.session_state["fid_done"]
        ):

            st.session_state[
                "fid_done"
            ] = r["n"]

            if fid_registrar(
                U,
                r,
            ):

                st.session_state[
                    "msg"
                ] = (
                    "Face ID ativado neste aparelho!"
                )

                st.rerun()

            st.error(
                "Não foi possível validar o Face ID."
            )


def form_op(op):

    cx = None
    cx2 = None

    if op in (
        "save",
        "take",
        "yld",
        "mov",
    ):

        ops = [
            k
            for k in S["caixas"]
            if (
                op == "save"
                or S["caixas"][k] > 0
            )
        ]

        if not ops:

            st.info(
                "Nenhuma caixinha disponível ainda. "
                "Crie uma na aba ➕ Montar Caixinha."
                if op == "save"
                else
                "Nenhuma caixinha com saldo ainda."
            )

            return

        cx = st.selectbox(
            "De"
            if op == "mov"
            else "Caixinha",
            ops,
            key="c_" + op,
            format_func=lambda k:
                nome_cx(k)
                + " · "
                + brl(
                    S["caixas"][k]
                ),
        )

        if op == "mov":

            outras = [
                k
                for k in S["caixas"]
                if k != cx
            ]

            if not outras:

                st.info(
                    "Crie outra caixinha "
                    "para poder mover valores."
                )

                return

            cx2 = st.selectbox(
                "Para",
                outras,
                key="d_mov",
                format_func=nome_cx,
            )

    v = st.number_input(
        "Valor (R$)",
        min_value=0.0,
        value=0.0,
        step=(
            0.10
            if op == "yld"
            else 1.0
        ),
        format="%.2f",
        key="v_" + op,
    )

    if op == "yld" and cx:

        st.caption(
            f"100% do CDI rende cerca de "
            f"{brl(S['caixas'][cx] * ((1 + S['cfg']['cdi'] / 100) ** (1 / 252) - 1))} "
            "por dia útil nessa caixinha."
        )

    obs = st.text_input(
        "Observação (opcional)",
        max_chars=40,
        key="o_" + op,
    )

    if st.button(
        "Confirmar",
        type="primary",
        use_container_width=True,
        key="ok_" + op,
    ):

        e = (
            mover(
                cx,
                cx2,
                v,
                obs.strip(),
            )
            if op == "mov"
            else aplicar(
                op,
                v,
                cx,
                obs.strip(),
            )
        )

        if e:
            st.error(e)
        else:
            st.rerun()


def form_criar_cx():

    st.caption(
        "Crie caixinhas para cada objetivo. "
        "Todas rendem 100% do CDI com resgate imediato."
    )

    nome = st.text_input(
        "Nome do objetivo (ex: Intercâmbio)",
        max_chars=24,
    )

    cor = st.selectbox(
        "Cor",
        [
            "pur",
            "blue",
            "gold",
            "grn",
            "red",
        ],
        format_func={
            "pur": "Roxo",
            "blue": "Azul",
            "gold": "Dourado",
            "grn": "Verde",
            "red": "Vermelho",
        }.get,
    )

    desc = st.text_input(
        "Descrição (opcional)",
        max_chars=40,
    )

    if st.button(
        "Criar caixinha",
        type="primary",
        use_container_width=True,
    ):

        if not nome.strip():

            st.error(
                "Dê um nome para a caixinha."
            )

        else:

            k = (
                chave(nome)
                + "-"
                + secrets.token_hex(2)
            )

            S["caixas"][k] = 0.0

            S["caixas_meta"][k] = [
                nome.strip(),
                cor,
                desc.strip(),
            ]

            fecha(
                "Caixinha criada! "
                "Agora guarde um valor nela em "
                "＋ › Caixinhas."
            )

            st.rerun()


@st.dialog("Novo lançamento")
def dlg_novo():

    t1, t2, t3 = st.tabs(
        [
            "💳 Conta",
            "🐷 Caixinhas",
            "➕ Montar Caixinha",
        ]
    )

    with t1:

        form_op(
            st.radio(
                "Conta",
                [
                    "in",
                    "out",
                ],
                horizontal=True,
                format_func=CURTO.get,
                label_visibility="collapsed",
                key="r1",
            )
        )

    with t2:

        form_op(
            st.radio(
                "Caixinhas",
                [
                    "save",
                    "take",
                    "yld",
                    "mov",
                ],
                horizontal=True,
                format_func=CURTO.get,
                label_visibility="collapsed",
                key="r2",
            )
        )

    with t3:
        form_criar_cx()


@st.dialog("🗑️ Excluir caixinha")
def dlg_excluir():

    ops = list(
        S["caixas"]
    )

    if not ops:

        st.info(
            "Nenhuma caixinha para excluir."
        )

        return

    cx = st.selectbox(
        "Qual caixinha?",
        ops,
        format_func=lambda k:
            nome_cx(k)
            + " · "
            + brl(
                S["caixas"][k]
            ),
    )

    modo = st.radio(
        "O que fazer com o saldo?",
        [
            "Resgatar para o Saldo Livre",
            "Apenas zerar (sai do patrimônio)",
        ],
    )

    if st.button(
        "Excluir caixinha",
        type="primary",
        use_container_width=True,
    ):

        excluir_caixinha(
            cx,
            modo.startswith(
                "Resgatar"
            ),
        )

        st.rerun()


@st.dialog("🛡️ Painel dos pais")
def dlg_pais():

    st.caption(
        "Modo supervisão: somente leitura. "
        "Aqui você pode redefinir os acessos."
    )

    senha = st.text_input(
        "Nova senha do titular (mín. 4)",
        type="password",
    )

    pin = st.text_input(
        "Novo PIN dos pais (4 números)",
        type="password",
        max_chars=4,
    )

    if st.button(
        "Salvar",
        type="primary",
        use_container_width=True,
    ):

        if (
            (
                senha
                and len(senha) < 4
            )
            or
            (
                pin
                and not (
                    pin.isdigit()
                    and len(pin) == 4
                )
            )
        ):

            st.error(
                "Senha com 4+ caracteres "
                "e PIN com exatamente 4 números."
            )

        else:

            if senha:

                CONTA["s"], CONTA["h"] = mk(
                    senha
                )

            if pin:

                CONTA["ps"], CONTA["ph"] = mk(
                    pin
                )

            salvar()

            st.session_state[
                "msg"
            ] = "Acessos atualizados"

            st.rerun()


# ================================================================
# PROCESSOS AUTOMÁTICOS
# ================================================================

if not SUP:

    creditar_mes()

    liberar_sonho()


if st.session_state.get(
    "warn"
):

    st.session_state[
        "msg"
    ] = st.session_state.pop(
        "warn"
    )


if st.session_state["msg"]:

    st.toast(
        st.session_state["msg"]
    )

    st.session_state["msg"] = None


# ================================================================
# TEMA / LOGOUT / NAVEGAÇÃO
# ================================================================

def _tema():

    st.session_state["tema"] = (
        "light"
        if st.session_state["tema"]
        == "dark"
        else "dark"
    )

    db()["contas"][
        st.session_state["u"]
    ]["d"]["tema"] = (
        st.session_state["tema"]
    )

    salvar()


def _sair():

    token = st.query_params.get(
        "s",
        "",
    )

    sessoes().pop(
        _th(token),
        None,
    )

    salvar()

    st.query_params.clear()

    st.session_state.update(
        u=None,
        modo=None,
        tela="login",
        chal=secrets.token_urlsafe(32),
        launch=False,
        nav=False,
        tab=0,
    )


def _nav(v):
    st.session_state["nav"] = v


st.button(
    "☀️"
    if st.session_state["tema"]
    == "dark"
    else "🌙",
    key="b_tema",
    on_click=_tema,
    help="Alternar tema",
)


if not SUP:

    if st.button(
        "⚙️",
        key="b_ajustes_top",
        help="Ajustes da conta",
    ):
        dlg_ajustes()


st.button(
    "🔒",
    key="b_sair",
    on_click=_sair,
    help="Encerrar sessão",
)


# ================================================================
# NAV
# ================================================================

tab = st.session_state["tab"]

if st.session_state["nav"]:

    with st.container(
        key="nav"
    ):

        st.button(
            "‹",
            key="b_min",
            on_click=_nav,
            args=(False,),
            help="Recolher menu",
        )

        aba = st.radio(
            "Atalhos",
            ABAS,
            index=tab,
            key="aba",
            horizontal=True,
            label_visibility="collapsed",
        )

        if st.button(
            "🛡️"
            if SUP
            else "＋",
            key="b_plus",
            help=(
                "Painel dos pais"
                if SUP
                else "Novo lançamento"
            ),
        ):

            (
                dlg_pais
                if SUP
                else dlg_novo
            )()

    idx = ABAS.index(
        aba
    )

else:

    st.button(
        ABAS[tab].split()[0],
        key="bolha",
        on_click=_nav,
        args=(True,),
        help="Abrir menu",
    )

    idx = tab


if idx != tab:

    st.session_state.update(
        dir=(
            "R"
            if idx > tab
            else "L"
        ),
        tab=idx,
    )


# ================================================================
# CABEÇALHO
# ================================================================

st.markdown(
    '<div class="hd">'
    '<div class="k">'
    + TITULOS[idx]
    + " · "
    + hoje_txt()
    + "</div>"
    "<h1>"
    + html.escape(
        CONTA["nome"]
    )
    + "</h1></div>",
    unsafe_allow_html=True,
)


if SUP:

    st.markdown(
        '<div class="sup">'
        "🔐 <b>Modo supervisão:</b> "
        "somente leitura. "
        "Lançamentos e ajustes ficam ocultos."
        "</div>",
        unsafe_allow_html=True,
    )


# ================================================================
# CONTEÚDO
# ================================================================

with st.container(
    key=(
        f"view_{idx}_from"
        + st.session_state["dir"]
    )
):

    # ------------------------------------------------------------
    # INÍCIO
    # ------------------------------------------------------------

    if idx == 0:

        if (
            S["cfg"]["tutorial"]
            and not SUP
        ):

            st.markdown(
                v_tutorial(),
                unsafe_allow_html=True,
            )

            if st.button(
                "Concluir tutorial",
                key="b_tut",
                use_container_width=True,
            ):

                S["cfg"][
                    "tutorial"
                ] = False

                fecha(
                    "Tutorial concluído. "
                    "Você pode reativá-lo em ⚙️ Ajustes."
                )

                st.rerun()

        st.markdown(
            v_home(),
            unsafe_allow_html=True,
        )

        if (
            not SUP
            and S["caixas"]
        ):

            if st.button(
                "🗑️ Excluir caixinha",
                key="b_del",
                use_container_width=True,
            ):

                dlg_excluir()

    # ------------------------------------------------------------
    # EXTRATO
    # ------------------------------------------------------------

    elif idx == 1:

        st.markdown(
            v_ext(),
            unsafe_allow_html=True,
        )

        if S["extrato"]:

            hoje = (
                f"{agora():%Y-%m-%d}"
            )

            x = xlsx_ext()

            with st.container(
                key="dl"
            ):

                c1, c2 = st.columns(
                    2
                )

                if x:

                    c1.download_button(
                        "📊 Excel",
                        x,
                        file_name=(
                            f"extrato_future_{hoje}.xlsx"
                        ),
                        mime=XL,
                        use_container_width=True,
                    )

                c2.download_button(
                    "📄 CSV",
                    csv_ext(),
                    file_name=(
                        f"extrato_future_{hoje}.csv"
                    ),
                    mime="text/csv",
                    use_container_width=True,
                )

    # ------------------------------------------------------------
    # PROJEÇÃO
    # ------------------------------------------------------------

    elif idx == 2:

        topo, resto = v_proj()

        st.markdown(
            topo,
            unsafe_allow_html=True,
        )

        extra = st.slider(
            "E se eu guardasse mais por mês? (R$)",
            0,
            1000,
            0,
            50,
            key="sl_extra",
        )

        if extra:

            meta_extra = mes_meta(
                extra
            )

            st.markdown(
                card(
                    "pur",
                    "Com +"
                    + brl(extra)
                    + " por mês",
                    brl(
                        final_com(
                            extra
                        )
                    ),
                    "Você chegaria à meta em "
                    + fmt_mes(
                        meta_extra
                    )
                    + " (hoje: "
                    + fmt_mes(
                        mes_meta()
                    )
                    + ").",
                ),
                unsafe_allow_html=True,
            )

        st.markdown(
            resto,
            unsafe_allow_html=True,
        )

        hoje = (
            f"{agora():%Y-%m-%d}"
        )

        x = xlsx_proj()

        with st.container(
            key="dl2"
        ):

            c1, c2 = st.columns(
                2
            )

            if x:

                c1.download_button(
                    "📊 Excel",
                    x,
                    file_name=(
                        f"projecao_future_{hoje}.xlsx"
                    ),
                    mime=XL,
                    use_container_width=True,
                )

            else:

                c1.download_button(
                    "📄 CSV",
                    csv_proj(),
                    file_name=(
                        f"projecao_future_{hoje}.csv"
                    ),
                    mime="text/csv",
                    use_container_width=True,
                )

            c2.download_button(
                "📄 PDF",
                pdf_proj(),
                file_name=(
                    f"projecao_future_{hoje}.pdf"
                ),
                mime="application/pdf",
                use_container_width=True,
            )

    # ------------------------------------------------------------
    # IDEIAS
    # ------------------------------------------------------------

    else:

        tela_ideias()


# ================================================================
# ANIMAÇÕES FINAIS
# ================================================================

if st.session_state["fx"]:

    st.markdown(
        fx_html(
            st.session_state["fx"]
        ),
        unsafe_allow_html=True,
    )

    st.session_state[
        "fx"
    ] = None


if st.session_state["launch"]:

    st.markdown(
        '<div class="lift">'
        "<i>🚀</i>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.session_state[
        "launch"
    ] = False