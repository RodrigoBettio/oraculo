# -*- coding: utf-8 -*-
"""
Rotas FastAPI para o Amazon Kindle Paperwhite (E-Ink).
5 Páginas x 6 Ativos = 30 Ativos Monitorados da Carteira Real & Macroeconomia.
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Response
from investimentos.kindle_service import kindle_service

kindle_router = APIRouter(prefix="/api/v1/kindle", tags=["Kindle E-Ink"])


@kindle_router.get("/b3/ticker-page/{page_id}.png")
async def get_ticker_page_png(page_id: int):
    """
    Retorna uma imagem PNG em 8-bit escala de cinza (1072x1448) da página solicitada (1 a 5).
    Página 1: 6 FIIs
    Página 2: 6 Ações Brasil (Lote 1)
    Página 3: 6 Ações Brasil (Lote 2)
    Página 4: 6 BDRs
    Página 5: 6 Indicadores Macro
    """
    if page_id not in (1, 2, 3, 4, 5):
        raise HTTPException(status_code=400, detail="Page ID deve ser 1, 2, 3, 4 ou 5.")

    try:
        png_bytes = await kindle_service.render_page_png(page_id)
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=30",
                "X-Kindle-Page": str(page_id),
                "X-Generated-At": datetime.now().isoformat()
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao renderizar página do Kindle: {str(e)}")


@kindle_router.get("/crm/latest.epub")
async def get_crm_latest_epub():
    """
    Retorna o relatório executivo em EPUB focado 100% em FECHAMENTO IMEDIATO DE VENDAS.
    Contém apenas clientes com valor aberto (deal_value > 0) ou diagnóstico/reunião de fechamento.
    """
    try:
        epub_bytes = await kindle_service.generate_crm_daily_epub()
        filename = f"CRM_Fechamento_{datetime.now().strftime('%Y-%m-%d')}.epub"
        return Response(
            content=epub_bytes,
            media_type="application/epub+zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "public, max-age=300",
                "X-Generated-At": datetime.now().isoformat()
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar EPUB de fechamento: {str(e)}")


@kindle_router.get("/manifest")
async def get_kindle_manifest():
    """
    Manifesto com informações de sincronização, status do mercado e ativos monitorados.
    """
    now = datetime.now()
    is_open = (now.weekday() < 5) and (10 <= now.hour < 18)

    return {
        "device": "Kindle Paperwhite 3 (1072x1448)",
        "server_time": now.strftime("%d/%m/%Y %H:%M:%S"),
        "market_status": "ABERTO" if is_open else "FECHADO",
        "total_items": 30,
        "pages_count": 5,
        "items_per_page": 6,
        "structure": [
            "Página 1: 6 FIIs",
            "Página 2: 6 Ações Brasil (Lote 1)",
            "Página 3: 6 Ações Brasil (Lote 2)",
            "Página 4: 6 BDRs Globais",
            "Página 5: 6 Indicadores Macroeconômicos"
        ],
        "endpoints": {
            "ticker_pages": [f"/api/v1/kindle/b3/ticker-page/{i}.png" for i in range(1, 6)],
            "crm_latest_epub": "/api/v1/kindle/crm/latest.epub"
        }
    }
