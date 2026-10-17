"""
extrator.py — Lê um IFC exportado pelo TQS e devolve, para cada pilar, viga e laje,
a lista de barras de armadura que pertencem a ele.

Como a barra é associada ao elemento:
  O IFC do TQS NÃO liga a barra ao elemento (não há IfcRelAggregates/Connects).
  O "P11" no nome da barra é a POSIÇÃO da barra, não o pilar P11.
  Por isso a associação é GEOMÉTRICA: para cada barra, contamos quantos pontos
  da geometria dela caem dentro da caixa (bounding box) de cada elemento do
  tipo correspondente (a descrição da barra diz "pilares", "vigas" ou "lajes").
  O elemento com mais pontos é o dono da barra.

Uso pela linha de comando:
  python extrator.py arquivo.ifc "Nome da Obra"   -> gera arquivo.json
"""
import re, sys, json, unicodedata, datetime
from collections import defaultdict, Counter
import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as U

TIPOS = {"IfcColumn": "Pilar", "IfcBeam": "Viga", "IfcSlab": "Laje"}
# palavra na descrição da barra -> tipo de elemento
DESC_PARA_TIPO = {"pilar": "Pilar", "viga": "Viga", "laje": "Laje"}
TOL = 0.02          # tolerância em metros ao testar "ponto dentro da caixa"
RE_NOME = re.compile(r"^\s*(\d+)\s+(\S+)\s+(?:Ø|\\X\\D8|ø)?\s*([\d.,]+)\s+C\s*=\s*([\d.,]+)", re.I)


def slug(txt):
    txt = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "", txt).upper() or "OBRA"


def _num(s):
    return float(str(s).replace(",", "."))


def tipo_da_barra(desc):
    d = (desc or "").lower()
    for chave, tipo in DESC_PARA_TIPO.items():
        if chave in d:
            return tipo
    return None


def categoria_da_barra(desc):
    """Texto curto para o app: Longitudinal, Estribo, Negativa..."""
    d = (desc or "").lower()
    if "transversal" in d: return "Estribo"
    if "grampo" in d: return "Grampo"
    if "lateral" in d: return "Pele (lateral)"
    if "negativa" in d: return "Negativa"
    if "positiva" in d: return "Positiva"
    if "secund" in d: return "Secundária"
    if "compl" in d: return "Longitudinal compl."
    if "longitudinal" in d: return "Longitudinal"
    return desc or "?"


def secao(e, tipo):
    g = U.get_psets(e).get("TQS_Geometria", {})
    try:
        if tipo == "Pilar":
            return f"{g['Dimensao_b1']:g}x{g['Dimensao_h1']:g}"
        if tipo == "Viga":
            return f"{g['Largura']:g}x{g['Altura']:g}"
        if tipo == "Laje":
            if "Altura" in g:
                return f"h={g['Altura']:g}" + (f" ({g['Tipo']})" if g.get("Tipo") else "")
            if "Altura_Nervura" in g:   # laje treliçada/nervurada: nervura + capa
                h = g["Altura_Nervura"] + g.get("Capa", 0)
                return f"h={h:g} ({g.get('Tipo','nervurada')} {g['Altura_Nervura']:g}+{g.get('Capa',0):g})"
    except (KeyError, TypeError):
        pass
    return ""


def _densificar(verts, faces, passo=0.10):
    """Os vértices de uma barra ficam só nas pontas e dobras. Para saber por onde
    a barra PASSA, espalhamos pontos a cada `passo` metros ao longo das arestas."""
    if faces is None or not len(faces):
        return verts
    tri = faces.reshape(-1, 3)
    a = np.concatenate([tri[:, 0], tri[:, 1], tri[:, 2]])
    b = np.concatenate([tri[:, 1], tri[:, 2], tri[:, 0]])
    ar = np.unique(np.sort(np.stack([a, b], 1), axis=1), axis=0)
    p, q = verts[ar[:, 0]], verts[ar[:, 1]]
    L = np.linalg.norm(q - p, axis=1)
    longas = L > passo
    pts = [verts]
    for i in np.flatnonzero(longas):
        n = int(np.ceil(L[i] / passo))
        t = np.linspace(0, 1, n + 1)[1:-1, None]
        pts.append(p[i] + t * (q[i] - p[i]))
    return np.vstack(pts)


def _geometrias(f, entidades, progresso=None, etapa="", densificar=False):
    """Devolve {id_entidade: pontos (N,3) em coordenadas globais, metros}."""
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    it = ifcopenshell.geom.iterator(s, f, include=entidades, num_threads=4)
    out = {}
    total = len(entidades)
    if it.initialize():
        while True:
            sh = it.get()
            v = np.array(sh.geometry.verts).reshape(-1, 3)
            if densificar:
                v = _densificar(v, np.array(sh.geometry.faces))
            out[sh.id] = v
            if progresso and len(out) % 200 == 0:
                progresso(len(out) / max(total, 1), etapa)
            if not it.next():
                break
    return out


def _juntar_pedacos(barras, geo, tol=0.03):
    """Agrupa objetos IfcReinforcingBar que são pedaços da mesma barra física:
    mesmo nome + representação em superfície (IfcFaceBasedSurfaceModel) + caixas
    que se tocam. Barras em IfcSweptDiskSolid já vêm inteiras (1 objeto = 1 barra)."""
    def e_pedaco(b):
        try:
            return b.Representation.Representations[0].Items[0].is_a("IfcFaceBasedSurfaceModel")
        except (AttributeError, IndexError, TypeError):
            return False
    inteiras, por_nome = [], defaultdict(list)
    for b in barras:
        (por_nome[b.Name].append(b) if e_pedaco(b) and b.id() in geo else inteiras.append([b]))
    grupos = list(inteiras)
    for nome, L in por_nome.items():
        cx = [(geo[b.id()].min(0) - tol, geo[b.id()].max(0) + tol) for b in L]
        pai = list(range(len(L)))
        def raiz(i):
            while pai[i] != i:
                pai[i] = pai[pai[i]]; i = pai[i]
            return i
        for i in range(len(L)):
            for j in range(i + 1, len(L)):
                if np.all(cx[i][0] <= cx[j][1]) and np.all(cx[j][0] <= cx[i][1]):
                    pai[raiz(i)] = raiz(j)
        g = defaultdict(list)
        for i, b in enumerate(L):
            g[raiz(i)].append(b)
        grupos.extend(g.values())
    return grupos


def extrair(caminho_ifc, nome_obra, progresso=None):
    f = ifcopenshell.open(caminho_ifc)
    obra_id = slug(nome_obra)

    # ---------- 1. elementos (pilares, vigas, lajes) ----------
    objetos = []               # um por objeto IFC
    for classe, tipo in TIPOS.items():
        for e in f.by_type(classe):
            cont = U.get_container(e)
            objetos.append({"ent": e, "tipo": tipo, "nome": e.Name or "?",
                            "pav": cont.Name if cont else "?"})
    geo_el = _geometrias(f, [o["ent"] for o in objetos], progresso, "Lendo elementos")
    for o in objetos:
        v = geo_el.get(o["ent"].id())
        o["min"], o["max"] = (v.min(0), v.max(0)) if v is not None and len(v) else (None, None)
    objetos = [o for o in objetos if o["min"] is not None]

    # Agrupa objetos com mesmo tipo+nome+pavimento (o TQS divide vigas em trechos)
    grupos = {}
    for o in objetos:
        k = (o["tipo"], o["nome"], o["pav"])
        if k not in grupos:
            g0 = o["ent"].GlobalId
            grupos[k] = {
                "id": f"{o['nome']}-{g0}-{slug(o['pav'])}-{obra_id}",
                "obra_id": obra_id, "tipo": o["tipo"], "nome": o["nome"],
                "pavimento": o["pav"], "secao": secao(o["ent"], o["tipo"]),
                "guids": [], "_barras": [],
            }
        grupos[k]["guids"].append(o["ent"].GlobalId)
        o["grupo"] = grupos[k]

    # ---------- 2. barras ----------
    barras = f.by_type("IfcReinforcingBar")
    geo_b = _geometrias(f, barras, progresso, "Lendo barras", densificar=True)
    por_tipo = defaultdict(list)
    for o in objetos:
        por_tipo[o["tipo"]].append(o)
    caixas = {t: (np.array([o["min"] for o in L]) - TOL, np.array([o["max"] for o in L]) + TOL)
              for t, L in por_tipo.items()}

    # Algumas barras (ex.: negativas de viga) vêm do TQS EM PEDAÇOS: a reta e
    # cada gancho são objetos separados com o MESMO nome. Juntamos os pedaços
    # de mesmo nome que se tocam -> 1 barra física.
    fisicas = _juntar_pedacos(barras, geo_b)

    sem_dono, aproximadas = [], 0
    for grupo_b in fisicas:
        b = grupo_b[0]
        v = np.vstack([geo_b[x.id()] for x in grupo_b if x.id() in geo_b]) if any(x.id() in geo_b for x in grupo_b) else None
        tipo = tipo_da_barra(b.Description)
        info = {"nome_ifc": b.Name, "descricao": b.Description,
                "guids": [x.GlobalId for x in grupo_b]}
        if v is None or not len(v) or tipo not in caixas:
            sem_dono.append(info); continue
        mn, mx = caixas[tipo]
        dentro = ((v[None, :, :] >= mn[:, None, :]) & (v[None, :, :] <= mx[:, None, :])).all(2).sum(1)
        if dentro.max() > 0:
            cand = np.flatnonzero(dentro == dentro.max())
            vol = np.prod(mx[cand] - mn[cand], axis=1)
            idx = cand[np.argmin(vol)]
        else:  # nenhum ponto dentro: pega o elemento mais próximo (marcado como aproximado)
            c = (v.min(0) + v.max(0)) / 2
            d = np.linalg.norm(np.maximum(0, np.maximum(mn - c, c - mx)), axis=1)
            idx = int(np.argmin(d)); aproximadas += 1
            info["aproximada"] = True
        por_tipo[tipo][idx]["grupo"]["_barras"].append(info)

    # ---------- 3. resumo por elemento ----------
    elementos = []
    for g in grupos.values():
        cont = Counter()
        n_aprox = sum(1 for bi in g["_barras"] if bi.get("aproximada"))
        for bi in g["_barras"]:
            m = RE_NOME.match(bi["nome_ifc"] or "")
            if m:
                qtd, pos, bit, comp = int(m.group(1)), m.group(2), _num(m.group(3)), _num(m.group(4))
            else:
                qtd, pos, bit, comp = 1, "?", 0.0, 0.0
            cont[(pos, bit, comp, categoria_da_barra(bi["descricao"]))] += qtd
        def chave_pos(k):
            n = re.findall(r"\d+", k[0]); return (int(n[0]) if n else 9999, k[0], k[2])
        lista = [{"posicao": p, "bitola": b, "comprimento_cm": c, "tipo": t, "qtd": q}
                 for (p, b, c, t), q in sorted(cont.items(), key=lambda kv: chave_pos(kv[0]))]
        por_bit = Counter()
        for x in lista:
            por_bit[x["bitola"]] += x["qtd"]
        resumo = " + ".join(f"{q} ø{b:.1f}" for b, q in sorted(por_bit.items(), reverse=True))
        g.pop("_barras")
        g.update({"barras": lista, "n_barras": sum(por_bit.values()), "resumo": resumo,
                  "n_barras_aproximadas": n_aprox,
                  "status": "A CONFERIR", "conferido_por": None, "data_conferencia": None})
        elementos.append(g)

    ordem = {"Pilar": 0, "Viga": 1, "Laje": 2}
    def nat(s):
        n = re.findall(r"\d+", s); return (int(n[0]) if n else 0, s)
    elementos.sort(key=lambda e: (ordem[e["tipo"]], e["pavimento"], nat(e["nome"])))

    obra = {
        "id": obra_id, "nome": nome_obra,
        "arquivo_ifc": caminho_ifc.split("/")[-1],
        "data_upload": datetime.datetime.now().isoformat(timespec="seconds"),
        "n_pilares": sum(e["tipo"] == "Pilar" for e in elementos),
        "n_vigas": sum(e["tipo"] == "Viga" for e in elementos),
        "n_lajes": sum(e["tipo"] == "Laje" for e in elementos),
        "n_objetos_barra_ifc": len(barras),
        "n_barras_total": len(fisicas),
        "n_barras_sem_elemento": len(sem_dono),
        "n_barras_aproximadas": aproximadas,
    }
    return {"obra": obra, "elementos": elementos, "barras_sem_elemento": sem_dono}


if __name__ == "__main__":
    import time
    t = time.time()
    caminho = sys.argv[1]
    nome = sys.argv[2] if len(sys.argv) > 2 else "Obra"
    r = extrair(caminho, nome, progresso=lambda p, e: print(f"{e}: {p:.0%}", end="\r"))
    saida = caminho.rsplit(".", 1)[0] + ".json"
    with open(saida, "w", encoding="utf-8") as fh:
        json.dump(r, fh, ensure_ascii=False, indent=1)
    print("\n", json.dumps(r["obra"], ensure_ascii=False, indent=1))
    print(f"Salvo em {saida} ({time.time()-t:.0f}s)")
