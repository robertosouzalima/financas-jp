# -*- coding: utf-8 -*-
"""Projeto 18 Anos - controle financeiro pessoal (Streamlit >= 1.40).

Rodar:   pip install -U streamlit && streamlit run app.py
Deploy:  Streamlit Cloud. requirements.txt -> streamlit>=1.40
Código:  "5102" por padrão. Para não deixá-lo no código, crie em Settings > Secrets:  codigo = "5102"
Tema:    crie .streamlit/config.toml com  [theme] base="dark"
"""
import csv, io, json, copy, random, time, html, hmac, secrets
from datetime import datetime
from pathlib import Path
import streamlit as st

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("America/Sao_Paulo")
except Exception:
    TZ = None

st.set_page_config(page_title="Projeto 18 Anos", page_icon="💜", layout="centered", initial_sidebar_state="collapsed")

try:
    CODIGO = str(st.secrets["codigo"])
except Exception:
    CODIGO = "5102"

ARQ = Path(__file__).with_name("projeto18_dados.json")
META, RESERVA, ANO_FIM = 62000.0, 100.0, 2032
CAIXAS = {"futuro": ("Caixinha Futuro", "pur", "Para a meta dos 18 anos"),
          "sonho": ("Caixinha Sonho", "gold", "Para o grande objetivo")}
TIPOS = {"in": ("📥", "Recebi dinheiro"), "save": ("🔒", "Guardar na caixinha"),
         "take": ("🔓", "Resgatar da caixinha"), "yld": ("📈", "Registrar rendimento / juros"),
         "out": ("💸", "Gastei dinheiro"), "cfg": ("⚙️", "Configurar renda / gastos fixos"),
         "del": ("🗑️", "Caixinha zerada")}
LANCAR = ["in", "save", "take", "yld", "out", "cfg"]
ABAS = ["🏠 Início", "🧾 Extrato", "📈 Projeção", "💡 Ideias"]

# Valores iniciais reais do Nubank (soma = R$ 2.038,40)
PADRAO = {"nome": "Minha Conta", "tema": "dark", "livre": 100.00,
          "caixas": {"futuro": 966.55, "sonho": 971.85}, "extrato": [],
          "cfg": {"renda": 600.0, "guardar": 500.0, "gastos": 0.0, "cdi": 9.5}, "ultimo_credito": None}

for _k, _v in dict(auth=False, tema="dark", prev=0, dir="R", fx=None, msg=None, tent=0, bloq=0.0).items():
    st.session_state.setdefault(_k, _v)


# ---------------------------------------------------------------- utilidades
def agora():
    return datetime.now(TZ) if TZ else datetime.now()


def brl(v):
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if v < 0 else "") + "R$ " + s


def kf(v):
    return f"{v / 1000:.1f}".replace(".", ",") + "k"


def fmt_dt(iso):
    return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M:%S")


def carregar():
    d = copy.deepcopy(PADRAO)
    try:
        for k, v in json.loads(ARQ.read_text("utf-8")).items():
            if isinstance(v, dict) and k in d:
                d[k].update(v)
            else:
                d[k] = v
    except Exception:
        pass
    if not d["ultimo_credito"]:
        h = agora()
        d["ultimo_credito"] = f"{h.year}-{h.month:02d}"
    return d


def salvar():
    d = st.session_state.get("S")
    if d:
        try:
            ARQ.write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")
        except Exception:
            pass


@st.cache_resource
def sessoes():
    return {}


# ------------------------------------------------------------------ visual
TEMAS = {
    "dark": ":root{--bg:#07070b;--c1:#16161f;--c2:#0e0e15;--tx:#f4f4f8;--mu:#8b8b9a;--ln:rgba(255,255,255,.09);--s1:rgba(0,0,0,.6);--s2:rgba(255,255,255,.04);--blue:#4aa3ff;--pur:#b57bff;--gold:#f0c24b;--grn:#3fdc78;--red:#ff6b62;--glass:rgba(34,34,48,.55)}",
    "light": ":root{--bg:#eceef4;--c1:#fff;--c2:#f3f4f9;--tx:#14141c;--mu:#656575;--ln:rgba(0,0,0,.09);--s1:rgba(120,125,150,.3);--s2:rgba(255,255,255,.95);--blue:#0a6fe0;--pur:#8a35d8;--gold:#9a6f00;--grn:#12843f;--red:#d9342b;--glass:rgba(255,255,255,.65)}",
}
CSS = """
.stApp{background:var(--bg)!important;color:var(--tx);overflow-x:hidden;font-family:-apple-system,"SF Pro Text",Roboto,system-ui,sans-serif}
header[data-testid="stHeader"],#MainMenu,footer{display:none!important}
.block-container{max-width:480px!important;padding:1.2rem 1rem 9rem!important}
.stApp p,.stApp label,.stApp h1,.stApp li,[data-testid="stDialog"] *{color:var(--tx)}
.stApp input,[data-baseweb="select"]>div,[data-baseweb="input"],[data-baseweb="base-input"]{background:var(--c2)!important;color:var(--tx)!important;border-radius:14px!important}
div[role="dialog"]{background:var(--c1)!important;border-radius:28px!important}
button[kind="secondary"],[data-testid="stBaseButton-secondary"]{background:var(--c2);border:1px solid var(--ln);border-radius:16px}
button[kind="secondary"] p,[data-testid="stBaseButton-secondary"] p{color:var(--tx)}
button[kind="primary"],[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,var(--pur),var(--blue))!important;border:0!important;border-radius:16px!important}
button[kind="primary"] *,[data-testid="stBaseButton-primary"] *{color:#fff!important}
[data-testid="stForm"]{border:0;padding:0;background:transparent}
.hd h1{margin:0;font-size:26px;letter-spacing:-.03em;padding:0}.hd{margin-bottom:16px}
.login{text-align:center;padding:12vh 0 22px;animation:slR .6s cubic-bezier(.2,.8,.2,1)}
.login h1{font-size:30px;letter-spacing:-.03em;margin:10px 0 4px;padding:0}.logo{font-size:56px;animation:glow 3s ease-in-out infinite}
@keyframes glow{50%{transform:scale(1.08);filter:drop-shadow(0 0 18px var(--pur))}}
.card{background:linear-gradient(145deg,var(--c1),var(--c2));border:1px solid color-mix(in srgb,var(--c,var(--ln)) 50%,transparent);border-radius:26px;padding:18px;box-shadow:9px 9px 22px var(--s1),-5px -5px 16px var(--s2);margin-bottom:16px}
.k{color:var(--mu);font-size:13px}.lb{font-size:14px;font-weight:600}.big{font-size:34px;font-weight:700;letter-spacing:-.035em;margin:2px 0 8px;font-variant-numeric:tabular-nums}
.pg{height:8px;border-radius:9px;background:var(--ln);overflow:hidden;margin:6px 0}.pg i{display:block;height:100%;border-radius:9px;background:linear-gradient(90deg,var(--blue),var(--grn))}
.as{font-size:15px;border-style:dashed}
.tx{display:flex;align-items:center;gap:12px;padding:13px 0;border-bottom:1px solid var(--ln)}.tx:last-child{border:0}.tx .g{flex:1;min-width:0}
.ic{width:40px;height:40px;border-radius:14px;background:var(--c2);display:grid;place-items:center;font-size:19px;flex:none;border:1px solid var(--ln)}
table{width:100%;border-collapse:collapse;font-size:13.5px}th{color:var(--mu);font-weight:500;text-align:right;padding:6px 0}td{padding:10px 0;text-align:right;border-top:1px solid var(--ln)}th:first-child,td:first-child{text-align:left}
.bar{fill:var(--grn);opacity:.9}.bt{fill:var(--mu);font-size:10px;text-anchor:middle}.tl{stroke:var(--gold);stroke-dasharray:4 4;stroke-width:1.2}
.al{display:flex;justify-content:space-between;align-items:baseline}.al b{font-size:20px}
.st-key-nav{position:fixed;left:50%;transform:translateX(-50%);bottom:calc(14px + env(safe-area-inset-bottom,0px));width:min(94vw,440px);z-index:999;background:var(--glass);backdrop-filter:blur(28px) saturate(180%);-webkit-backdrop-filter:blur(28px) saturate(180%);border:1px solid var(--ln);border-radius:999px;padding:6px;box-shadow:0 14px 40px var(--s1),inset 0 1px 0 rgba(255,255,255,.14)}
.st-key-nav [role="radiogroup"]{display:flex;flex-wrap:nowrap;gap:2px;width:100%}
.st-key-nav label{flex:1;justify-content:center;margin:0;padding:12px 2px;border-radius:999px;cursor:pointer;transition:background .3s}
.st-key-nav label>div:first-child{display:none}
.st-key-nav label p{font-size:11.5px;font-weight:600;white-space:nowrap;color:var(--mu)}
.st-key-nav label:has(input:checked){background:color-mix(in srgb,var(--pur) 26%,transparent)}
.st-key-nav label:has(input:checked) p{color:var(--tx)}
.st-key-b_tema,.st-key-b_sair,.st-key-fab_btn{position:fixed;z-index:1000;width:auto!important}
.st-key-b_tema{top:calc(12px + env(safe-area-inset-top,0px));right:66px}.st-key-b_sair{top:calc(12px + env(safe-area-inset-top,0px));right:14px}
.st-key-fab_btn{right:18px;bottom:calc(92px + env(safe-area-inset-bottom,0px))}
.st-key-b_tema button,.st-key-b_sair button{width:44px;height:44px;border-radius:50%;padding:0;background:var(--glass);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid var(--ln);font-size:18px}
.st-key-fab_btn button{width:58px;height:58px;border-radius:50%;padding:0;border:0;background:linear-gradient(135deg,var(--pur),var(--blue));box-shadow:0 8px 24px color-mix(in srgb,var(--pur) 55%,transparent)}
.st-key-fab_btn button p{color:#fff;font-size:28px;line-height:1}
[class*="_fromR"]{animation:slR .4s cubic-bezier(.2,.8,.2,1)}[class*="_fromL"]{animation:slL .4s cubic-bezier(.2,.8,.2,1)}
@keyframes slR{from{transform:translateX(48px);opacity:0}}@keyframes slL{from{transform:translateX(-48px);opacity:0}}
.fx{position:fixed;inset:0;pointer-events:none;z-index:2000;overflow:hidden}
.fx i{position:absolute;bottom:-50px;font-style:normal;opacity:0;animation:rise 2.4s ease-out forwards}
.fx b{position:absolute;left:50%;top:36%;font-size:36px;color:var(--grn);opacity:0;animation:pop 2.4s ease forwards;text-shadow:0 4px 24px rgba(0,0,0,.35)}
@keyframes rise{0%{transform:translateY(0) scale(.6);opacity:0}15%{opacity:1}100%{transform:translateY(-90vh) rotate(25deg) scale(1.1);opacity:0}}
@keyframes pop{0%{opacity:0;transform:translate(-50%,30px) scale(.7)}20%{opacity:1;transform:translate(-50%,0) scale(1.05)}80%{opacity:1}100%{opacity:0;transform:translate(-50%,-40px)}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""
st.markdown("<style>" + TEMAS[st.session_state["tema"]] + CSS + "</style>", unsafe_allow_html=True)


# ------------------------------------------------------- SESSÃO SECRETA (5102)
def tela_login():
    st.markdown('<div class="login"><div class="logo">💜</div><h1>Projeto 18 Anos</h1>'
                '<div class="k" style="letter-spacing:.2em">INICIAR SESSÃO</div></div>', unsafe_allow_html=True)
    with st.form("login", clear_on_submit=True):
        cod = st.text_input("Código secreto", type="password", max_chars=12, placeholder="Código secreto",
                            label_visibility="collapsed")
        ok = st.form_submit_button("Entrar", type="primary", use_container_width=True)
    if not ok:
        return
    espera = st.session_state["bloq"] - time.time()
    if espera > 0:
        st.error(f"Muitas tentativas. Aguarde {int(espera) + 1}s.")
    elif hmac.compare_digest(cod.encode(), CODIGO.encode()):
        tok = secrets.token_urlsafe(16)
        sessoes()[tok] = time.time()
        st.query_params["s"] = tok
        st.session_state.update(auth=True, tent=0)
        st.rerun()
    else:
        st.session_state["tent"] += 1
        if st.session_state["tent"] >= 5:
            st.session_state.update(bloq=time.time() + 30, tent=0)
        st.error("Código incorreto.")


if not st.session_state["auth"]:
    tok = st.query_params.get("s")
    if tok and tok in sessoes():            # lembra a sessão após recarregar a página
        st.session_state["auth"] = True
if not st.session_state["auth"]:
    tela_login()
    st.stop()                                # nada de finanças é carregado nem exibido

if "S" not in st.session_state:              # dados só são lidos após o login
    st.session_state["S"] = carregar()
    st.session_state["tema"] = st.session_state["S"]["tema"]
    st.rerun()
S = st.session_state["S"]


# ------------------------------------------------------------ regras de negócio
def total():
    return round(S["livre"] + sum(S["caixas"].values()), 2)


def reg(t, v, cx, obs, ts=None):
    S["extrato"].append({"t": t, "v": round(v, 2), "c": cx, "o": obs, "ts": (ts or agora()).isoformat()})


def fx(valor):
    st.session_state["fx"] = {"txt": "+" + brl(valor), "n": int(time.time() * 1000)}


def aplicar(t, v, cx=None, obs=""):
    v = round(v, 2)
    if v <= 0:
        return "Informe um valor maior que zero."
    cxs = S["caixas"]
    if t == "save":
        if S["livre"] - v < RESERVA - 1e-9:
            return f"A reserva de {brl(RESERVA)} é protegida. Você pode guardar até {brl(max(0, S['livre'] - RESERVA))}."
        S["livre"] -= v
        cxs[cx] += v
    elif t == "take":
        if v > cxs[cx] + 1e-9:
            return f"Essa caixinha tem só {brl(cxs[cx])}."
        cxs[cx] -= v
        S["livre"] += v
    elif t == "yld":
        if cxs[cx] <= 0:
            return "Essa caixinha está sem saldo."
        cxs[cx] += v
    elif t == "out":
        if v > S["livre"] + 1e-9:
            return f"Saldo livre insuficiente ({brl(S['livre'])})."
        S["livre"] -= v
    else:
        S["livre"] += v
    S["livre"] = round(S["livre"], 2)
    for k in cxs:
        cxs[k] = round(cxs[k], 2)
    reg(t, v, cx if t in ("save", "take", "yld") else None, obs)
    salvar()
    if t in ("in", "yld"):
        fx(v)
    st.session_state["msg"] = "Lançado em " + fmt_dt(S["extrato"][-1]["ts"])
    return ""


def excluir_caixinha(cx, resgatar):
    v = S["caixas"][cx]
    if resgatar:
        S["livre"] = round(S["livre"] + v, 2)
        reg("take", v, cx, "Exclusão da caixinha")
    else:
        reg("del", v, cx, "Saldo removido do patrimônio")
    S["caixas"][cx] = 0.0
    salvar()
    st.session_state["msg"] = f"{CAIXAS[cx][0]} excluída"


def creditar_mes():
    """Todo dia 1 entra a renda (R$ 600): R$ 500 vão p/ Caixinha Futuro e R$ 100 ficam livres, acumulando."""
    h = agora()
    a, m = S["ultimo_credito"].split("-")
    ult, atual = int(a) * 12 + int(m) - 1, h.year * 12 + h.month - 1
    if atual <= ult:
        return
    c = S["cfg"]
    g = min(c["guardar"], c["renda"])
    n = 0
    for k in range(ult + 1, atual + 1):
        ano, mes = divmod(k, 12)
        ts = datetime(ano, mes + 1, 1, 0, 0, 0, tzinfo=TZ)
        S["livre"] += c["renda"]
        reg("in", c["renda"], None, "Mesada automática", ts)
        if g > 0:
            S["livre"] -= g
            S["caixas"]["futuro"] += g
            reg("save", g, "futuro", "Aporte automático", ts)
        n += 1
    S["livre"] = round(S["livre"], 2)
    S["caixas"]["futuro"] = round(S["caixas"]["futuro"], 2)
    S["ultimo_credito"] = f"{h.year}-{h.month:02d}"
    salvar()
    fx(c["renda"] * n)
    st.session_state["msg"] = f"Mesada de {brl(c['renda'])} creditada" if n == 1 else f"{n} mesadas creditadas"


def projetar():
    """Base = Saldo Livre + Caixinhas reais. Aporte mensal + CDI composto mensalmente até dez/2032."""
    c, h = S["cfg"], agora()
    r = (1 + c["cdi"] / 100) ** (1 / 12) - 1
    t = total()
    b = ap = t
    n = 0
    linhas = []
    for ano in range(h.year, ANO_FIM + 1):
        for _ in range(12 - h.month if ano == h.year else 12):
            b = b * (1 + r) + c["renda"]
            ap += c["renda"]
            n += 1
        linhas.append((ano, ap, b - ap, b))
    g = (1 + r) ** n
    falta = max(0.0, (META - t * g) / ((g - 1) / r)) if n and r > 0 else 0.0
    return linhas, falta


def csv_extrato():
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Data", "Hora", "Tipo", "Caixinha", "Valor (R$)", "Observação"])
    for x in sorted(S["extrato"], key=lambda e: e["ts"]):
        d = datetime.fromisoformat(x["ts"])
        obs = x["o"]
        if obs[:1] in ("=", "+", "-", "@"):
            obs = "'" + obs
        w.writerow([d.strftime("%d/%m/%Y"), d.strftime("%H:%M:%S"), TIPOS[x["t"]][1],
                    CAIXAS[x["c"]][0] if x["c"] else "", f"{x['v']:.2f}".replace(".", ","), obs])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


# ------------------------------------------------------------------ telas
def fx_html(d):
    random.seed(d["n"])
    itens = "".join(
        '<i style="left:%d%%;font-size:%dpx;animation-delay:%.2fs;animation-duration:%.2fs">%s</i>'
        % (random.randint(4, 90), random.randint(22, 38), random.random() * .9, 1.8 + random.random() * 1.2,
           random.choice(["💵", "💸", "🪙", "💰"])) for _ in range(16))
    return f'<div class="fx">{itens}<b>{d["txt"]}</b></div>'


def card(cor, tit, val, sub="", extra=""):
    return (f'<div class="card" style="--c:var(--{cor})"><div class="lb" style="color:var(--{cor})">{tit}</div>'
            f'<div class="big">{val}</div>{extra}<div class="k">{sub}</div></div>')


def v_home():
    t, f, c = total(), S["livre"], S["cfg"]
    pc = min(100, t / META * 100)
    if f > RESERVA + .005:
        msg = f"Você tem <b>{brl(f - RESERVA)}</b> acima da reserva de {brl(RESERVA)}. Veja onde aplicar em Ideias."
    elif f < RESERVA - .005:
        msg = f"Atenção: faltam <b>{brl(RESERVA - f)}</b> para completar a reserva de {brl(RESERVA)}."
    else:
        msg = f"Reserva de {brl(RESERVA)} completa. Tudo em ordem."
    h = agora()
    prox = f"01/{h.month + 1:02d}/{h.year}" if h.month < 12 else f"01/01/{h.year + 1}"
    livre_mes = c["renda"] - min(c["guardar"], c["renda"])
    pct = f"{pc:.1f}".replace(".", ",")
    out = card("grn", "Patrimônio total", brl(t), f"{pct}% da meta de {brl(META)} aos 18 anos",
               f'<div class="pg"><i style="width:{pc}%"></i></div>')
    out += f'<div class="card as">💡 {msg}</div>'
    out += card("blue", "Saldo livre", brl(f),
                f"Reserva fixa de {brl(RESERVA)} · {brl(livre_mes)} ficam livres todo mês, acumulando.<br>"
                f"Próxima mesada de {brl(c['renda'])}: {prox}")
    for k, (nome, cor, sub) in CAIXAS.items():
        if S["caixas"][k] > 0.004:
            out += card(cor, nome, brl(S["caixas"][k]), sub)
    return out


def v_ext():
    if not S["extrato"]:
        return '<div class="card"><div class="k">Nenhum lançamento ainda. Toque no + para começar.</div></div>'
    itens = sorted(enumerate(S["extrato"]), key=lambda p: (p[1]["ts"], p[0]), reverse=True)
    rows = ""
    for _, x in itens:
        ic, nome = TIPOS[x["t"]]
        tr, ps = x["t"] in ("save", "take"), x["t"] in ("in", "yld")
        cor = "blue" if tr else "grn" if ps else "red"
        sg = ("→ " if x["t"] == "save" else "← ") if tr else "+" if ps else "−"
        det = (CAIXAS[x["c"]][0] + " · " if x["c"] else "") + (html.escape(x["o"]) + " · " if x["o"] else "") + fmt_dt(x["ts"])
        rows += (f'<div class="tx"><span class="ic">{ic}</span><div class="g"><b>{nome}</b><div class="k">{det}</div></div>'
                 f'<b style="color:var(--{cor})">{sg}{brl(x["v"])}</b></div>')
    return f'<div class="card" style="padding:6px 16px">{rows}</div>'


def svg_barras(L):
    W, H = 340, 210
    mx = max([META] + [x[3] for x in L]) * 1.12
    bw = W / len(L)
    ty = H - 24 - META / mx * (H - 44)
    s = (f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto;touch-action:pan-y">'
         f'<line class="tl" x1="0" x2="{W}" y1="{ty:.1f}" y2="{ty:.1f}"/>'
         f'<text class="bt" style="fill:var(--gold);text-anchor:start" x="2" y="{ty - 5:.1f}">Meta {kf(META)}</text>')
    for i, (ano, ap, j, b) in enumerate(L):
        h = b / mx * (H - 44)
        x = i * bw + bw * .17
        s += (f'<rect class="bar" x="{x:.1f}" y="{H - 24 - h:.1f}" width="{bw * .66:.1f}" height="{h:.1f}" rx="7"/>'
              f'<text class="bt" x="{x + bw * .33:.1f}" y="{H - 28 - h:.1f}">{kf(b)}</text>'
              f'<text class="bt" x="{x + bw * .33:.1f}" y="{H - 7}">{ano}</text>')
    return s + "</svg>"


def v_proj():
    L, falta = projetar()
    if not L:
        return card("grn", "Projeção", brl(total()), "Sem meses restantes até 2032.")
    fim = L[-1][3]
    ok = fim >= META
    sub = (f"Meta de {brl(META)} batida, com folga de {brl(fim - META)}." if ok
           else f"Para chegar a {brl(META)}, aporte cerca de {brl(falta)} por mês.")
    tab = ('<table><tr><th>Ano</th><th>Investido</th><th>Juros</th><th>Total</th></tr>'
           + "".join(f'<tr><td>{a}</td><td>{brl(p)}</td><td style="color:var(--grn)">{brl(j)}</td><td><b>{brl(b)}</b></td></tr>'
                     for a, p, j, b in L) + '</table>')
    cdi = str(S["cfg"]["cdi"]).replace(".", ",")
    return (card("grn" if ok else "gold", "Projeção até 2032", brl(fim), sub)
            + f'<div class="card">{svg_barras(L)}</div><div class="card">{tab}</div>'
            + f'<div class="k" style="padding:0 6px">Ponto de partida: {brl(total())} (saldo livre + caixinhas) · aporte líquido de '
              f'{brl(S["cfg"]["renda"])}/mês · 100% do CDI a {cdi}% a.a. (bruto, estimativa).</div>')


def v_idea():
    ex = round(max(0.0, S["livre"] - RESERVA), 2)
    opc = [("Reserva de liquidez diária", 1.0 if ex < 50 else .4, "blue",
            "CDB ou RDB com liquidez diária pagando cerca de 100% do CDI. Dinheiro disponível para imprevistos."),
           ("RDB de longo prazo", .35, "pur",
            "Prazos de 2 a 5 anos costumam render acima do CDI. Boa para a meta de 2032; confira a cobertura do FGC."),
           ("Tesouro IPCA+", .25, "gold",
            "Rende inflação mais juros fixos e protege o poder de compra. Escolha vencimento próximo de 2032.")]
    if ex < 50:
        opc = opc[:1]
    sub = "Sugestão de divisão para esse valor:" if ex else f"Seu saldo livre precisa passar de {brl(RESERVA + 50)} para liberar sugestões."
    out = card("blue", "Excedente acima da reserva", brl(ex), sub)
    if ex:
        for nome, p, cor, txt in opc:
            out += (f'<div class="card" style="--c:var(--{cor})"><div class="al"><span class="lb">{nome}</span>'
                    f'<b style="color:var(--{cor})">{brl(ex * p)}</b></div><div class="k">{round(p * 100)}% · {txt}</div></div>')
    return out + '<div class="k" style="padding:0 6px">Sugestões educativas, não são recomendação personalizada. Menores investem com acompanhamento do responsável.</div>'


# ------------------------------------------------------------------ diálogos
@st.dialog("Novo lançamento")
def dlg_lancar():
    t = st.selectbox("O que aconteceu?", LANCAR, format_func=lambda k: TIPOS[k][0] + "  " + TIPOS[k][1])
    if t == "cfg":
        c = S["cfg"]
        nome = st.text_input("Nome da conta", S["nome"], max_chars=24)
        renda = st.number_input("Renda / aporte mensal (R$), entra todo dia 1", min_value=0.0, value=float(c["renda"]), step=50.0, format="%.2f")
        guard = st.number_input("Guardar automático na Caixinha Futuro (R$)", min_value=0.0, value=float(c["guardar"]), step=50.0, format="%.2f")
        gast = st.number_input("Gastos fixos mensais (R$)", min_value=0.0, value=float(c["gastos"]), step=10.0, format="%.2f")
        cdi = st.number_input("CDI estimado (% ao ano)", min_value=0.0, max_value=100.0, value=float(c["cdi"]), step=0.1, format="%.2f")
        st.caption(f"Ficam livres todo mês: {brl(renda - min(guard, renda))}")
        if st.button("Salvar", type="primary", use_container_width=True):
            S["nome"] = nome.strip() or S["nome"]
            S["cfg"] = {"renda": renda, "guardar": guard, "gastos": gast, "cdi": cdi}
            salvar()
            st.session_state["msg"] = "Configuração salva"
            st.rerun()
        return
    cx = None
    if t in ("save", "take", "yld"):
        ops = [k for k in CAIXAS if t == "save" or S["caixas"][k] > 0]
        if not ops:
            st.info("Nenhuma caixinha com saldo ainda. Guarde um valor primeiro.")
            return
        cx = st.selectbox("Caixinha", ops, format_func=lambda k: CAIXAS[k][0] + " · " + brl(S["caixas"][k]))
    v = st.number_input("Valor (R$)", min_value=0.0, value=0.0, step=0.10 if t == "yld" else 1.0, format="%.2f")
    if t == "yld" and cx:
        dia = S["caixas"][cx] * ((1 + S["cfg"]["cdi"] / 100) ** (1 / 252) - 1)
        st.caption(f"100% do CDI rende cerca de {brl(dia)} por dia útil nessa caixinha.")
    obs = st.text_input("Observação (opcional)", max_chars=40)
    if st.button("Confirmar", type="primary", use_container_width=True):
        erro = aplicar(t, v, cx, obs.strip())
        if erro:
            st.error(erro)
        else:
            st.rerun()


@st.dialog("🗑️ Excluir caixinha")
def dlg_excluir():
    ops = [k for k in CAIXAS if S["caixas"][k] > 0.004]
    if not ops:
        st.info("Nenhuma caixinha com saldo para excluir.")
        return
    cx = st.selectbox("Qual caixinha?", ops, format_func=lambda k: CAIXAS[k][0] + " · " + brl(S["caixas"][k]))
    modo = st.radio("O que fazer com o saldo?", ["Resgatar para o Saldo Livre", "Apenas zerar (sai do patrimônio)"])
    st.caption("O card some da tela principal e só reaparece quando houver novo aporte.")
    if st.button("Excluir caixinha", type="primary", use_container_width=True):
        excluir_caixinha(cx, modo.startswith("Resgatar"))
        st.rerun()


# ------------------------------------------------------------------ app
creditar_mes()

if st.session_state["msg"]:
    st.toast(st.session_state["msg"])
    st.session_state["msg"] = None


def _tema():
    st.session_state["tema"] = "light" if st.session_state["tema"] == "dark" else "dark"
    st.session_state["S"]["tema"] = st.session_state["tema"]
    salvar()


def _sair():
    sessoes().pop(st.query_params.get("s"), None)
    st.query_params.clear()
    for k in ("S", "auth", "aba"):
        st.session_state.pop(k, None)


st.button("☀️" if st.session_state["tema"] == "dark" else "🌙", key="b_tema", on_click=_tema, help="Alternar tema")
st.button("🔒", key="b_sair", on_click=_sair, help="Encerrar sessão")
if st.button("＋", key="fab_btn", help="Novo lançamento"):
    dlg_lancar()

with st.container(key="nav"):
    aba = st.radio("Navegação", ABAS, key="aba", horizontal=True, label_visibility="collapsed")
idx = ABAS.index(aba)
if idx != st.session_state["prev"]:
    st.session_state["dir"] = "R" if idx > st.session_state["prev"] else "L"
    st.session_state["prev"] = idx

st.markdown(f'<div class="hd"><div class="k">Olá,</div><h1>{html.escape(S["nome"])}</h1></div>', unsafe_allow_html=True)

with st.container(key=f"view_{idx}_from{st.session_state['dir']}"):
    st.markdown([v_home, v_ext, v_proj, v_idea][idx](), unsafe_allow_html=True)
    if idx == 0 and any(v > 0.004 for v in S["caixas"].values()):
        if st.button("🗑️ Excluir caixinha", key="b_del", use_container_width=True):
            dlg_excluir()
    if idx == 1:
        st.download_button("⬇️ Baixar tabela (CSV)", csv_extrato(), file_name=f"extrato_projeto18_{agora():%Y-%m-%d}.csv",
                           mime="text/csv", use_container_width=True, disabled=not S["extrato"])

if st.session_state["fx"]:
    st.markdown(fx_html(st.session_state["fx"]), unsafe_allow_html=True)
    st.session_state["fx"] = None
