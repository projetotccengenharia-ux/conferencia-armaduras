"""
exportar.py — Gera a planilha Excel (relatório) a partir dos dados extraídos
ou lidos do Firebase. Abas: Resumo, Elementos, Barras.
"""
import io
import pandas as pd


def gerar_excel(dados, destino=None):
    o = dados["obra"]
    els = dados["elementos"]
    resumo = pd.DataFrame([
        ("Obra", o["nome"]), ("ID da obra", o["id"]), ("Arquivo IFC", o.get("arquivo_ifc", "")),
        ("Data de upload", o.get("data_upload", "")), ("Pilares", o.get("n_pilares")),
        ("Vigas", o.get("n_vigas")), ("Lajes", o.get("n_lajes")),
        ("Barras (físicas)", o.get("n_barras_total")),
        ("Barras sem elemento", o.get("n_barras_sem_elemento")),
        ("Barras associadas por proximidade", o.get("n_barras_aproximadas")),
        ("Conferidos", sum(e.get("status") == "CONFERIDO" for e in els)),
    ], columns=["Item", "Valor"])
    elementos = pd.DataFrame([{
        "ID_Unico": e["id"], "Tipo": e["tipo"], "Nome": e["nome"], "Pavimento": e["pavimento"],
        "Seção": e["secao"], "Nº barras": e["n_barras"], "Armadura (resumo)": e["resumo"],
        "Status": e.get("status"), "Conferido por": e.get("conferido_por"),
        "Data conferência": e.get("data_conferencia"),
    } for e in els])
    barras = pd.DataFrame([{
        "ID_Unico": e["id"], "Tipo elemento": e["tipo"], "Elemento": e["nome"],
        "Pavimento": e["pavimento"], "Posição": b["posicao"], "Bitola (mm)": b["bitola"],
        "Comprimento (cm)": b["comprimento_cm"], "Tipo barra": b["tipo"], "Quantidade": b["qtd"],
    } for e in els for b in e["barras"]])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for nome, df in (("Resumo", resumo), ("Elementos", elementos), ("Barras", barras)):
            df.to_excel(xw, sheet_name=nome, index=False)
            ws = xw.sheets[nome]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for col in ws.columns:
                w = max(len(str(c.value or "")) for c in col[:300])
                ws.column_dimensions[col[0].column_letter].width = min(max(10, w + 2), 60)
    data = buf.getvalue()
    if destino:
        with open(destino, "wb") as fh:
            fh.write(data)
    return data
