# -*- coding: utf-8 -*-
"""FUTURE - controle financeiro pessoal (Streamlit >= 1.40).

requirements.txt:  streamlit>=1.40   cryptography   openpyxl

NADA sensível fica neste arquivo. Configure em Streamlit Cloud > Settings > Secrets:

    supabase_url = "https://SEU-PROJETO.supabase.co"
    supabase_key = "CHAVE_SERVER_SIDE"         # só nos Secrets, nunca no GitHub
    backup_key   = "texto-longo-e-aleatorio"   # criptografa o backup do aparelho

    # conta inicial (opcional). Sem estes 4 valores nenhuma conta é criada automaticamente:
    seed_user = "joao"
    seed_nome = "João"
    seed_codigo = "..."        # senha de login da conta inicial
    seed_pin = "...."          # PIN dos pais da conta inicial
    # saldos iniciais (opcionais):
    seed_livre = "0"
    seed_caixas_json = '{"futuro": 0}'
    seed_caixas_meta_json = '{"futuro": ["Caixinha Futuro", "pur", "Principal"]}'
    seed_renda = "0"  seed_guardar = "0"  seed_gastos = "0"  seed_meta = "10000"  seed_reserva = "100"

Supabase (SQL Editor). O RLS fica LIGADO e sem policies: só a chave server-side acessa a tabela.

    create table future (id text primary key, dados jsonb not null);
    alter table future enable row level security;

Persistência: Supabase é a fonte da verdade; future_db.json é só cache/fallback.
Cada conta tem versão (_v): vence sempre a mais nova, e uma gravação que encontrar a conta
alterada por outra sessão/aparelho NÃO sobrescreve nada.
"""
import csv, io, json, random, time, html, hmac, hashlib, base64, secrets, threading, urllib.request, unicodedata
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urlparse
import streamlit as st
import streamlit.components.v1 as components

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

st.set_page_config(page_title="FUTURE", page_icon="🚀", layout="centered", initial_sidebar_state="collapsed")


def secret_str(nome, padrao=""):
    """Lê um secret sem quebrar o app quando ele não existe."""
    try:
        v = st.secrets.get(nome, padrao)
        return padrao if v is None else str(v)
    except Exception:
        return padrao


CODIGO, PIN_PAIS = secret_str("seed_codigo"), secret_str("seed_pin")
SEED, SEED_NOME = secret_str("seed_user", "joao"), secret_str("seed_nome", "João")
SB_URL, SB_KEY = secret_str("supabase_url").rstrip("/"), secret_str("supabase_key")
_BACKUP_KEY = secret_str("backup_key")
BK = hashlib.sha256(_BACKUP_KEY.encode()).digest() if _BACKUP_KEY else None    # sem chave = backup desativado
ARQ = Path(__file__).with_name("future_db.json")
XL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SESSAO_SEG = 30 * 86400

TIPOS = {"in": ("📥", "Recebi dinheiro"), "out": ("💸", "Gastei dinheiro"), "save": ("🔒", "Guardar na caixinha"),
         "take": ("🔓", "Resgatar da caixinha"), "yld": ("📈", "Rendimento / juros"), "mov": ("🔁", "Mover entre caixinhas"),
         "del": ("🗑️", "Caixinha excluída")}
CURTO = {"in": "📥 Receber", "out": "💸 Gastar", "save": "🔒 Guardar", "take": "🔓 Resgatar", "yld": "📈 Juros", "mov": "🔁 Mover"}
ABAS, TITULOS = ["🏠 Início", "🧾 Extrato", "📈 Projeção", "💡 Ideias"], ["Início", "Extrato", "Projeção", "Ideias"]
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
PALETAS = {
    "Padrão": {"pur": "#b57bff", "blue": "#4aa3ff", "gold": "#f0c24b", "grn": "#3fdc78", "red": "#ff6b62"},
    "Neon": {"pur": "#ff00ff", "blue": "#00ffff", "gold": "#ffff00", "grn": "#00ff00", "red": "#ff0000"},
    "Oceano": {"pur": "#3a0ca3", "blue": "#4361ee", "gold": "#4cc9f0", "grn": "#2ec4b6", "red": "#e71d36"},
    "Outono": {"pur": "#6a4c93", "blue": "#1982c4", "gold": "#ffca3a", "grn": "#8ac926", "red": "#ff595e"},
}
for _k, _v in dict(u=None, modo=None, tela="login", tema="dark", paleta="Padrão", tab=0, nav=False, dir="R", fx=None, msg=None,
                   chal=secrets.token_urlsafe(32), fid_done=None, bak_done=None, launch=False, db_obj=None, db_ts=0.0,
                   recarregar=False, base_v={}, storage_mode="local", bak_hash=None, bak_payload=None).items():
    st.session_state.setdefault(_k, _v)


# ---------------------------------------------------------------- utilidades
def agora():
    return datetime.now(TZ) if TZ else datetime.now()


def hoje_txt():
    h = agora()
    return f"{DIAS[h.weekday()]}, {h.day} {MESES[h.month - 1]}"


def brl(v):
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if v < 0 else "") + "R$ " + s


def kf(v):
    return f"{v / 1000:.1f}".replace(".", ",") + "k"


def fmt_dt(iso):
    return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M:%S")


def chave(n):
    n = "".join(c for c in unicodedata.normalize("NFD", n) if unicodedata.category(c) != "Mn")
    return " ".join(n.lower().split())


def b64d(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def mk(txt):
    s = secrets.token_bytes(16)
    return s.hex(), hashlib.pbkdf2_hmac("sha256", txt.encode(), s, 150000).hex()


def confere(txt, s, h):
    return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", txt.encode(), bytes.fromhex(s), 150000).hex(), h)


def _th(t):
    return hashlib.sha256((t or "").encode()).hexdigest()


def safe_float(v, padrao=0.0):
    try:
        return float(v)
    except Exception:
        return padrao


def nova_conta(nome, senha, pin, nasc="2014-01-01", seed=False):
    s, h = mk(senha)
    ps, ph = mk(pin)
    a = agora()
    d = {"livre": 0.0, "caixas": {}, "caixas_meta": {}, "extrato": [], "tema": "dark", "paleta": "Padrão", "nasc": nasc,
         "_v": 0.0 if seed else time.time(),       # conta inicial "virgem" (v=0) nunca vence dados reais salvos
         "cfg": {"renda": 0.0, "guardar": 0.0, "gastos": 0.0, "cdi": 9.5, "sonho_data": None, "meta": 10000.0,
                 "reserva": 100.0, "tutorial": not seed, "ajustado": False},
         "ultimo_credito": f"{a.year}-{a.month:02d}"}
    if seed:   # valores vêm dos Secrets; nada financeiro fica no código
        d["livre"] = safe_float(secret_str("seed_livre", "0"))
        try:
            bruto = json.loads(secret_str("seed_caixas_json", "{}"))
        except Exception:
            bruto = {}
        try:
            meta = json.loads(secret_str("seed_caixas_meta_json", "{}"))
        except Exception:
            meta = {}
        meta = meta if isinstance(meta, dict) else {}
        caixas = {str(k): round(safe_float(v), 2) for k, v in bruto.items()} if isinstance(bruto, dict) else {}
        d["caixas"] = caixas
        d["caixas_meta"] = {k: (meta[k] if isinstance(meta.get(k), list) and len(meta[k]) == 3 else [k.title(), "pur", ""]) for k in caixas}
        d["cfg"].update(renda=safe_float(secret_str("seed_renda", "0")), guardar=safe_float(secret_str("seed_guardar", "0")),
                        gastos=safe_float(secret_str("seed_gastos", "0")), meta=safe_float(secret_str("seed_meta", "10000"), 10000.0),
                        reserva=safe_float(secret_str("seed_reserva", "100"), 100.0), tutorial=False)
    return {"nome": nome, "s": s, "h": h, "ps": ps, "ph": ph, "fid": {}, "sess": {}, "d": d}


def supabase_configurado():
    return bool(SB_URL and SB_KEY)


def _sb(metodo, path="", corpo=None):
    if not supabase_configurado():
        raise RuntimeError("Supabase não configurado.")
    h = {"apikey": SB_KEY, "Authorization": "Bearer " + SB_KEY, "Content-Type": "application/json",
         "Prefer": "resolution=merge-duplicates,return=minimal"}
    req = urllib.request.Request(SB_URL + "/rest/v1/future" + path, headers=h, method=metodo,
                                 data=None if corpo is None else json.dumps(corpo, ensure_ascii=False).encode())
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read()


def carregar_local():
    try:
        d = json.loads(ARQ.read_text(encoding="utf-8")) if ARQ.exists() else {}
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def salvar_local(dados):
    """Escrita atômica (arquivo temporário + rename) para não corromper o cache local."""
    tmp = ARQ.with_name(ARQ.name + ".tmp")
    try:
        tmp.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(ARQ)
        return True
    except Exception:
        try:
            tmp.unlink()
        except Exception:
            pass
        return False


def ler_fonte():
    """Fonte da verdade: Supabase (quando configurado), senão o arquivo local. Retorna (leu_ok, dados|None)."""
    if supabase_configurado():
        try:
            r = json.loads(_sb("GET", "?id=eq.db&select=dados"))
            d = r[0].get("dados") if r else None
            return True, (d if isinstance(d, dict) else None)
        except Exception:
            return False, None
    d = carregar_local()
    return True, (d or None)


def _ver(c):
    try:
        return float((c.get("d") or {}).get("_v", 0) or 0)
    except Exception:
        return 0.0


def _merge(a, b):
    """Une dois bancos conta a conta. Vence a conta com versão (_v) maior; em empate vence `a`."""
    out = {"contas": {}}
    for src in (a or {}, b or {}):
        for u, c in (src.get("contas") or {}).items():
            if isinstance(c, dict) and (u not in out["contas"] or _ver(c) > _ver(out["contas"][u])):
                out["contas"][u] = c
    return out


@st.cache_resource
def trava():
    return threading.RLock()


def _gravar(dados, nuvem=True):
    """Grava no cache local (sempre) e na nuvem (só quando a leitura da nuvem funcionou)."""
    ok_l, ok_n = salvar_local(dados), True
    if supabase_configurado() and nuvem:
        try:
            _sb("POST", "", [{"id": "db", "dados": dados}])
        except Exception:
            ok_n = False
    return ok_l, ok_n


def carregar_db():
    """Carrega o banco desta sessão: nuvem + cache local, vencendo sempre a conta mais nova. Nunca apaga nada."""
    ok, fonte = ler_fonte()
    local = carregar_local()
    d = _merge(fonte, local)
    contas = d["contas"]
    for src in (fonte, local):      # migra sessões do formato antigo (top-level) para dentro de cada conta
        for h, r in ((src or {}).get("sessoes") or {}).items():
            if isinstance(r, list) and len(r) >= 3 and r[0] in contas:
                contas[r[0]].setdefault("sess", {}).setdefault(h, r)
    criou = False
    if SEED and CODIGO and PIN_PAIS and SEED not in contas:      # sem Secrets não existe conta inicial
        contas[SEED] = nova_conta(SEED_NOME, CODIGO, PIN_PAIS, seed=True)
        criou = True
    nv = {u: _ver(c) for u, c in ((fonte or {}).get("contas") or {}).items()}
    if criou or (supabase_configurado() and ok and any(_ver(c) > nv.get(u, -1) for u, c in contas.items())):
        _gravar(d, nuvem=ok)        # sincroniza o que só existia no cache local
    st.session_state["storage_mode"] = ("cloud" if ok else "local-fallback") if supabase_configurado() else "local"
    return d


def refrescar_db(force=False):
    """Chamado uma vez no topo de cada execução completa. Cada sessão trabalha na sua própria cópia."""
    ss = st.session_state
    if force or ss.get("recarregar") or ss.get("db_obj") is None or time.time() - ss.get("db_ts", 0) > 8:
        d = carregar_db()
        ss.update(db_obj=d, db_ts=time.time(), recarregar=False, base_v={u: _ver(c) for u, c in d["contas"].items()})


def db():
    return st.session_state["db_obj"]


def salvar(forcar_u=None):
    """
    1) sobe a versão da conta alterada; 2) lê a fonte da verdade; 3) se outra sessão alterou a mesma conta
    nesse meantime, NÃO grava (evita sobrescrever dados novos com antigos); 4) senão mescla e grava
    no cache local e na nuvem. Falha da nuvem nunca apaga dados: o cache local fica à frente e é sincronizado depois.
    Retorna True se gravou.
    """
    ss = st.session_state
    u = forcar_u or ss.get("u")
    dados = db()
    if u in dados["contas"]:
        dados["contas"][u]["d"]["_v"] = max(time.time(), _ver(dados["contas"][u]) + 0.001)
    with trava():
        ok, fonte = ler_fonte()
        if ok and fonte and u:
            rc = (fonte.get("contas") or {}).get(u)
            if rc is not None and _ver(rc) != ss["base_v"].get(u):
                ss["recarregar"] = True
                ss["warn"] = "⚠️ Esses dados foram alterados em outro aparelho. Atualizei a tela; repita a ação."
                return False
        if ok:
            for k, c in _merge(fonte, dados)["contas"].items():
                dados["contas"][k] = c
        ok_l, ok_n = _gravar(dados, nuvem=ok)
        ss["base_v"] = {k: _ver(c) for k, c in dados["contas"].items()}
        if supabase_configurado():
            ss["storage_mode"] = "cloud" if (ok and ok_n) else "local-fallback"
    if not ok_l:
        ss["warn"] = "⚠️ Não consegui gravar o cache local."
    elif supabase_configurado() and not (ok and ok_n):
        ss["warn"] = "☁️ Nuvem indisponível agora. Seus dados estão salvos neste servidor e sincronizam depois."
    return True


# ------------------------------------------------------------------ visual
def get_css(tema, nome):
    p = PALETAS.get(nome, PALETAS["Padrão"])
    if tema == "light":
        p = {k: "color-mix(in srgb," + v + " 70%,#000)" for k, v in p.items()}
    cores = f"--blue:{p['blue']};--pur:{p['pur']};--gold:{p['gold']};--grn:{p['grn']};--red:{p['red']}"
    if tema == "light":
        return ":root{--bg:#eceef4;--c1:#fff;--c2:#f3f4f9;--tx:#14141c;--mu:#656575;--ln:rgba(0,0,0,.09);--s1:rgba(120,125,150,.3);--s2:rgba(255,255,255,.95);--glass:rgba(255,255,255,.68);color-scheme:light;" + cores + "}"
    return ":root{--bg:#07070b;--c1:#16161f;--c2:#0e0e15;--tx:#f4f4f8;--mu:#8b8b9a;--ln:rgba(255,255,255,.09);--s1:rgba(0,0,0,.6);--s2:rgba(255,255,255,.04);--glass:rgba(34,34,48,.58);color-scheme:dark;" + cores + "}"


CSS_BASE = """
html,body,[data-testid="stApp"],[data-testid="stMain"],[data-testid="stMainBlockContainer"]{background:var(--bg)!important;overscroll-behavior-y:none;margin:0;padding:0}
[data-testid="stApp"]{background:radial-gradient(900px 520px at 12% -8%,color-mix(in srgb,var(--pur) 13%,transparent),transparent 62%),radial-gradient(760px 460px at 100% 6%,color-mix(in srgb,var(--blue) 10%,transparent),transparent 60%),var(--bg)!important;background-attachment:fixed!important}
.stApp{color:var(--tx);overflow-x:hidden}
header[data-testid="stHeader"],#MainMenu,footer{display:none!important}
.block-container{max-width:480px!important;padding:1.2rem 1rem 10rem!important;margin:0 auto!important}
.stApp p,.stApp label,.stApp h1,.stApp li,[data-testid="stDialog"] *{color:var(--tx)}
.stApp input,[data-baseweb="select"]>div,[data-baseweb="input"],[data-baseweb="base-input"]{background:var(--c2)!important;color:var(--tx)!important;border-radius:14px!important}
div[role="dialog"]{background:var(--c1)!important;border-radius:28px!important;border:1px solid var(--ln)!important;max-width:calc(100vw - 24px)!important;box-shadow:0 24px 70px rgba(0,0,0,.3),inset 0 1px 0 rgba(255,255,255,.06)!important;animation:dialogIn .28s cubic-bezier(.16,1,.3,1)}
@keyframes dialogIn{from{opacity:0;transform:translateY(10px) scale(.985)}to{opacity:1;transform:none}}
button[kind="secondary"],[data-testid="stBaseButton-secondary"]{background:var(--c2);border:1px solid var(--ln);border-radius:16px}
button[kind="secondary"] p,[data-testid="stBaseButton-secondary"] p{color:var(--tx)}
button[kind="primary"],[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,var(--pur),var(--blue))!important;border:0!important;border-radius:16px!important}
button[kind="primary"] *,[data-testid="stBaseButton-primary"] *{color:#fff!important}
[data-testid="stForm"]{border:0;padding:0;background:transparent}
.st-key-bak{position:fixed;left:0;bottom:0;width:0;height:0;overflow:hidden;opacity:0;pointer-events:none}
.hd h1{margin:0;font-size:26px;letter-spacing:-.03em;padding:0}.hd{margin-bottom:16px}
.rkw{position:relative;display:inline-block}
.rkw::before{content:"";position:absolute;inset:-22px;border-radius:50%;background:radial-gradient(circle,color-mix(in srgb,var(--pur) 28%,transparent),transparent 68%)}
.logo{position:relative;font-size:64px;line-height:1;display:inline-block;animation:rocketLaunch .7s cubic-bezier(.175,.885,.32,1.275) both}
@keyframes rocketLaunch{0%{transform:translateY(80px) scale(.4);opacity:0}60%{transform:translateY(-15px) scale(1.1);opacity:1}100%{transform:none;opacity:1}}

.brand{font-size:34px;font-weight:800;letter-spacing:.14em;text-indent:.14em;line-height:1.1;margin:14px 0 6px;color:var(--tx)}
@supports ((-webkit-background-clip:text) or (background-clip:text)){.brand{background:linear-gradient(135deg,var(--tx) 35%,var(--pur));-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}}
.card{background:linear-gradient(145deg,var(--c1),var(--c2));border:1px solid color-mix(in srgb,var(--c,var(--ln)) 50%,transparent);border-radius:25px;padding:18px;box-shadow:8px 9px 24px var(--s1),-4px -4px 16px var(--s2),inset 0 1px 0 rgba(255,255,255,.05);backdrop-filter:blur(14px) saturate(140%);-webkit-backdrop-filter:blur(14px) saturate(140%);margin-bottom:16px}
button{transition:transform .18s cubic-bezier(.2,.8,.2,1),background .25s ease,box-shadow .25s ease!important}button:active{transform:scale(.97)!important}label{transition:background .25s ease!important}
.k{color:var(--mu);font-size:13px}.lb{font-size:14px;font-weight:600}.big{font-size:34px;font-weight:700;letter-spacing:-.035em;margin:2px 0 8px;font-variant-numeric:tabular-nums}
.pg{height:8px;border-radius:9px;background:var(--ln);overflow:hidden;margin:6px 0}
.pg i{display:block;height:100%;border-radius:9px;background:linear-gradient(90deg,var(--blue),var(--grn));animation:grow 1.4s cubic-bezier(.25,1,.5,1)}
@keyframes grow{from{width:0}}
.rkbar{position:relative;padding-top:14px}
.rkbar s{position:absolute;top:-6px;margin-left:-9px;font-size:17px;text-decoration:none;animation:fly .9s cubic-bezier(.25,1,.5,1) both}
@keyframes fly{from{left:0}}
.as{font-size:15px;border-style:dashed}.sup{background:color-mix(in srgb,var(--gold) 16%,transparent);border:1px solid var(--gold);border-radius:18px;padding:12px 14px;margin-bottom:16px;font-size:14px}
.sp{display:flex;gap:10px;align-items:flex-start;padding:7px 0}.sp>span{font-size:18px;line-height:1.3}.sp.ok b{text-decoration:line-through;opacity:.5}
.tx{display:flex;align-items:center;gap:12px;padding:13px 0;border-bottom:1px solid var(--ln)}.tx:last-child{border:0}.tx .g{flex:1;min-width:0}
.ic{width:40px;height:40px;border-radius:14px;background:var(--c2);display:grid;place-items:center;font-size:19px;flex:none;border:1px solid var(--ln)}
table{width:100%;border-collapse:collapse;font-size:13.5px}th{color:var(--mu);font-weight:500;text-align:right;padding:6px 0}td{padding:10px 0;text-align:right;border-top:1px solid var(--ln)}th:first-child,td:first-child{text-align:left}
.bar{fill:var(--grn);opacity:.9}.bt{fill:var(--mu);font-size:10px;text-anchor:middle}.tl{stroke:var(--gold);stroke-dasharray:4 4;stroke-width:1.2}
.al{display:flex;justify-content:space-between;align-items:baseline}.al b{font-size:20px}
.st-key-nav,.st-key-bolha{position:fixed;left:16px;bottom:calc(66px + env(safe-area-inset-bottom,0px));z-index:999;width:auto!important}
.st-key-nav{width:min(calc(100vw - 32px),420px)!important;display:flex!important;flex-direction:row!important;align-items:center;gap:4px!important;padding:6px;overflow:hidden;background:var(--glass);backdrop-filter:blur(20px) saturate(160%);-webkit-backdrop-filter:blur(20px) saturate(160%);border:1px solid var(--ln);border-radius:34px;box-shadow:0 14px 40px var(--s1),inset 0 1px 0 rgba(255,255,255,.14);animation:stretch .7s cubic-bezier(.16,1,.3,1) forwards}
@keyframes stretch{from{width:58px!important;padding:0;opacity:0}}
.st-key-nav>div{width:auto!important;animation:fi .6s .15s cubic-bezier(.16,1,.3,1) both}@keyframes fi{from{opacity:0;transform:translateX(-16px)}}
.st-key-aba{flex:1!important}
.st-key-nav [role="radiogroup"]{display:flex;flex-wrap:nowrap;gap:2px;width:100%}
.st-key-nav label{flex:1;justify-content:center;margin:0;padding:8px 0;border-radius:26px;cursor:pointer}
.st-key-nav label>div:first-child{display:none}
.st-key-nav label p{font-size:10px;line-height:1.3;font-weight:600;text-align:center;word-spacing:100vw;margin:0;opacity:.55;transition:opacity .3s}
.st-key-nav label p::first-line{font-size:21px}
.st-key-nav label:has(input:checked){background:color-mix(in srgb,var(--pur) 26%,transparent)}
.st-key-nav label:has(input:checked) p{opacity:1}
.st-key-b_min button,.st-key-b_plus button,.st-key-bolha button,.st-key-b_tema button,.st-key-b_ajustes_top button,.st-key-b_sair button{border-radius:50%;padding:0;background:var(--glass);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid var(--ln)}
.st-key-b_min button{width:34px;height:34px}.st-key-b_plus button{width:46px;height:46px;border:0;background:linear-gradient(135deg,var(--pur),var(--blue))}
.st-key-b_plus button p{color:#fff;font-size:24px;line-height:1}
.st-key-bolha{animation:popin .4s cubic-bezier(.2,1.4,.4,1)}.st-key-bolha button{width:58px;height:58px;font-size:24px;box-shadow:0 10px 30px var(--s1)}
@keyframes popin{from{transform:scale(.4);opacity:0}}
.st-key-b_tema,.st-key-b_ajustes_top,.st-key-b_sair{position:fixed;z-index:1000;width:auto!important;top:calc(12px + env(safe-area-inset-top,0px))}
.st-key-b_tema{right:118px}.st-key-b_ajustes_top{right:66px}.st-key-b_sair{right:14px}
.st-key-b_tema button,.st-key-b_ajustes_top button,.st-key-b_sair button{width:44px;height:44px;font-size:18px}
[class*="_fromR"]{animation:slR .6s cubic-bezier(.25,1,.5,1) forwards}[class*="_fromL"]{animation:slL .6s cubic-bezier(.25,1,.5,1) forwards}
@keyframes slR{from{transform:translateX(50px);opacity:0}to{transform:none;opacity:1}}@keyframes slL{from{transform:translateX(-50px);opacity:0}to{transform:none;opacity:1}}
.fx,.lift{position:fixed;inset:0;pointer-events:none;z-index:2000;overflow:hidden}
.fx i{position:absolute;bottom:-50px;font-style:normal;opacity:0;animation:rise 2.4s ease-out forwards}
.fx b{position:absolute;left:50%;top:36%;font-size:36px;color:var(--grn);opacity:0;animation:pop 2.4s ease forwards;text-shadow:0 4px 24px rgba(0,0,0,.35)}
@keyframes rise{0%{transform:translateY(0) scale(.6);opacity:0}15%{opacity:1}100%{transform:translateY(-90vh) rotate(25deg) scale(1.1);opacity:0}}
@keyframes pop{0%{opacity:0;transform:translate(-50%,30px) scale(.7)}20%{opacity:1;transform:translate(-50%,0) scale(1.05)}80%{opacity:1}100%{opacity:0;transform:translate(-50%,-40px)}}
.lift i{position:absolute;left:6%;bottom:-70px;font-size:56px;font-style:normal;filter:drop-shadow(0 0 18px var(--gold));animation:blast 1.4s cubic-bezier(.5,0,.9,.4) forwards}
@keyframes blast{to{transform:translate(78vw,-118vh) scale(.6)}}
html,body,.stApp,.stApp p,.stApp label,.stApp input,.stApp textarea,.stApp button,.stApp [data-baseweb],div[role="dialog"] p{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",system-ui,sans-serif!important}
.big,.hd h1,.al b,.lb,.brand{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Segoe UI",system-ui,sans-serif!important}
.dh{font-size:11.5px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;color:var(--mu);padding:12px 0 2px}.dh:first-child{padding-top:8px}
.mes{display:flex;gap:8px;margin-top:8px}.mes>div{flex:1}.mes b{font-size:16px;font-variant-numeric:tabular-nums}
[class*="st-key-conf"] [data-testid="stHorizontalBlock"],[class*="st-key-dl"] [data-testid="stHorizontalBlock"]{flex-direction:row!important;flex-wrap:nowrap!important;gap:10px!important}
[class*="st-key-conf"] [data-testid="stColumn"],[class*="st-key-dl"] [data-testid="stColumn"],[class*="st-key-conf"] [data-testid="column"],[class*="st-key-dl"] [data-testid="column"]{min-width:0!important;flex:1 1 0!important;width:auto!important}
.bar{transform-box:fill-box;transform-origin:50% 100%;animation:barUp .9s cubic-bezier(.25,1,.5,1) both}
@keyframes barUp{from{transform:scaleY(0)}}
[data-baseweb="popover"],[data-baseweb="popover"]>div,[data-baseweb="menu"],ul[role="listbox"]{background:var(--c1)!important;border-radius:16px!important}
[data-baseweb="popover"] *,ul[role="listbox"] *{color:var(--tx)!important}
li[role="option"]:hover,li[aria-selected="true"]{background:var(--c2)!important}
[data-baseweb="calendar"],[data-baseweb="calendar"] *{background-color:var(--c1)!important;color:var(--tx)!important}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] *{color:var(--mu)!important}
[data-testid="stAlert"]{background:color-mix(in srgb,var(--pur) 12%,var(--c1))!important;border:1px solid var(--ln)!important;border-radius:16px!important}
[data-testid="stAlert"] *,[data-testid="stToast"] *{color:var(--tx)!important}
[data-testid="stToast"]{background:var(--c1)!important;border:1px solid var(--ln)!important;border-radius:16px!important}
[data-testid="stNumberInput"] button,[data-testid="stDownloadButton"] button{background:var(--c2)!important;color:var(--tx)!important;border-color:var(--ln)!important}
[data-testid="stDownloadButton"] button p{color:var(--tx)!important}
button[data-baseweb="tab"] p{color:var(--mu)!important}button[data-baseweb="tab"][aria-selected="true"] p{color:var(--tx)!important}
[data-baseweb="tab-border"]{background:var(--ln)!important}[data-baseweb="tab-highlight"]{background:var(--pur)!important}
hr{border-color:var(--ln)!important}input::placeholder{color:var(--mu)!important;opacity:1}
[data-baseweb="select"] *{color:var(--tx)!important}[data-baseweb="select"] svg{fill:var(--mu)!important}
[data-testid="stSlider"] *,[data-testid="stSliderThumbValue"],[data-testid="stTickBarMin"],[data-testid="stTickBarMax"],[data-testid="stCheckbox"] *{color:var(--tx)!important}
[data-baseweb="slider"] [role="slider"]{background:var(--pur)!important}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}}
"""
st.markdown("<style>" + get_css(st.session_state["tema"], st.session_state["paleta"]) + CSS_BASE + "</style>", unsafe_allow_html=True)

try:
    refrescar_db(force=st.session_state["u"] is None)      # tela de login sempre lê dados frescos
except Exception:
    st.error("Não foi possível carregar os dados. Atualize a página em instantes.")
    st.stop()


# ------------------------------- componentes de navegador (backup + Face ID)
def _componente(nome, html_src):
    d = Path(__file__).with_name("_" + nome)
    try:
        d.mkdir(exist_ok=True)
        (d / "index.html").write_text(html_src, "utf-8")
    except Exception:
        pass
    return components.declare_component(nome, path=str(d))


BAK_HTML = """<!DOCTYPE html><html><body><script>
const P=(t,d)=>parent.postMessage(Object.assign({isStreamlitMessage:true,type:t},d),"*");
let first=true,last="";
addEventListener("message",ev=>{if(ev.data.type!="streamlit:render")return;const A=ev.data.args||{};
let m={};try{m=JSON.parse(localStorage.getItem("future_bak")||"{}")}catch(e){}
if(A.save&&A.save!==last){last=A.save;try{const o=JSON.parse(A.save);m[o.u]=o;localStorage.setItem("future_bak",JSON.stringify(m))}catch(e){}}
if(first){first=false;P("streamlit:setComponentValue",{value:{n:Date.now()+Math.random(),itens:Object.values(m)},dataType:"json"})}
P("streamlit:setFrameHeight",{height:0})});
P("streamlit:componentReady",{apiVersion:1});</script></body></html>"""

FACEID_HTML = """<!DOCTYPE html><html><body style="margin:0;font-family:-apple-system,system-ui,sans-serif"><button id="b"></button><div id="m"></div><script>
const P=(t,d)=>parent.postMessage(Object.assign({isStreamlitMessage:true,type:t},d),"*");
const e64=b=>btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\\+/g,"-").replace(/\\//g,"_").replace(/=+$/,"");
const d64=s=>Uint8Array.from(atob(s.replace(/-/g,"+").replace(/_/g,"/")),c=>c.charCodeAt(0));
const B=document.getElementById("b"),M=document.getElementById("m");let A={};
const done=v=>P("streamlit:setComponentValue",{value:Object.assign({n:Date.now()+Math.random()},v),dataType:"json"});
async function reg(){try{
const c=await navigator.credentials.create({publicKey:{challenge:d64(A.chal),rp:{name:"FUTURE",id:location.hostname},user:{id:new TextEncoder().encode(A.user),name:A.user,displayName:A.user},pubKeyCredParams:[{type:"public-key",alg:-7},{type:"public-key",alg:-257}],authenticatorSelection:{authenticatorAttachment:"platform",userVerification:"required"},timeout:60000}});
const r=c.response,L=JSON.parse(localStorage.getItem("future_auth")||"[]").filter(x=>x.id!=c.id);L.push({id:c.id,user:A.user});localStorage.setItem("future_auth",JSON.stringify(L));
done({kind:"reg",id:c.id,pk:e64(r.getPublicKey()),alg:r.getPublicKeyAlgorithm(),cd:e64(r.clientDataJSON)});
}catch(e){M.textContent="Não foi possível ativar ("+e.name+")"}}
async function get(){try{
const L=JSON.parse(localStorage.getItem("future_auth")||"[]");if(!L.length){M.textContent="Ative o Face ID nos Ajustes depois de entrar.";return}
const c=await navigator.credentials.get({publicKey:{challenge:d64(A.chal),rpId:location.hostname,allowCredentials:L.map(x=>({type:"public-key",id:d64(x.id)})),userVerification:"required",timeout:60000}});
const r=c.response,u=(L.find(x=>x.id==c.id)||{}).user;
done({kind:"get",id:c.id,user:u,ad:e64(r.authenticatorData),cd:e64(r.clientDataJSON),sg:e64(r.signature)});
}catch(e){M.textContent="Face ID cancelado."}}
addEventListener("message",ev=>{if(ev.data.type!="streamlit:render")return;A=ev.data.args;const d=A.tema=="dark";
document.body.style.color=d?"#8b8b9a":"#656575";M.style.cssText="font-size:12px;text-align:center;margin-top:6px";
B.style.cssText="width:100%;padding:14px;border-radius:16px;font-size:16px;font-weight:600;cursor:pointer;border:1px solid "+(d?"rgba(255,255,255,.14)":"rgba(0,0,0,.14)")+";background:"+(d?"#16161f":"#fff")+";color:"+(d?"#f4f4f8":"#14141c");
B.textContent=(A.modo=="reg"?"Ativar Face ID neste aparelho":"Entrar com Face ID");B.onclick=A.modo=="reg"?reg:get;P("streamlit:setFrameHeight",{height:88})});
P("streamlit:componentReady",{apiVersion:1});</script></body></html>"""
BACKUP, FACEID = _componente("bak", BAK_HTML), _componente("faceid", FACEID_HTML)


def _fernet():
    """Backup do aparelho: criptografado e autenticado com a backup_key dos Secrets (sem chave = desativado)."""
    if not (BK and HAS_CRYPTO):
        return None
    from cryptography.fernet import Fernet
    return Fernet(base64.urlsafe_b64encode(BK))


def _payload():
    f, u = _fernet(), st.session_state.get("u")
    if not f or u not in db()["contas"]:
        return None
    corpo = json.dumps(db()["contas"][u], sort_keys=True, ensure_ascii=False)
    h = hashlib.sha256(corpo.encode()).hexdigest()
    if st.session_state.get("bak_hash") != h:      # só gera um novo backup quando algo mudou
        blob = f.encrypt(json.dumps({"u": u, "c": json.loads(corpo)}, ensure_ascii=False).encode()).decode()
        st.session_state.update(bak_hash=h, bak_payload=json.dumps({"u": _th(u), "blob": blob}))
    return st.session_state["bak_payload"]


def restaurar(itens):
    """Restaura contas que o servidor perdeu, só se o backup for MAIS NOVO que o dado atual."""
    f = _fernet()
    if not f:
        return False
    restauradas = []
    for it in itens or []:
        try:
            b = json.loads(f.decrypt(it["blob"].encode()))
            u, c = b["u"], b["c"]
            if not (isinstance(c, dict) and isinstance(c.get("d"), dict) and isinstance(u, str)):
                continue
            atual = db()["contas"].get(u)
            if atual is None or _ver(c) > _ver(atual):
                db()["contas"][u] = c
                restauradas.append(u)
        except Exception:
            continue
    for u in restauradas:
        salvar(u)
    return bool(restauradas)


if _fernet():
    _bk_val = BACKUP(save=_payload(), key="bak", default=None)
    if _bk_val and _bk_val.get("n") != st.session_state["bak_done"]:
        st.session_state["bak_done"] = _bk_val["n"]
        if restaurar(_bk_val.get("itens")):
            st.rerun()


def _cd(p, tipo):
    try:
        cd = json.loads(b64d(p["cd"]))
    except Exception:
        return None
    return cd if cd.get("type") == tipo and cd.get("challenge") == st.session_state["chal"] else None


def fid_registrar(u, p):
    cd = _cd(p, "webauthn.create")
    st.session_state["chal"] = secrets.token_urlsafe(32)
    if cd:
        db()["contas"][u]["fid"][p["id"]] = {"pk": p["pk"], "alg": p["alg"]}
        salvar()
    return bool(cd)


def fid_entrar(p):
    cd = _cd(p, "webauthn.get")
    st.session_state["chal"] = secrets.token_urlsafe(32)
    c = db()["contas"].get(p.get("user") or "")
    cr = c["fid"].get(p.get("id")) if c else None
    if not (cd and cr and HAS_CRYPTO):
        return None
    try:
        ad = b64d(p["ad"])
        host = urlparse(cd["origin"]).hostname or ""
        if ad[:32] != hashlib.sha256(host.encode()).digest() or not (ad[32] & 1 and ad[32] & 4):
            return None
        msg = ad + hashlib.sha256(b64d(p["cd"])).digest()
        pub, sig = serialization.load_der_public_key(b64d(cr["pk"])), b64d(p["sg"])
        if cr["alg"] == -7:
            pub.verify(sig, msg, ec.ECDSA(hashes.SHA256()))
        else:
            pub.verify(sig, msg, padding.PKCS1v15(), hashes.SHA256())
        return p["user"]
    except Exception:
        return None


# ------------------------------------------------------------ login / sessão
def achar_sessao(token):
    th = _th(token)
    for u, c in db()["contas"].items():
        r = (c.get("sess") or {}).get(th)
        if r and time.time() - r[2] < SESSAO_SEG:
            return u, r[1]
    return None


def entrar(u, modo):
    tok = secrets.token_urlsafe(24)
    sess = db()["contas"][u].setdefault("sess", {})
    for h in [h for h, r in sess.items() if time.time() - r[2] >= SESSAO_SEG]:
        sess.pop(h, None)                     # limpa sessões vencidas
    sess[_th(tok)] = [u, modo, time.time()]   # só o hash do token é guardado
    st.query_params["s"] = tok
    salvar(u)
    d = db()["contas"][u]["d"]
    st.session_state.update(u=u, modo=modo, tela="login", launch=True, tema=d.get("tema", "dark"), paleta=d.get("paleta", "Padrão"))
    st.rerun()


def _ir(t):
    st.session_state["tela"] = t


@st.cache_resource
def _tent():
    return {}


def _espera(k):
    t = _tent().get(k)
    e = (t[1] - time.time()) if t else 0
    if e > 0:
        st.error(f"Segurança ativada. Aguarde {int(e) + 1}s para tentar novamente.")
    return e > 0


def _falha(k):
    tt = _tent()
    if len(tt) > 5000:
        tt.clear()
    t = tt.setdefault(k, [0, 0.0])
    t[0] += 1
    if t[0] >= 5:
        t[:] = [0, time.time() + 60]
    st.error("Dados incorretos. Após 5 erros a conta fica bloqueada por 1 minuto.")


def tela_login():
    t = st.session_state["tela"]
    sub = {"login": "INICIAR SESSÃO", "criar": "CRIAR CONTA", "pais": "CONTROLE PARENTAL"}[t]
    st.markdown('<div style="display:flex;flex-direction:column;align-items:center;width:100%;text-align:center;padding:5vh 0 2vh">'
                '<div class="rkw"><div class="logo">🚀</div></div>'
                '<div class="brand">FUTURE</div>'
                '<div style="color:var(--mu);font-size:13px;letter-spacing:.2em;width:100%;text-align:center">' + sub + '</div></div>', unsafe_allow_html=True)
    if t == "login":
        with st.form("f_login"):
            n = st.text_input("Nome", placeholder="Nome da conta", label_visibility="collapsed", max_chars=24)
            p = st.text_input("Senha", type="password", placeholder="Senha", label_visibility="collapsed")
            go = st.form_submit_button("Entrar", type="primary", use_container_width=True)
        if go:
            k = "f:" + chave(n)[:40]
            if not _espera(k):
                c = db()["contas"].get(chave(n))
                if c and confere(p, c["s"], c["h"]):
                    _tent().pop(k, None)
                    entrar(chave(n), "filho")
                else:
                    _falha(k)
        if HAS_CRYPTO:
            r = FACEID(modo="get", chal=st.session_state["chal"], user="", tema=st.session_state["tema"], key="fid_get", default=None)
            if r and r.get("kind") == "get" and r["n"] != st.session_state["fid_done"]:
                st.session_state["fid_done"] = r["n"]
                u = fid_entrar(r)
                if u:
                    entrar(u, "filho")
                st.error("Face ID não reconhecido.")
        st.button("🛡️ Controle parental", key="b_pais", use_container_width=True, on_click=_ir, args=("pais",))
        st.button("Criar nova conta", key="b_criar", use_container_width=True, on_click=_ir, args=("criar",))
        st.caption({"cloud": "☁️ Dados sincronizados na nuvem.", "local-fallback": "⚠️ Nuvem indisponível: usando o cache deste servidor.",
                    "local": "💾 Dados salvos neste servidor."}.get(st.session_state["storage_mode"], ""))
        return
    if t == "criar":
        with st.form("f_criar"):
            n = st.text_input("Nome da conta", max_chars=24)
            p = st.text_input("Senha (mín. 4 caracteres)", type="password")
            pin = st.text_input("PIN dos pais (4 números)", type="password", max_chars=4)
            nasc = st.date_input("Data de nascimento", value=date(2014, 1, 1), min_value=date(1950, 1, 1), max_value=agora().date(), format="DD/MM/YYYY")
            go = st.form_submit_button("Criar conta", type="primary", use_container_width=True)
        if go:
            k = chave(n)
            if not 2 <= len(k) <= 24:
                st.error("Use um nome entre 2 e 24 caracteres.")
            elif k in db()["contas"]:
                st.error("Esse nome já existe.")
            elif len(p) < 4:
                st.error("A senha precisa de no mínimo 4 caracteres.")
            elif not (pin.isdigit() and len(pin) == 4):
                st.error("O PIN dos pais precisa ter exatamente 4 números.")
            else:
                db()["contas"][k] = nova_conta(n.strip(), p, pin, nasc=nasc.isoformat())
                if salvar(k):
                    entrar(k, "filho")
                db()["contas"].pop(k, None)      # nome tomado por outra sessão no mesmo instante
                st.error("Esse nome acabou de ser usado. Escolha outro.")
    else:
        with st.form("f_pais"):
            n = st.text_input("Nome da conta supervisionada", max_chars=24)
            pin = st.text_input("PIN dos pais", type="password", max_chars=4)
            go = st.form_submit_button("Entrar em supervisão", type="primary", use_container_width=True)
        if go:
            k = "p:" + chave(n)[:40]
            if not _espera(k):
                c = db()["contas"].get(chave(n))
                if c and confere(pin, c["ps"], c["ph"]):
                    _tent().pop(k, None)
                    entrar(chave(n), "pais")
                else:
                    _falha(k)
    st.button("← Voltar", key="b_volta", use_container_width=True, on_click=_ir, args=("login",))


if not st.session_state["u"]:
    _r = achar_sessao(st.query_params.get("s", ""))        # lembra a sessão (30 dias)
    if _r:
        _d = db()["contas"][_r[0]]["d"]
        st.session_state.update(u=_r[0], modo=_r[1], tema=_d.get("tema", "dark"), paleta=_d.get("paleta", "Padrão"))
        st.rerun()
if not st.session_state["u"]:
    tela_login()
    st.stop()

U, SUP = st.session_state["u"], st.session_state["modo"] == "pais"
CONTA = db()["contas"][U]
S = CONTA["d"]
S.setdefault("caixas", {})
S.setdefault("caixas_meta", {})
for _k, _v in dict(meta=62000.0, reserva=100.0, tutorial=False, ajustado=True, cdi=9.5, gastos=0.0, renda=0.0, guardar=0.0).items():
    S["cfg"].setdefault(_k, _v)
for _k, _t in (("futuro", ["Caixinha Futuro", "pur", "Principal · rende 100% do CDI"]), ("sonho", ["Caixinha Sonho", "gold", "Rende 100% do CDI · resgate imediato"])):
    if _k in S["caixas"]:
        S["caixas_meta"].setdefault(_k, _t)


# ------------------------------------------------------------ regras de negócio
def total():
    return round(S["livre"] + sum(S["caixas"].values()), 2)


def idade_info():
    try:
        n = date.fromisoformat(S.get("nasc", "2014-01-01"))
    except Exception:
        n = date(2014, 1, 1)
    h = agora().date()
    idade = h.year - n.year - ((h.month, h.day) < (n.month, n.day))
    try:
        b18 = n.replace(year=n.year + 18)
    except ValueError:
        b18 = date(n.year + 18, 3, 1)
    meses = 0 if h >= b18 else max(1, (b18.year - h.year) * 12 + b18.month - h.month - (1 if b18.day < h.day else 0))
    return idade, b18, meses


def prazo_txt(m):
    a, mm = divmod(m, 12)
    p = ([f"{a} ano" + ("s" if a > 1 else "")] if a else []) + ([f"{mm} " + ("mês" if mm == 1 else "meses")] if mm else [])
    return " e ".join(p) or "menos de 1 mês"


def reg(t, v, cx, obs, ts=None, dest=None):
    M = S["caixas_meta"]
    S["extrato"].append({"t": t, "v": round(v, 2), "c": cx, "d": dest, "o": obs, "ts": (ts or agora()).isoformat(),
                         "cn": M.get(cx, [None])[0] if cx else None, "dn": M.get(dest, [None])[0] if dest else None})


def fx(valor):
    st.session_state["fx"] = {"txt": "+" + brl(valor), "n": int(time.time() * 1000)}


def fecha(msg=None):
    S["livre"] = round(S["livre"], 2)
    for k in S["caixas"]:
        S["caixas"][k] = round(S["caixas"][k], 2)
    st.session_state["msg"] = msg or "Lançado em " + fmt_dt(S["extrato"][-1]["ts"])
    salvar()


def visivel(k):
    """Caixinha zerada some da tela, exceto se acabou de ser criada (nunca foi usada)."""
    return S["caixas"][k] > 0.004 or not any(x.get("c") == k or x.get("d") == k for x in S["extrato"])


def nome_cx(k):
    return S["caixas_meta"].get(k, ["Caixinha"])[0]


def aplicar(t, v, cx=None, obs=""):
    v, reserva, cxs = round(safe_float(v), 2), safe_float(S["cfg"]["reserva"]), S["caixas"]
    if v <= 0:
        return "Informe um valor maior que zero."
    if t in ("save", "take", "yld") and cx not in cxs:       # valida tudo ANTES de alterar qualquer saldo
        return "Escolha uma caixinha válida."
    if t == "save":
        if S["livre"] - v < reserva - 1e-9:
            return f"A reserva fixa de {brl(reserva)} está protegida. Você pode guardar até {brl(max(0, S['livre'] - reserva))}."
        S["livre"] -= v
        cxs[cx] += v
    elif t == "take":
        if v > cxs[cx] + 1e-9:
            return f"Essa caixinha tem só {brl(cxs[cx])}."
        cxs[cx] -= v
        S["livre"] += v
    elif t == "yld":
        if cxs[cx] <= 0:
            return "Essa caixinha não tem saldo para render."
        cxs[cx] += v
    elif t == "out":
        if v > S["livre"] + 1e-9:
            return f"Saldo livre insuficiente ({brl(S['livre'])})."
        S["livre"] -= v
    elif t == "in":
        S["livre"] += v
    else:
        return "Tipo de lançamento inválido."
    reg(t, v, cx if t in ("save", "take", "yld") else None, obs)
    if t in ("in", "yld"):
        fx(v)
    fecha()
    return ""


def mover(o, d, v, obs=""):
    v = round(safe_float(v), 2)
    if v <= 0:
        return "Informe um valor maior que zero."
    if o not in S["caixas"] or d not in S["caixas"] or o == d:
        return "Escolha duas caixinhas diferentes."
    if v > S["caixas"][o] + 1e-9:
        return f"{nome_cx(o)} tem só {brl(S['caixas'][o])}."
    S["caixas"][o] -= v
    S["caixas"][d] += v
    reg("mov", v, o, obs, dest=d)
    fecha()
    return ""


def excluir_caixinha(cx, resgatar):
    v, nome = S["caixas"][cx], nome_cx(cx)
    if resgatar:
        S["livre"] += v
        reg("take", v, cx, "Resgate por exclusão")
    else:
        reg("del", v, cx, "Saldo removido do patrimônio")
    S["caixas"].pop(cx, None)
    S["caixas_meta"].pop(cx, None)
    fecha(f"{nome} excluída")


def liberar_sonho():
    sd = S["cfg"].get("sonho_data")
    if sd and agora().date().isoformat() >= sd:
        if "sonho" in S["caixas"] and "futuro" in S["caixas"] and S["caixas"]["sonho"] > 0.004:
            mover("sonho", "futuro", S["caixas"]["sonho"], "Sonho liberada → Futuro")
        S["cfg"]["sonho_data"] = None
        salvar()


def creditar_mes():
    """
    Todo dia 1: entra a renda, saem os gastos fixos e parte vai para a primeira caixinha.
    O saldo livre NUNCA fica negativo: sem saldo, o gasto é lançado só até o que existe (e isso aparece no extrato).
    Meses sem nada configurado só avançam a data, sem lançamentos.
    """
    h, c = agora(), S["cfg"]
    try:
        a, m = S["ultimo_credito"].split("-")
        ult = int(a) * 12 + int(m) - 1
    except Exception:
        ult = h.year * 12 + h.month - 2
    atual = h.year * 12 + h.month - 1
    if atual <= ult:
        return
    renda, gastos, guardar = (max(0.0, safe_float(c[k])) for k in ("renda", "gastos", "guardar"))
    cx, n = next(iter(S["caixas"]), None), 0
    if renda > 0 or gastos > 0:
        for k in range(ult + 1, atual + 1):
            ano, mes = divmod(k, 12)
            ts = datetime(ano, mes + 1, 1, 0, 0, 0, tzinfo=TZ)
            if renda > 0:
                S["livre"] += renda
                reg("in", renda, None, "Renda mensal programada", ts)
            gasto = min(gastos, max(0.0, S["livre"]))
            if gasto > 0:
                S["livre"] -= gasto
                reg("out", gasto, None, "Gastos fixos do mês" + ("" if gasto >= gastos - 1e-9 else " (parcial: saldo insuficiente)"), ts)
            aporte = min(guardar, max(0.0, renda - gasto), max(0.0, S["livre"])) if cx else 0.0
            if aporte > 0:
                S["livre"] -= aporte
                S["caixas"][cx] += aporte
                reg("save", aporte, cx, "Aporte automático mensal", ts)
            n += 1
    S["ultimo_credito"] = f"{h.year}-{h.month:02d}"
    if n:
        if renda > 0:
            fx(renda)
        fecha("Entradas e saídas do mês lançadas automaticamente.")
    else:
        salvar()


def _passos(extra=0.0, limite_meses=None):
    """Simula mês a mês, sempre a 100% do CDI. O guardado automático vai para a caixinha principal; o resto, para o saldo livre."""
    c, h = S["cfg"], agora()
    r = (1 + max(0.0, safe_float(c["cdi"])) / 100) ** (1 / 12) - 1
    cx = {k: max(0.0, safe_float(v)) for k, v in S["caixas"].items()}
    lv, ap, main = max(0.0, safe_float(S["livre"])), total(), next(iter(S["caixas"]), None)
    renda, gastos, guard, extra = (max(0.0, safe_float(c["renda"])), max(0.0, safe_float(c["gastos"])),
                                   max(0.0, safe_float(c["guardar"])), safe_float(extra))
    net = renda - gastos + extra
    g = (min(guard, max(0.0, renda - gastos)) + extra) if main else 0.0
    ano, mes, passos = h.year, h.month, 0
    while limite_meses is None or passos < limite_meses:
        mes += 1
        if mes > 12:
            mes, ano = 1, ano + 1
        lv = max(0.0, lv * (1 + r) + net - g)
        for k in cx:
            cx[k] *= 1 + r
        if main:
            cx[main] += g
        ap += net
        passos += 1
        yield ano, mes, lv + sum(cx.values()), ap, lv, dict(cx)


def _limite():
    """Meses da simulação: até a data EXATA dos 18 anos; depois dos 18, uma janela de 10 anos."""
    meses = idade_info()[2]
    return meses if meses > 0 else 120


def periodo_txt():
    h, (idade, b18, meses) = agora().date(), idade_info()
    fim = b18 if meses > 0 else date(h.year + 10, h.month, min(h.day, 28))
    return f"Período considerado: {h:%d/%m/%Y} até {fim:%d/%m/%Y}" + (" (aniversário de 18 anos)" if meses > 0 else " (próximos 10 anos)")


def projetar():
    h = agora()
    limite, meses = _limite(), idade_info()[2]
    por_ano, ult, estado = {}, None, (total(), total(), S["livre"], dict(S["caixas"]))
    for ano, mes, b, ap, lv, cx in _passos(limite_meses=limite):
        estado, ult = (b, ap, lv, cx), (ano, mes)
        if mes == 12:
            por_ano[ano] = estado
    linhas = [(a, v[1], v[0] - v[1], v[0]) for a, v in sorted(por_ano.items())]
    ano_fim = ult[0] if ult else h.year
    rotulo = "18 anos" if meses > 0 else ano_fim
    if ult and ult[1] == 12 and linhas and linhas[-1][0] == ult[0]:
        linhas[-1] = (rotulo,) + linhas[-1][1:]
    else:
        linhas.append((rotulo, estado[1], estado[0] - estado[1], estado[0]))
    r = (1 + max(0.0, safe_float(S["cfg"]["cdi"])) / 100) ** (1 / 12) - 1
    meta, g = S["cfg"]["meta"], (1 + r) ** limite
    falta = max(0.0, (meta - total() * g) / ((g - 1) / r)) if r > 0 else max(0.0, (meta - total()) / limite)
    return linhas, falta, ano_fim, meta, estado[2:]


def final_com(extra):
    ult = total()
    for ano, mes, b, *_ in _passos(extra, limite_meses=_limite()):
        ult = b
    return ult


def mes_meta(extra=0.0):
    h, meta = agora(), S["cfg"]["meta"]
    if total() >= meta:
        return h.year, h.month
    for ano, mes, b, *_ in _passos(extra, limite_meses=_limite()):
        if b >= meta:
            return ano, mes
    return None


def fmt_mes(t):
    return f"{MESES[t[1] - 1]}/{t[0]}" if t else "fora do período projetado"


def destino(x):
    s = x.get("cn") or (nome_cx(x["c"]) if x.get("c") else "")
    d = x.get("dn") or (nome_cx(x["d"]) if x.get("d") else "")
    return s + (" → " + d if d else "")


# ------------------------------------------------------------------ downloads
def _csv(cab, linhas):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(cab)
    w.writerows(linhas)
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def _xlsx(titulo, cab, linhas, fmts, larg, notas=(), grafico=False):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.chart import BarChart, Reference
        from openpyxl.utils import get_column_letter as col
    except Exception:
        return None
    wb = Workbook()
    ws = wb.active
    ws.title = titulo
    ws.sheet_view.showGridLines = False
    ws["A1"] = "🚀 FUTURE · " + titulo
    ws["A1"].font = Font(bold=True, size=16, color="5B2BE0")
    ws["A2"] = f"{CONTA['nome']} · gerado em {agora():%d/%m/%Y às %H:%M}"
    ws["A2"].font = Font(size=10, color="888888")
    for j, c in enumerate(cab, 1):
        x = ws.cell(4, j, c)
        x.font, x.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="5B2BE0")
        x.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[col(j)].width = larg[j - 1]
    ws.row_dimensions[4].height = 24
    for i, lin in enumerate(linhas, 1):
        for j, v in enumerate(lin, 1):
            x = ws.cell(4 + i, j, v)
            if isinstance(v, str) and v[:1] in ("=", "+", "-", "@"):
                x.data_type = "s"      # texto do usuário nunca vira fórmula no Excel
            if fmts[j - 1]:
                x.number_format = fmts[j - 1]
            if i % 2 == 0:
                x.fill = PatternFill("solid", fgColor="F3EEFF")
    ws.freeze_panes = "A5"
    n = len(linhas) + 6
    for k, (a, v, f) in enumerate(notas):
        ws.cell(n + k, 1, a).font = Font(bold=True)
        x = ws.cell(n + k, 2, v)
        if f:
            x.number_format = f
    if grafico and linhas:
        ch = BarChart()
        ch.title, ch.height, ch.width, ch.legend = "Patrimônio projetado", 8, 16, None
        ch.add_data(Reference(ws, min_col=4, min_row=4, max_row=4 + len(linhas)), titles_from_data=True)
        ch.set_categories(Reference(ws, min_col=1, min_row=5, max_row=4 + len(linhas)))
        ws.add_chart(ch, col(len(cab) + 2) + "4")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


MOEDA = '"R$" #,##0.00;[Red]-"R$" #,##0.00'


def proj_dados():
    L, _, _, meta, _ = projetar()
    return [(a, p, j, b, b / meta if meta > 0 else 0) for a, p, j, b in L]


def xlsx_proj():
    c = S["cfg"]
    return _xlsx("Projeção", ["Ano", "Capital investido", "Juros acumulados", "Patrimônio total", "% da meta"], proj_dados(),
                 [None, MOEDA, MOEDA, MOEDA, "0.0%"], [10, 22, 22, 22, 14],
                 [("Meta (R$)", c["meta"], MOEDA), ("Ponto de partida (R$)", total(), MOEDA), ("Aporte líquido mensal (R$)", max(0.0, c["renda"] - c["gastos"]), MOEDA),
                  ("CDI estimado (% a.a.)", c["cdi"], None)], True)


def csv_proj():
    m = lambda v: f"{v:.2f}".replace(".", ",")
    return _csv(["Ano", "Capital investido (R$)", "Juros acumulados (R$)", "Patrimônio total (R$)", "% da meta"],
                [(a, m(p), m(j), m(b), f"{q * 100:.1f}".replace(".", ",") + "%") for a, p, j, b, q in proj_dados()])


def _extrato_linhas():
    out = []
    for x in sorted(S["extrato"], key=lambda e: e["ts"], reverse=True):
        v = x["v"] if x["t"] in ("in", "yld") else -x["v"] if x["t"] in ("out", "del") else x["v"]
        out.append((datetime.fromisoformat(x["ts"]).replace(tzinfo=None), TIPOS[x["t"]][1], destino(x), x["o"], v))
    return out


def xlsx_ext():
    return _xlsx("Extrato", ["Data e hora", "Tipo", "Caixinha", "Observação", "Valor (R$)"], _extrato_linhas(),
                 ["dd/mm/yyyy hh:mm", None, None, None, MOEDA], [20, 26, 34, 32, 18], [("Patrimônio atual (R$)", total(), MOEDA)])


def csv_ext():
    return _csv(["Data", "Hora", "Tipo", "Caixinha", "Valor (R$)", "Observação"],
                [(d.strftime("%d/%m/%Y"), d.strftime("%H:%M:%S"), t, c, f"{v:.2f}".replace(".", ","), ("'" + o if o[:1] in "=+-@" and o else o))
                 for d, t, c, o, v in _extrato_linhas()])


_W = {**{str(i): 556 for i in range(10)}, ",": 278, ".": 278, " ": 278, "R": 722, "$": 556, "%": 889, "-": 333, "/": 278, "|": 260, "k": 500}


class _Pdf:
    def __init__(self):
        self.o = []

    @staticmethod
    def _c(c):
        return "%.3f %.3f %.3f" % c

    def rect(self, x, y, w, h, c):
        self.o.append("%s rg %.1f %.1f %.1f %.1f re f" % (self._c(c), x, y, w, h))

    def line(self, x1, y1, x2, y2, c, lw=1.0, dash=False):
        self.o.append("%s RG %.1f w %s %.1f %.1f m %.1f %.1f l S [] 0 d" % (self._c(c), lw, "[4 3] 0 d" if dash else "", x1, y1, x2, y2))

    def txt(self, x, y, t, sz=10, c=(0.1, 0.1, 0.15), bold=False, al="l"):
        wd = sum(_W.get(ch, 520) for ch in t) * sz / 1000
        x = x - wd if al == "r" else x - wd / 2 if al == "c" else x
        e = t.encode("cp1252", "replace").decode("latin-1").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        self.o.append("BT /F%d %g Tf %s rg %.1f %.1f Td (%s) Tj ET" % (2 if bold else 1, sz, self._c(c), x, y, e))

    def pdf(self):
        ct = "\n".join(self.o).encode("latin-1")
        objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>",
                b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
                b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
                b"<< /Length %d >>\nstream\n" % len(ct) + ct + b"\nendstream"]
        out, offs = b"%PDF-1.4\n", []
        for i, o in enumerate(objs, 1):
            offs.append(len(out))
            out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
        x = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
        return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, x)


def pdf_proj():
    L, falta, ano_fim, meta, (lv, cxf) = projetar()
    fim, c, P = L[-1][3], S["cfg"], _Pdf()
    roxo, cinza, claro, ouro = (0.43, 0.25, 0.88), (0.45, 0.43, 0.55), (0.95, 0.93, 0.99), (0.84, 0.61, 0.0)
    P.rect(0, 722, 595, 120, roxo)
    P.txt(40, 805, "FUTURE  |  Projeção financeira", 10, (1, 1, 1), True)
    P.txt(40, 790, f"{CONTA['nome']}  ·  gerado em {agora():%d/%m/%Y}", 9, (0.9, 0.85, 1))
    P.txt(40, 752, brl(fim), 34, (1, 1, 1), True)
    P.txt(40, 735, f"Projeção para {ano_fim}  ·  meta de {brl(meta)}" + (" alcançada" if fim >= meta else f"  ·  faltam {brl(meta - fim)}"), 10, (1, 1, 1))
    P.txt(40, 700, f"Hoje: {brl(total())}   |   Aporte líquido: {brl(max(0.0, c['renda'] - c['gastos']))}/mês   |   100% do CDI (cerca de {str(c['cdi']).replace('.', ',')}% a.a.)", 9, cinza)
    P.txt(40, 686, periodo_txt(), 8.5, cinza)
    P.txt(40, 664, "Evolução do patrimônio", 11, bold=True)
    mx, slot, base = (max([meta] + [x[3] for x in L]) * 1.1) or 1, 515 / len(L), 470
    for i, (a, ap, j, b) in enumerate(L):
        h, x = b / mx * 165, 40 + i * slot + slot * .19
        P.rect(x, base, slot * .62, max(h, 0.5), roxo)
        P.txt(x + slot * .31, base + h + 4, kf(b), 8, cinza, al="c")
        P.txt(x + slot * .31, base - 12, str(a), 8, cinza, al="c")
    ym = base + meta / mx * 165
    P.line(40, ym, 555, ym, ouro, 1, True)
    P.txt(40, ym + 4, "Meta " + kf(meta), 8, ouro, True)
    y = 438
    P.txt(40, y, "Ano", 9, cinza, True)
    for xr, t in ((215, "Investido"), (335, "Juros"), (455, "Total"), (555, "% da meta")):
        P.txt(xr, y, t, 9, cinza, True, "r")
    y -= 8
    for i, (a, ap, j, b) in enumerate(L):
        y -= 17
        if i % 2 == 0:
            P.rect(34, y - 4, 527, 17, claro)
        P.txt(40, y, str(a), 9.5)
        P.txt(215, y, brl(ap), 9.5, al="r")
        P.txt(335, y, brl(j), 9.5, (0.07, 0.52, 0.25), al="r")
        P.txt(455, y, brl(b), 9.5, bold=True, al="r")
        P.txt(555, y, f"{b / meta * 100:.0f}%" if meta else "-", 9.5, al="r")
    y -= 30
    if y > 110:
        P.txt(40, y, f"Onde seu dinheiro estará em {ano_fim}", 11, bold=True)
        itens = [("Saldo livre", S["livre"], lv)] + [(nome_cx(k), S["caixas"][k], cxf.get(k, 0.0)) for k in S["caixas"]]
        for nm, hoje, fut in itens[:5]:
            y -= 16
            if y < 60:
                break
            P.txt(40, y, nm, 9.5)
            P.txt(555, y, f"{brl(hoje)} hoje  >  {brl(fut)}", 9.5, al="r")
    P.txt(40, 36, "Simulação educativa: rendimento de 100% do CDI estimado, bruto e sem impostos. Não é recomendação de investimento.", 7.5, cinza)
    return P.pdf()


# ------------------------------------------------------------------ telas
def fx_html(d):
    random.seed(d["n"])
    itens = "".join('<i style="left:%d%%;font-size:%dpx;animation-delay:%.2fs;animation-duration:%.2fs">%s</i>'
                    % (random.randint(4, 90), random.randint(22, 38), random.random() * .9, 1.8 + random.random() * 1.2,
                       random.choice(["💵", "💸", "🪙", "💰"])) for _ in range(16))
    return '<div class="fx">' + itens + '<b>' + d["txt"] + '</b></div>'


def card(cor, tit, val, sub="", extra=""):
    return ('<div class="card" style="--c:var(--' + cor + ')"><div class="lb" style="color:var(--' + cor + ')">' + tit + '</div>'
            '<div class="big">' + val + '</div>' + extra + '<div class="k">' + sub + '</div></div>')


def passos():
    c = S["cfg"]
    p = [("Definir sua meta e reserva", "Toque em ⚙️ no topo da tela", c["ajustado"]),
         ("Cadastrar renda e gastos do mês", "⚙️ › Balanço mensal (cai todo dia 1)", c["renda"] > 0),
         ("Criar sua primeira caixinha", "＋ › Montar Caixinha", bool(S["caixas"])),
         ("Fazer seu primeiro lançamento", "＋ › Conta ou Caixinhas", bool(S["extrato"]))]
    if HAS_CRYPTO:
        p.append(("Ativar o Face ID", "⚙️ › Ativar Face ID neste aparelho", bool(CONTA.get("fid"))))
    return p


def v_tutorial():
    idade, b18, meses = idade_info()
    ps = passos()
    feitos = sum(1 for p in ps if p[2])
    frase = (f"Faltam <b>{prazo_txt(meses)}</b> para os 18 anos. Cada mês conta!" if meses > 0
             else f"Você já tem {idade} anos, então a projeção olha 10 anos à frente.")
    lis = "".join('<div class="sp' + (" ok" if f else "") + '"><span>' + ("✅" if f else "⭕") + '</span><div><b>' + a + '</b><div class="k">' + b + '</div></div></div>' for a, b, f in ps)
    tit = "🎉 Tudo pronto!" if feitos == len(ps) else "👋 Vamos começar, " + html.escape(CONTA["nome"]) + "?"
    return ('<div class="card as" style="border-color:var(--pur)"><div class="lb" style="color:var(--pur);font-size:16px">' + tit + '</div>'
            '<div class="k" style="margin:4px 0 8px">' + frase + '</div><div class="pg"><i style="width:' + str(feitos / len(ps) * 100) + '%"></i></div>'
            '<div class="k">' + str(feitos) + ' de ' + str(len(ps)) + ' passos</div><div style="margin-top:8px">' + lis + '</div></div>')


def v_home():
    t, f, c = total(), S["livre"], S["cfg"]
    _, _, ano_fim, meta, _ = projetar()
    idade, b18, meses = idade_info()
    reserva = c["reserva"]
    pc = min(100, t / meta * 100) if meta > 0 else 0
    if f > reserva + .005:
        msg = "Você tem <b>" + brl(f - reserva) + "</b> acima da reserva fixa. Veja onde aplicar na aba Ideias."
    elif f < reserva - .005:
        msg = "Atenção: faltam <b>" + brl(reserva - f) + "</b> para completar a sua reserva fixa."
    else:
        msg = "Sua reserva fixa está completa. Tudo em ordem."
    h = agora()
    prox = f"01/{h.month + 1:02d}/{h.year}" if h.month < 12 else f"01/01/{h.year + 1}"
    mesada = ("<br>Próxima entrada automática: " + prox) if (c["renda"] > 0 or c["gastos"] > 0) else "<br>Configure renda e gastos em ⚙️."
    pct = f"{pc:.1f}".replace(".", ",")
    prazo = f"faltam {prazo_txt(meses)} para os 18 anos" if meses > 0 else f"projeção até {ano_fim}"
    out = card("grn", "Patrimônio total", brl(t), f"{pct}% da meta de {brl(meta)} · {prazo}",
               '<div class="rkbar"><div class="pg"><i style="width:' + str(pc) + '%"></i></div><s style="left:' + str(max(pc, 2)) + '%">🚀</s></div>')
    out += '<div class="card as">💡 ' + msg + '</div>'
    out += card("blue", "Saldo livre", brl(f), "Reserva fixa: " + brl(reserva) + mesada)
    out += v_mes()
    for k, v in S["caixas"].items():
        if visivel(k):
            m = S["caixas_meta"].get(k, ["Caixinha", "blue", ""])
            out += card(m[1], html.escape(m[0]), brl(v), html.escape(m[2]) or "Faça o primeiro aporte em ＋ › Caixinhas")
    return out


def v_mes():
    h = agora()
    pre = f"{h.year}-{h.month:02d}"
    e = sd = r = 0.0
    for x in S["extrato"]:
        if x["ts"][:7] == pre:
            if x["t"] == "in":
                e += x["v"]
            elif x["t"] == "out":
                sd += x["v"]
            elif x["t"] == "yld":
                r += x["v"]
    rend = sum(S["caixas"].values()) * ((1 + S["cfg"]["cdi"] / 100) ** (1 / 252) - 1)
    cel = lambda t, v, cor: '<div><div class="k">' + t + '</div><b style="color:var(--' + cor + ')">' + brl(v) + '</b></div>'
    nota = f"Suas caixinhas rendem cerca de {brl(rend)} por dia útil (100% do CDI)." if rend >= 0.005 else "Guarde um valor em uma caixinha para começar a render."
    return ('<div class="card"><div class="lb">Este mês · ' + MESES[h.month - 1] + '/' + str(h.year) + '</div><div class="mes">'
            + cel("Entrou", e, "grn") + cel("Saiu", sd, "red") + cel("Rendeu", r, "pur") + '</div><div class="k" style="margin-top:10px">' + nota + '</div></div>')


def dia_rotulo(iso):
    d, h = datetime.fromisoformat(iso).date(), agora().date()
    if d == h:
        return "Hoje"
    if (h - d).days == 1:
        return "Ontem"
    return f"{DIAS[d.weekday()]}, {d.day} {MESES[d.month - 1]}" + (f" {d.year}" if d.year != h.year else "")


def v_ext():
    if not S["extrato"]:
        return '<div class="card"><div class="k">🌱 Nenhum lançamento ainda. Toque em ＋ para começar.</div></div>'
    rows, ult = "", None
    for _, x in sorted(enumerate(S["extrato"]), key=lambda p: (p[1]["ts"], p[0]), reverse=True):
        dia = dia_rotulo(x["ts"])
        if dia != ult:
            rows, ult = rows + '<div class="dh">' + dia + '</div>', dia
        ic, nome = TIPOS[x["t"]]
        tr, ps = x["t"] in ("save", "take", "mov"), x["t"] in ("in", "yld")
        cor = "blue" if tr else "grn" if ps else "red"
        sg = {"save": "→ ", "take": "← ", "mov": "↔ "}.get(x["t"], "+" if ps else "−")
        det = (html.escape(destino(x)) + " · " if x.get("c") else "") + (html.escape(x["o"]) + " · " if x["o"] else "") + fmt_dt(x["ts"])
        rows += ('<div class="tx"><span class="ic">' + ic + '</span><div class="g"><b>' + nome + '</b><div class="k">' + det + '</div></div>'
                 '<b style="color:var(--' + cor + ')">' + sg + brl(x["v"]) + '</b></div>')
    return '<div class="card" style="padding:6px 16px">' + rows + '</div>'


def svg_barras(L, meta):
    W, H = 340, 210
    mx = max([meta] + [x[3] for x in L]) * 1.12 if meta > 0 else 1000.0
    bw = W / max(1, len(L))
    ty = H - 24 - meta / mx * (H - 44)
    s = ('<svg viewBox="0 0 %d %d" style="width:100%%;height:auto;touch-action:pan-y"><line class="tl" x1="0" x2="%d" y1="%.1f" y2="%.1f"/>'
         '<text class="bt" style="fill:var(--gold);text-anchor:start" x="2" y="%.1f">Meta %s</text>' % (W, H, W, ty, ty, ty - 5, kf(meta)))
    for i, (ano, ap, j, b) in enumerate(L):
        h = b / mx * (H - 44)
        x = i * bw + bw * .17
        s += ('<rect class="bar" style="animation-delay:%dms" x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="7"/><text class="bt" x="%.1f" y="%.1f">%s</text><text class="bt" x="%.1f" y="%d">%s</text>'
              % (i * 70, x, H - 24 - h, bw * .66, h, x + bw * .33, H - 28 - h, kf(b), x + bw * .33, H - 7, ano))
    return s + "</svg>"


def v_proj():
    L, falta, ano_fim, meta, (lv, cxf) = projetar()
    fim, c = L[-1][3], S["cfg"]
    meta_em = mes_meta()
    if fim >= meta:
        sub = f"Meta de {brl(meta)} alcançada em {fmt_mes(meta_em)}, com {brl(fim - meta)} de folga no fim do período."
    elif meta_em:
        sub = f"A meta chega em {fmt_mes(meta_em)}."
    else:
        sub = f"No ritmo atual a meta não é alcançada no período. O aporte mensal precisaria ser de cerca de {brl(falta)}."
    topo = card("grn" if fim >= meta else "gold", "Projeção até " + (str(L[-1][0]) if not isinstance(L[-1][0], int) else str(ano_fim)),
                brl(fim), sub + "<br>" + periodo_txt())
    tab = '<table><tr><th>Ano</th><th>Investido</th><th>Juros</th><th>Total</th></tr>'
    for a, p, j, b in L:
        tab += '<tr><td>' + str(a) + '</td><td>' + brl(p) + '</td><td style="color:var(--grn)">' + brl(j) + '</td><td><b>' + brl(b) + '</b></td></tr>'
    partes = [("Saldo livre", S["livre"], lv, "blue")] + [(nome_cx(k), S["caixas"][k], cxf.get(k, 0.0), S["caixas_meta"].get(k, ["", "pur"])[1]) for k in S["caixas"]]
    onde = "".join('<div class="al" style="padding:6px 0"><span class="lb" style="color:var(--' + cor + ')">' + html.escape(nm) + '</span><span class="k">'
                   + brl(h0) + ' → <span style="color:var(--tx);font-weight:700">' + brl(h1) + '</span></span></div>' for nm, h0, h1, cor in partes)
    resto = ('<div class="card">' + svg_barras(L, meta) + '</div>'
             '<div class="card"><div class="lb" style="margin-bottom:4px">Onde seu dinheiro estará em ' + str(ano_fim) + '</div>' + onde + '</div>'
             '<div class="card">' + tab + '</table></div>'
             '<div class="k" style="padding:0 6px">Ponto de partida de hoje: ' + brl(total()) + ' (saldo livre + caixinhas) · aporte líquido de '
             + brl(max(0.0, c["renda"] - c["gastos"])) + '/mês · sempre 100% do CDI (cerca de ' + str(c["cdi"]).replace(".", ",") + '% a.a., bruto e estimado).</div>')
    return topo, resto


def v_idea():
    reserva = S["cfg"]["reserva"]
    ex = round(max(0.0, S["livre"] - reserva), 2)
    main, out = next(iter(S["caixas"]), None), ""
    for k, v in S["caixas"].items():
        if v <= 0.004:
            continue
        m = S["caixas_meta"].get(k, ["Caixinha", "blue", ""])
        if k == main:
            partes, dica = [("Liquidez diária (100% do CDI)", .4), ("RDB de 2 a 5 anos", .35), ("Tesouro IPCA+", .25)], "Objetivo de longo prazo: mantenha uma parte com liquidez e deixe o resto trabalhando por mais tempo."
        else:
            partes, dica = [("Liquidez diária (100% do CDI)", 1.0)], "Objetivo mais próximo: o melhor é manter com resgate imediato e sem risco."
        linhas = "".join('<div class="al" style="padding:4px 0"><span class="k">' + n + ' · ' + str(round(p * 100)) + '%</span><b style="font-size:15px">' + brl(v * p) + '</b></div>' for n, p in partes)
        out += card(m[1], html.escape(m[0]), brl(v), dica, linhas)
    sub = "Esse valor pode ir para a sua caixinha principal e começar a render." if ex else "Seu saldo livre precisa passar de " + brl(reserva + 1) + " para sobrar algo além da reserva."
    out += card("blue", "Saldo livre acima da reserva", brl(ex), sub)
    return out + '<div class="k" style="padding:0 6px">Hoje todas as caixinhas rendem 100% do CDI com resgate imediato. As ideias acima mostram como buscar mais retorno. São sugestões educativas, não recomendação de investimento.</div>'


def tela_ideias():
    ks = list(S["caixas"])
    sig = "|".join(sorted(ks))
    if not ks:
        st.markdown(card("blue", "Ideias sob medida", "Sem caixinhas", "Crie sua primeira caixinha para receber ideias de como fazer cada uma render mais."), unsafe_allow_html=True)
        if not SUP and st.button("➕ Criar caixinha", key="b_ic", use_container_width=True):
            dlg_novo()
        return
    if st.session_state.get("ideias_ok") != sig:
        n = len(ks)
        nomes = ", ".join(nome_cx(k).replace("Caixinha ", "") for k in ks)
        st.markdown('<div class="card as" style="padding:14px 16px">🤔 Você tem <b>' + str(n) + (" caixinha" if n == 1 else " caixinhas") + '</b> (' + html.escape(nomes) + '), está correto?</div>', unsafe_allow_html=True)
        with st.container(key="conf"):
            a, b = st.columns(2)
            if a.button("Sim", key="ok_s", type="primary", use_container_width=True):
                st.session_state.update(ideias_ok=sig, ideias_no=False)
                st.rerun()
            if b.button("Não", key="ok_n", use_container_width=True):
                st.session_state["ideias_no"] = True
        if st.session_state.get("ideias_no"):
            st.caption("Sem problemas! Ajuste suas caixinhas e volte aqui." if not SUP else "Peça ao titular para ajustar as caixinhas.")
            if not SUP:
                with st.container(key="conf2"):
                    c1, c2 = st.columns(2)
                    if c1.button("➕ Criar", key="b_ic2", use_container_width=True):
                        dlg_novo()
                    if c2.button("🗑️ Excluir", key="b_ie2", use_container_width=True):
                        dlg_excluir()
        return
    st.markdown(v_idea(), unsafe_allow_html=True)
    ex = round(max(0.0, S["livre"] - S["cfg"]["reserva"]), 2)
    if ex >= 1 and not SUP and st.button("🔒 Guardar " + brl(ex) + " na " + nome_cx(ks[0]), key="b_ex", use_container_width=True):
        e = aplicar("save", ex, ks[0], "Excedente guardado")
        if e:
            st.error(e)
        else:
            st.rerun()
    if st.button("Revisar minhas caixinhas", key="b_rev", use_container_width=True):
        st.session_state["ideias_ok"] = None
        st.rerun()


# ------------------------------------------------------------------ diálogos
@st.dialog("⚙️ Ajustes da conta")
def dlg_ajustes():
    c = S["cfg"]
    tem_sonho = "sonho" in S["caixas"] and "futuro" in S["caixas"]
    pal = list(PALETAS)
    with st.form("f_ajustes"):
        nome = st.text_input("Nome da conta", CONTA["nome"], max_chars=24)
        paleta = st.selectbox("Cores do app", pal, index=pal.index(S["paleta"]) if S.get("paleta") in pal else 0)
        tutorial = st.checkbox("Mostrar tutorial na tela Início", value=c["tutorial"])
        st.caption("🎯 META E RESERVA")
        meta = st.number_input("Meta financeira (R$)", min_value=0.0, value=float(c["meta"]), step=1000.0, format="%.2f")
        reserva = st.number_input("Reserva fixa protegida no Saldo Livre (R$)", min_value=0.0, value=float(c["reserva"]), step=50.0, format="%.2f")
        st.caption("💰 BALANÇO MENSAL (lançado todo dia 1)")
        renda = st.number_input("Renda mensal (R$)", min_value=0.0, value=float(c["renda"]), step=50.0, format="%.2f")
        gast = st.number_input("Gastos fixos do mês (R$)", min_value=0.0, value=float(c["gastos"]), step=10.0, format="%.2f")
        guard = st.number_input("Guardar automático na primeira caixinha (R$)", min_value=0.0, value=float(c["guardar"]), step=50.0, format="%.2f")
        cdi = st.number_input("CDI estimado (% ao ano). O app sempre projeta 100% dele", min_value=0.0, max_value=100.0, value=float(c["cdi"]), step=0.1, format="%.2f")
        sd = st.date_input("Liberar a Sonho para a Futuro em (opcional)", value=date.fromisoformat(c["sonho_data"]) if c.get("sonho_data") else None,
                           format="DD/MM/YYYY") if tem_sonho else None
        if st.form_submit_button("Salvar", type="primary", use_container_width=True):
            CONTA["nome"] = nome.strip() or CONTA["nome"]
            S["paleta"] = st.session_state["paleta"] = paleta
            S["cfg"].update(renda=renda, gastos=gast, guardar=min(guard, max(0.0, renda - gast)), cdi=cdi, meta=meta, reserva=reserva, tutorial=tutorial, ajustado=True)
            if tem_sonho:
                S["cfg"]["sonho_data"] = sd.isoformat() if sd else None
            fecha("Ajustes salvos!")
            st.rerun()
    if HAS_CRYPTO:
        st.divider()
        r = FACEID(modo="reg", chal=st.session_state["chal"], user=U, tema=st.session_state["tema"], key="fid_reg", default=None)
        if r and r.get("kind") == "reg" and r["n"] != st.session_state["fid_done"]:
            st.session_state["fid_done"] = r["n"]
            if fid_registrar(U, r):
                st.session_state["msg"] = "Face ID ativado neste aparelho!"
                st.rerun()
            st.error("Não foi possível validar o Face ID.")


def form_op(op):
    cx = cx2 = None
    if op in ("save", "take", "yld", "mov"):
        ops = [k for k in S["caixas"] if op == "save" or S["caixas"][k] > 0]
        if not ops:
            st.info("Nenhuma caixinha disponível ainda. Crie uma na aba ➕ Montar Caixinha." if op == "save" else "Nenhuma caixinha com saldo ainda.")
            return
        cx = st.selectbox("De" if op == "mov" else "Caixinha", ops, key="c_" + op, format_func=lambda k: nome_cx(k) + " · " + brl(S["caixas"][k]))
        if op == "mov":
            outras = [k for k in S["caixas"] if k != cx]
            if not outras:
                st.info("Crie outra caixinha para poder mover valores.")
                return
            cx2 = st.selectbox("Para", outras, key="d_mov", format_func=nome_cx)
    v = st.number_input("Valor (R$)", min_value=0.0, value=0.0, step=0.10 if op == "yld" else 1.0, format="%.2f", key="v_" + op)
    if op == "yld" and cx:
        st.caption(f"100% do CDI rende cerca de {brl(S['caixas'][cx] * ((1 + S['cfg']['cdi'] / 100) ** (1 / 252) - 1))} por dia útil nessa caixinha.")
    obs = st.text_input("Observação (opcional)", max_chars=40, key="o_" + op)
    if st.button("Confirmar", type="primary", use_container_width=True, key="ok_" + op):
        e = mover(cx, cx2, v, obs.strip()) if op == "mov" else aplicar(op, v, cx, obs.strip())
        if e:
            st.error(e)
        else:
            st.rerun()


def form_criar_cx():
    st.caption("Crie caixinhas para cada objetivo. Todas rendem 100% do CDI com resgate imediato.")
    nome = st.text_input("Nome do objetivo (ex: Intercâmbio)", max_chars=24)
    cor = st.selectbox("Cor", ["pur", "blue", "gold", "grn", "red"], format_func={"pur": "Roxo", "blue": "Azul", "gold": "Dourado", "grn": "Verde", "red": "Vermelho"}.get)
    desc = st.text_input("Descrição (opcional)", max_chars=40)
    if st.button("Criar caixinha", type="primary", use_container_width=True):
        if not nome.strip():
            st.error("Dê um nome para a caixinha.")
        else:
            k = chave(nome) + "-" + secrets.token_hex(2)
            S["caixas"][k] = 0.0
            S["caixas_meta"][k] = [nome.strip(), cor, desc.strip()]
            fecha("Caixinha criada! Agora guarde um valor nela em ＋ › Caixinhas.")
            st.rerun()


@st.dialog("Novo lançamento")
def dlg_novo():
    t1, t2, t3 = st.tabs(["💳 Conta", "🐷 Caixinhas", "➕ Montar Caixinha"])
    with t1:
        form_op(st.radio("Conta", ["in", "out"], horizontal=True, format_func=CURTO.get, label_visibility="collapsed", key="r1"))
    with t2:
        form_op(st.radio("Caixinhas", ["save", "take", "yld", "mov"], horizontal=True, format_func=CURTO.get, label_visibility="collapsed", key="r2"))
    with t3:
        form_criar_cx()


@st.dialog("🗑️ Excluir caixinha")
def dlg_excluir():
    ops = list(S["caixas"])
    if not ops:
        st.info("Nenhuma caixinha para excluir.")
        return
    cx = st.selectbox("Qual caixinha?", ops, format_func=lambda k: nome_cx(k) + " · " + brl(S["caixas"][k]))
    modo = st.radio("O que fazer com o saldo?", ["Resgatar para o Saldo Livre", "Apenas zerar (sai do patrimônio)"])
    if st.button("Excluir caixinha", type="primary", use_container_width=True):
        excluir_caixinha(cx, modo.startswith("Resgatar"))
        st.rerun()


@st.dialog("🛡️ Painel dos pais")
def dlg_pais():
    st.caption("Modo supervisão: somente leitura. Aqui você pode redefinir os acessos.")
    senha = st.text_input("Nova senha do titular (mín. 4)", type="password")
    pin = st.text_input("Novo PIN dos pais (4 números)", type="password", max_chars=4)
    if st.button("Salvar", type="primary", use_container_width=True):
        if (senha and len(senha) < 4) or (pin and not (pin.isdigit() and len(pin) == 4)):
            st.error("Senha com 4+ caracteres e PIN com exatamente 4 números.")
        else:
            if senha:
                CONTA["s"], CONTA["h"] = mk(senha)
            if pin:
                CONTA["ps"], CONTA["ph"] = mk(pin)
            salvar()
            st.session_state["msg"] = "Acessos atualizados"
            st.rerun()


# ------------------------------------------------------------------ app
if not SUP:
    creditar_mes()
    liberar_sonho()
if st.session_state.get("warn"):
    st.session_state["msg"] = st.session_state.pop("warn")
if st.session_state["msg"]:
    st.toast(st.session_state["msg"])
    st.session_state["msg"] = None


def _tema():
    st.session_state["tema"] = "light" if st.session_state["tema"] == "dark" else "dark"
    db()["contas"][st.session_state["u"]]["d"]["tema"] = st.session_state["tema"]
    salvar()


def _sair():
    u = st.session_state["u"]
    if u in db()["contas"]:
        db()["contas"][u].get("sess", {}).pop(_th(st.query_params.get("s", "")), None)
        salvar()
    st.query_params.clear()
    st.session_state.update(u=None, modo=None, tela="login", chal=secrets.token_urlsafe(32), launch=False, nav=False, tab=0, recarregar=True)


def _nav(v):
    st.session_state["nav"] = v


st.button("☀️" if st.session_state["tema"] == "dark" else "🌙", key="b_tema", on_click=_tema, help="Alternar tema")
if not SUP and st.button("⚙️", key="b_ajustes_top", help="Ajustes da conta"):
    dlg_ajustes()
st.button("🔒", key="b_sair", on_click=_sair, help="Encerrar sessão")

tab = st.session_state["tab"]
if st.session_state["nav"]:
    with st.container(key="nav"):
        st.button("‹", key="b_min", on_click=_nav, args=(False,), help="Recolher menu")
        aba = st.radio("Atalhos", ABAS, index=tab, key="aba", horizontal=True, label_visibility="collapsed")
        if st.button("🛡️" if SUP else "＋", key="b_plus", help="Painel dos pais" if SUP else "Novo lançamento"):
            (dlg_pais if SUP else dlg_novo)()
    idx = ABAS.index(aba)
else:
    st.button(ABAS[tab].split()[0], key="bolha", on_click=_nav, args=(True,), help="Abrir menu")
    idx = tab
if idx != tab:
    st.session_state.update(dir="R" if idx > tab else "L", tab=idx)

st.markdown('<div class="hd"><div class="k">' + TITULOS[idx] + ' · ' + hoje_txt() + '</div><h1>' + html.escape(CONTA["nome"]) + '</h1></div>', unsafe_allow_html=True)
if SUP:
    st.markdown('<div class="sup">🔐 <b>Modo supervisão:</b> somente leitura. Lançamentos e ajustes ficam ocultos.</div>', unsafe_allow_html=True)

with st.container(key=f"view_{idx}_from{st.session_state['dir']}"):
    if idx == 0:
        if S["cfg"]["tutorial"] and not SUP:
            st.markdown(v_tutorial(), unsafe_allow_html=True)
            if st.button("Concluir tutorial", key="b_tut", use_container_width=True):
                S["cfg"]["tutorial"] = False
                fecha("Tutorial concluído. Você pode reativá-lo em ⚙️ Ajustes.")
                st.rerun()
        st.markdown(v_home(), unsafe_allow_html=True)
        if not SUP and S["caixas"]:
            if st.button("🗑️ Excluir caixinha", key="b_del", use_container_width=True):
                dlg_excluir()
    elif idx == 1:
        st.markdown(v_ext(), unsafe_allow_html=True)
        if S["extrato"]:
            hoje, x = f"{agora():%Y-%m-%d}", xlsx_ext()
            with st.container(key="dl"):
                c1, c2 = st.columns(2)
                if x:
                    c1.download_button("📊 Excel", x, file_name=f"extrato_future_{hoje}.xlsx", mime=XL, use_container_width=True)
                c2.download_button("📄 CSV", csv_ext(), file_name=f"extrato_future_{hoje}.csv", mime="text/csv", use_container_width=True)
    elif idx == 2:
        topo, resto = v_proj()
        st.markdown(topo, unsafe_allow_html=True)
        extra = st.slider("E se eu guardasse mais por mês? (R$)", 0, 1000, 0, 50, key="sl_extra")
        if extra:
            st.markdown(card("pur", "Com +" + brl(extra) + " por mês", brl(final_com(extra)),
                             "Meta em: " + fmt_mes(mes_meta(extra)) + " (hoje: " + fmt_mes(mes_meta()) + ")."), unsafe_allow_html=True)
        st.markdown(resto, unsafe_allow_html=True)
        hoje, x = f"{agora():%Y-%m-%d}", xlsx_proj()
        with st.container(key="dl2"):
            c1, c2 = st.columns(2)
            if x:
                c1.download_button("📊 Excel", x, file_name=f"projecao_future_{hoje}.xlsx", mime=XL, use_container_width=True)
            else:
                c1.download_button("📄 CSV", csv_proj(), file_name=f"projecao_future_{hoje}.csv", mime="text/csv", use_container_width=True)
            c2.download_button("📄 PDF", pdf_proj(), file_name=f"projecao_future_{hoje}.pdf", mime="application/pdf", use_container_width=True)
    else:
        tela_ideias()

if st.session_state["fx"]:
    st.markdown(fx_html(st.session_state["fx"]), unsafe_allow_html=True)
    st.session_state["fx"] = None
if st.session_state["launch"]:
    st.markdown('<div class="lift"><i>🚀</i></div>', unsafe_allow_html=True)
    st.session_state["launch"] = False
