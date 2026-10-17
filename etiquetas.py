"""
etiquetas.py — Gera o PDF com as etiquetas (QR code + dados) de cada elemento.
O QR guarda SOMENTE o ID único do elemento (ex.: P11-1MK9u0...-PRIMEIRO-CASAPD).
O aplicativo lê esse ID e busca o resto no Firebase.
"""
import io
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

COLS, ROWS = 2, 6
MARGEM_X, MARGEM_Y = 10 * mm, 12 * mm
CORES = {"Pilar": (0.10, 0.35, 0.70), "Viga": (0.10, 0.55, 0.30), "Laje": (0.75, 0.40, 0.05)}


def _qr(texto):
    img = qrcode.make(texto, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=1)
    buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
    return ImageReader(buf)


def _cortar(c, txt, fonte, tam, largura):
    while txt and c.stringWidth(txt, fonte, tam) > largura:
        txt = txt[:-2] + "…" if not txt.endswith("…") else txt[:-2] + "…"
    return txt


def _quebrar(c, txt, fonte, tam, largura, max_linhas):
    """Quebra o texto em até `max_linhas` linhas (separando nos ' + ')."""
    partes, linhas, atual = txt.split(" + "), [], ""
    for p in partes:
        teste = p if not atual else atual + " + " + p
        if c.stringWidth(teste, fonte, tam) <= largura:
            atual = teste
        else:
            linhas.append(atual + " +"); atual = p
    linhas.append(atual)
    if len(linhas) > max_linhas:
        linhas = linhas[:max_linhas]
        linhas[-1] = _cortar(c, linhas[-1].rstrip(" +") + " …", fonte, tam, largura)
    return linhas


def gerar_pdf(dados, destino=None):
    """dados = resultado de extrator.extrair(). Devolve os bytes do PDF
    (e grava em `destino`, se informado)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    lw = (W - 2 * MARGEM_X) / COLS
    lh = (H - 2 * MARGEM_Y) / ROWS
    obra = dados["obra"]["nome"]
    elementos = dados["elementos"]
    c.setTitle(f"Etiquetas - {obra}")

    for i, e in enumerate(elementos):
        k = i % (COLS * ROWS)
        if i and k == 0:
            c.showPage()
        col, lin = k % COLS, k // COLS
        x = MARGEM_X + col * lw
        y = H - MARGEM_Y - (lin + 1) * lh
        # borda tracejada (linha de corte)
        c.setDash(2, 2); c.setStrokeGray(0.6); c.setLineWidth(0.5)
        c.rect(x + 1.5 * mm, y + 1.5 * mm, lw - 3 * mm, lh - 3 * mm)
        c.setDash()
        # faixa colorida por tipo
        r, g, b = CORES.get(e["tipo"], (0.3, 0.3, 0.3))
        c.setFillColorRGB(r, g, b)
        c.rect(x + 1.5 * mm, y + 1.5 * mm, 3 * mm, lh - 3 * mm, stroke=0, fill=1)
        # QR
        q = lh - 10 * mm
        c.drawImage(_qr(e["id"]), x + 7 * mm, y + (lh - q) / 2, q, q)
        # textos
        tx = x + 9 * mm + q
        larg = lw - (tx - x) - 4 * mm
        top = y + lh - 10 * mm
        c.setFillColorRGB(r, g, b)
        c.setFont("Helvetica-Bold", 15)
        c.drawString(tx, top, f"{e['tipo'].upper()}: {e['nome']}")
        c.setFillGray(0)
        c.setFont("Helvetica", 9.5)
        c.drawString(tx, top - 13, _cortar(c, f"Seção: {e['secao'] or '-'}", "Helvetica", 9.5, larg))
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(tx, top - 25, _cortar(c, f"Pavimento: {e['pavimento']}", "Helvetica-Bold", 9.5, larg))
        c.setFont("Helvetica", 8)
        for j, linha in enumerate(_quebrar(c, f"{e['n_barras']} barras: {e['resumo']}", "Helvetica", 8, larg, 3)):
            c.drawString(tx, top - 37 - j * 10, linha)
        c.setFont("Helvetica-Oblique", 6.5); c.setFillGray(0.45)
        c.drawString(tx, y + 6 * mm, _cortar(c, f"Obra: {obra}", "Helvetica-Oblique", 6.5, larg))
        c.drawString(tx, y + 3.6 * mm, _cortar(c, e["id"], "Helvetica-Oblique", 6.5, larg))
        c.setFillGray(0)
    c.save()
    pdf = buf.getvalue()
    if destino:
        with open(destino, "wb") as fh:
            fh.write(pdf)
    return pdf
