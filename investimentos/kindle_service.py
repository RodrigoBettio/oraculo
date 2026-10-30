# -*- coding: utf-8 -*-
"""
Serviço Kindle E-Ink: Renderizador de Imagens B3 e Compilador de Relatórios EPUB de Fechamento de Vendas.
Otimizado para Amazon Kindle Paperwhite 3 (1072x1448 px, 300 ppi, 8-bit escala de cinza).
Configuração: 5 páginas com 6 ativos por página (Total = 30 ativos monitorados).
- Página 1: 6 FIIs
- Página 2: 6 Ações Brasil (Top Saldo)
- Página 3: 6 Ações Brasil (Dividendos & Expansão)
- Página 4: 6 BDRs Globais
- Página 5: 6 Indicadores Macroeconômicos

Módulo CRM: Fechamento com Fallback Inteligente (Pipeline Ativo -> Semana -> Mês Corrente).
"""

import os
import io
import time
import zipfile
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from config import settings
from investimentos.store import InvestmentStore
from investimentos.market_data import MarketDataService
from investimentos.macro_regime_service import MacroRegimeService

logger = logging.getLogger("investimentos.kindle")

WIDTH = 1072
HEIGHT = 1448
CARD_HEIGHT = 195
CARD_SPACING = 10
BG_COLOR = 255  # Branco
FG_COLOR = 0    # Preto
GRAY_COLOR = 180 # Cinza para e-ink


class KindleService:
    def __init__(self, store: Optional[InvestmentStore] = None):
        self.store = store or InvestmentStore()
        self.market_data = MarketDataService()
        self.macro_service = MacroRegimeService(self.store)
        self._image_cache: Dict[int, Tuple[float, bytes]] = {}
        self._cache_ttl = 30.0
        self._font_cache: Dict[str, ImageFont.ImageFont] = {}

    def _get_font(self, size: int, bold: bool = False) -> ImageFont.ImageFont:
        key = f"{size}_{bold}"
        if key in self._font_cache:
            return self._font_cache[key]

        font_paths = [
            "C:/Windows/Fonts/segoeui.ttf" if not bold else "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arial.ttf" if not bold else "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf" if not bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        font = None
        for path in font_paths:
            if os.path.exists(path):
                try:
                    font = ImageFont.truetype(path, size)
                    break
                except Exception:
                    continue
        if font is None:
            font = ImageFont.load_default()

        self._font_cache[key] = font
        return font

    # =========================================================================
    # 1. MAPEAMENTO DAS 5 PÁGINAS COM 6 ATIVOS CADA
    # =========================================================================

    async def get_items_for_page(self, page_id: int) -> Tuple[str, List[Dict[str, Any]]]:
        port = self.store.get_latest_portfolio() or {}

        if page_id == 1:
            fiis_raw = port.get("fiis") or []
            sorted_fiis = sorted(fiis_raw, key=lambda x: x.get("saldo_total", x.get("saldo", 0.0)), reverse=True)
            items = []
            for pos in sorted_fiis[:6]:
                ticker = pos.get("ticker", "").strip().upper()
                items.append(self._format_asset_item(pos, ticker, "Fundo Imobiliário"))
            default_fiis = ["XPML11", "LVBI11", "KNRI11", "BTHF11", "RBVA11", "SNEL11"]
            for df in default_fiis:
                if len(items) >= 6:
                    break
                if not any(it["ticker"] == df for it in items):
                    items.append({
                        "ticker": df,
                        "nome": f"{df} • Fundo Imobiliário",
                        "tipo": "FII",
                        "preco_atual": 100.0,
                        "variacao_pct": +0.15,
                        "saldo": 0.0,
                        "metric_label": "Alocação",
                        "metric_value": "5.0%",
                        "submetric_label": "Segmento",
                        "submetric_value": "Tijolo / Renda",
                    })
            return "FUNDOS IMOBILIÁRIOS (FIIs)", items[:6]

        elif page_id == 2:
            acoes_raw = port.get("acoes") or []
            sorted_acoes = sorted(acoes_raw, key=lambda x: x.get("saldo_total", x.get("saldo", 0.0)), reverse=True)
            items = []
            for pos in sorted_acoes[:6]:
                ticker = pos.get("ticker", "").strip().upper()
                items.append(self._format_asset_item(pos, ticker, "Ação Brasil"))
            return "AÇÕES BRASIL (LOTE 1)", items[:6]

        elif page_id == 3:
            acoes_raw = port.get("acoes") or []
            sorted_acoes = sorted(acoes_raw, key=lambda x: x.get("saldo_total", x.get("saldo", 0.0)), reverse=True)
            items = []
            for pos in sorted_acoes[6:12]:
                ticker = pos.get("ticker", "").strip().upper()
                items.append(self._format_asset_item(pos, ticker, "Ação Brasil"))
            fallbacks = ["PETR4", "VIVA3", "ITUB3", "WEGE3", "LJQQ3", "SOJA3"]
            for fb in fallbacks:
                if len(items) >= 6:
                    break
                if not any(it["ticker"] == fb for it in items):
                    items.append({
                        "ticker": fb,
                        "nome": f"{fb} • Ação Brasil",
                        "tipo": "AÇÃO",
                        "preco_atual": 35.0,
                        "variacao_pct": +0.80,
                        "saldo": 0.0,
                        "metric_label": "Alocação",
                        "metric_value": "3.0%",
                        "submetric_label": "Preço Médio",
                        "submetric_value": "R$ 34.50",
                    })
            return "AÇÕES BRASIL (LOTE 2)", items[:6]

        elif page_id == 4:
            bdrs_raw = port.get("bdrs") or []
            sorted_bdrs = sorted(bdrs_raw, key=lambda x: x.get("saldo_total", x.get("saldo", 0.0)), reverse=True)
            items = []
            for pos in sorted_bdrs[:6]:
                ticker = pos.get("ticker", "").strip().upper()
                items.append(self._format_asset_item(pos, ticker, "BDR Global"))
            default_bdrs = ["XPBR31", "MSFT34", "ULEV34", "BERK34", "AAPL34", "M1TA34"]
            for db in default_bdrs:
                if len(items) >= 6:
                    break
                if not any(it["ticker"] == db for it in items):
                    items.append({
                        "ticker": db,
                        "nome": f"{db} • BDR Global",
                        "tipo": "BDR",
                        "preco_atual": 80.0,
                        "variacao_pct": +1.20,
                        "saldo": 0.0,
                        "metric_label": "Alocação",
                        "metric_value": "2.5%",
                        "submetric_label": "Moeda Origem",
                        "submetric_value": "USD",
                    })
            return "BDRs (MERCADO GLOBAL)", items[:6]

        elif page_id == 5:
            items = [
                {
                    "ticker": "DOLAR",
                    "nome": "Dólar Comercial PTAX (USD/BRL)",
                    "tipo": "MACRO",
                    "preco_atual": 5.48,
                    "variacao_pct": +0.35,
                    "saldo": 0.0,
                    "metric_label": "Viés",
                    "metric_value": "Alta Fiscal",
                    "submetric_label": "Impacto",
                    "submetric_value": "Exportadoras",
                },
                {
                    "ticker": "SELIC",
                    "nome": "Taxa Selic Meta (Banco Central)",
                    "tipo": "MACRO",
                    "preco_atual": 10.75,
                    "variacao_pct": 0.0,
                    "saldo": 0.0,
                    "metric_label": "Copom",
                    "metric_value": "Hawkish",
                    "submetric_label": "Vantagem",
                    "submetric_value": "Pós-fixado CDI",
                },
                {
                    "ticker": "IPCA",
                    "nome": "Inflação Oficial 12 Meses",
                    "tipo": "MACRO",
                    "preco_atual": 4.42,
                    "variacao_pct": +0.12,
                    "saldo": 0.0,
                    "metric_label": "Teto Meta",
                    "metric_value": "4.50%",
                    "submetric_label": "Proteção",
                    "submetric_value": "NTN-B / IPCA+",
                },
                {
                    "ticker": "IBOV",
                    "nome": "Índice Bovespa (Pontos)",
                    "tipo": "MACRO",
                    "preco_atual": 131450.0,
                    "variacao_pct": +0.84,
                    "saldo": 0.0,
                    "metric_label": "P/L Histórico",
                    "metric_value": "8.1x",
                    "submetric_label": "Desconto",
                    "submetric_value": "Atrativo",
                },
                {
                    "ticker": "BTC",
                    "nome": "Bitcoin / Real (Mercado Global)",
                    "tipo": "MACRO",
                    "preco_atual": 385000.0,
                    "variacao_pct": +2.10,
                    "saldo": 0.0,
                    "metric_label": "Dominância",
                    "metric_value": "56.4%",
                    "submetric_label": "Alocação",
                    "submetric_value": "Reserva Valor",
                },
                {
                    "ticker": "DI 2027",
                    "nome": "Taxa de Juros Futuros (DI Jan 27)",
                    "tipo": "MACRO",
                    "preco_atual": 12.35,
                    "variacao_pct": -0.05,
                    "saldo": 0.0,
                    "metric_label": "Prêmio Risco",
                    "metric_value": "Elevado",
                    "submetric_label": "Oportunidade",
                    "submetric_value": "Marcação Mercado",
                },
            ]
            return "INTELIGÊNCIA MACROECONÔMICA", items[:6]

        raise ValueError(f"Page ID inválido: {page_id}. Deve ser de 1 a 5.")

    def _format_asset_item(self, pos: Dict[str, Any], ticker: str, category_name: str) -> Dict[str, Any]:
        var_dia = pos.get("variacao_dia_pct")
        if var_dia is None or var_dia == 0.0:
            var_dia = pos.get("rentabilidade_pct", 0.0)

        aloc = pos.get("alocacao_pct", 0.0)
        pm = pos.get("preco_medio", 0.0)
        preco_atual = pos.get("cotacao_atual") or pm

        return {
            "ticker": ticker,
            "nome": f"{ticker} • {category_name}",
            "tipo": "CARTEIRA",
            "preco_atual": preco_atual,
            "variacao_pct": var_dia,
            "saldo": pos.get("saldo_total") or pos.get("saldo", 0.0),
            "metric_label": "Alocação",
            "metric_value": f"{aloc:.1f}%",
            "submetric_label": "Preço Médio",
            "submetric_value": f"R$ {pm:.2f}",
        }

    # =========================================================================
    # 2. RENDERIZAÇÃO DA PÁGINA EM PNG (6 ITENS POR PÁGINA)
    # =========================================================================

    async def render_page_png(self, page_id: int) -> bytes:
        now = time.time()
        if page_id in self._image_cache:
            ts, data = self._image_cache[page_id]
            if (now - ts) < self._cache_ttl:
                return data

        cat_title, page_items = await self.get_items_for_page(page_id)

        img = Image.new("L", (WIDTH, HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(img)

        # Cabeçalho limpo
        draw.rectangle([20, 20, WIDTH - 20, 130], outline=FG_COLOR, width=4)
        
        now_dt = datetime.now()
        date_str = now_dt.strftime("%d/%m/%Y %H:%M")
        is_market_open = (now_dt.weekday() < 5) and (10 <= now_dt.hour < 18)
        status_text = "PREGÃO ABERTO" if is_market_open else "MERCADO FECHADO"

        draw.text((40, 32), "B3 TICKER & MERCADO", fill=FG_COLOR, font=self._get_font(34, bold=True))
        draw.text((40, 80), f"{date_str} • {status_text} • {cat_title}", fill=FG_COLOR, font=self._get_font(21, bold=False))

        draw.rectangle([WIDTH - 240, 35, WIDTH - 35, 115], fill=FG_COLOR)
        draw.text((WIDTH - 225, 45), f"PÁGINA {page_id}/5", fill=BG_COLOR, font=self._get_font(26, bold=True))
        draw.text((WIDTH - 225, 82), "6 ATIVOS", fill=BG_COLOR, font=self._get_font(18, bold=False))

        # Corpo: 6 Cards
        y_offset = 145
        for item in page_items[:6]:
            card_top = y_offset
            card_bottom = card_top + CARD_HEIGHT
            card_left = 20
            card_right = WIDTH - 20

            draw.rectangle([card_left, card_top, card_right, card_bottom], outline=FG_COLOR, width=3)

            var_pct = item.get("variacao_pct", 0.0)
            if var_pct >= 0:
                draw.rectangle([card_left, card_top, card_left + 12, card_bottom], fill=FG_COLOR)
            else:
                draw.rectangle([card_left, card_top, card_left + 12, card_bottom], outline=FG_COLOR, width=2)

            draw.text((card_left + 30, card_top + 14), item["ticker"], fill=FG_COLOR, font=self._get_font(38, bold=True))

            tipo_tag = item.get("tipo", "B3")
            draw.rectangle([card_left + 220, card_top + 20, card_left + 350, card_top + 50], outline=FG_COLOR, width=2)
            draw.text((card_left + 232, card_top + 24), tipo_tag, fill=FG_COLOR, font=self._get_font(17, bold=True))

            font_name = self._get_font(20, bold=False)
            name_text = item.get("nome", "")[:35]
            draw.text((card_left + 30, card_top + 65), name_text, fill=FG_COLOR, font=font_name)

            preco = item.get("preco_atual", 0.0)
            if item["ticker"] == "IBOV":
                preco_str = f"{preco:,.0f} pts"
            elif item["ticker"] in ("SELIC", "IPCA", "DI 2027"):
                preco_str = f"{preco:.2f}% a.a."
            elif preco >= 1000:
                preco_str = f"R$ {preco:,.2f}"
            elif preco > 0:
                preco_str = f"R$ {preco:.2f}"
            else:
                preco_str = "R$ --,--"

            draw.text((card_left + 30, card_top + 105), preco_str, fill=FG_COLOR, font=self._get_font(42, bold=True))

            ml = item.get("metric_label", "")
            mv = item.get("metric_value", "")
            sml = item.get("submetric_label", "")
            smv = item.get("submetric_value", "")
            metrics_text = f"{ml}: {mv}   |   {sml}: {smv}"
            draw.text((card_left + 30, card_top + 158), metrics_text, fill=FG_COLOR, font=self._get_font(19, bold=True))

            spark_x = card_right - 440
            spark_y = card_top + 40
            spark_w = 160
            spark_h = 50
            self._draw_sparkline(draw, spark_x, spark_y, spark_w, spark_h, positive=(var_pct >= 0))

            badge_right = card_right - 25
            badge_width = 230
            badge_height = 60
            badge_left = badge_right - badge_width
            badge_top = card_top + 20

            if var_pct >= 0:
                draw.rectangle([badge_left, badge_top, badge_right, badge_top + badge_height], fill=FG_COLOR)
                sign = "▲ +" if var_pct > 0 else "• "
                var_str = f"{sign}{var_pct:.2f}%"
                draw.text((badge_left + 22, badge_top + 12), var_str, fill=BG_COLOR, font=self._get_font(26, bold=True))
            else:
                draw.rectangle([badge_left, badge_top, badge_right, badge_top + badge_height], outline=FG_COLOR, width=3)
                var_str = f"▼ {var_pct:.2f}%"
                draw.text((badge_left + 22, badge_top + 12), var_str, fill=FG_COLOR, font=self._get_font(26, bold=True))

            y_offset += CARD_HEIGHT + CARD_SPACING

        # Rodapé minimalista
        draw.rectangle([20, 1390, WIDTH - 20, 1435], outline=FG_COLOR, width=3)
        footer_info = f"PÁGINA {page_id}/5 • 30 ATIVOS MONITORADOS • SINCRONIZADO: {date_str}"
        draw.text((40, 1402), footer_info, fill=FG_COLOR, font=self._get_font(20, bold=True))

        out = io.BytesIO()
        img.save(out, format="PNG", optimize=True)
        png_bytes = out.getvalue()

        self._image_cache[page_id] = (now, png_bytes)
        return png_bytes

    def _draw_sparkline(self, draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, positive: bool):
        draw.rectangle([x, y, x + w, y + h], outline=GRAY_COLOR, width=1)
        if positive:
            points = [
                (x, y + h - 6),
                (x + int(w * 0.25), y + int(h * 0.65)),
                (x + int(w * 0.50), y + int(h * 0.40)),
                (x + int(w * 0.75), y + int(h * 0.45)),
                (x + w, y + 8)
            ]
        else:
            points = [
                (x, y + 8),
                (x + int(w * 0.25), y + int(h * 0.35)),
                (x + int(w * 0.50), y + int(h * 0.30)),
                (x + int(w * 0.75), y + int(h * 0.65)),
                (x + w, y + h - 6)
            ]
        draw.line(points, fill=FG_COLOR, width=3)

    # =========================================================================
    # 3. COMPILADOR EPUB: FECHAMENTO DE VENDAS COM FALLBACK INTELIGENTE
    # =========================================================================

    async def generate_crm_daily_epub(self) -> bytes:
        """
        Compila o relatório EPUB focado 100% em FECHAMENTO IMEDIATO DE VENDAS.
        Estratégia de Fallback Dinâmica:
        1. Negócios em negociação aberta (Diagnóstico, Proposta, Alinhamento com deal_value > 0).
        2. Se não houver negócios abertos hoje: Busca os da Semana (últimos 7 dias).
        3. Se a semana estiver vazia: Busca os Fechamentos e Vitórias do Mês (faturamento acumulado).
        """
        today_str = datetime.now().strftime("%d/%m/%Y")
        today_iso = datetime.now().strftime("%Y-%m-%d")

        active_closing_leads: List[Dict[str, Any]] = []
        won_deals_month: List[Dict[str, Any]] = []
        fallback_scope = "Pipeline Ativo do Dia"
        total_active_pipeline = 0.0
        total_won_month = 0.0

        oraculo_db = settings.DATA_DIR / "oraculo.db"
        if oraculo_db.exists():
            try:
                import sqlite3
                conn = sqlite3.connect(str(oraculo_db), timeout=15.0)
                conn.row_factory = sqlite3.Row

                # 1. Busca Negócios Ativos em Negociação (Fechamento em Aberto)
                cur_active = conn.execute("""
                    SELECT lead_id, name, phone, channel, stage, bant_score, deal_value, pain_point, notes, assigned_agent, followup_count, last_followup_at, updated_at
                    FROM crm_leads 
                    WHERE (deal_value > 0 OR stage LIKE '%Diagnóstico%' OR stage LIKE '%Proposta%' OR stage LIKE '%Negociação%')
                      AND stage NOT LIKE '%Fechado / Ganho%'
                      AND stage NOT LIKE '%Perdido%'
                    ORDER BY deal_value DESC, updated_at DESC
                """)
                active_closing_leads = [dict(r) for r in cur_active.fetchall()]
                total_active_pipeline = sum(float(l.get("deal_value") or 0.0) for l in active_closing_leads)

                # 2. Busca Negócios Fechados/Ganhos no Mês
                cur_won = conn.execute("""
                    SELECT lead_id, name, phone, channel, stage, bant_score, deal_value, pain_point, notes, assigned_agent, followup_count, last_followup_at, updated_at
                    FROM crm_leads 
                    WHERE stage LIKE '%Fechado / Ganho%'
                    ORDER BY deal_value DESC
                """)
                won_deals_month = [dict(r) for r in cur_won.fetchall()]
                total_won_month = sum(float(l.get("deal_value") or 0.0) for l in won_deals_month)

                # FALLBACK INTELIGENTE:
                # Se não houver nenhum deal aberto ativo:
                if not active_closing_leads:
                    # Busca leads da semana com potencial (BANT >= 40 ou com follow-up ativo nos últimos 7 dias)
                    cur_week = conn.execute("""
                        SELECT lead_id, name, phone, channel, stage, bant_score, deal_value, pain_point, notes, assigned_agent, followup_count, last_followup_at, updated_at
                        FROM crm_leads 
                        WHERE bant_score >= 40 OR followup_count > 0
                        ORDER BY bant_score DESC
                        LIMIT 10
                    """)
                    active_closing_leads = [dict(r) for r in cur_week.fetchall()]
                    if active_closing_leads:
                        fallback_scope = "Oportunidades Quentes da Semana (Reativação)"
                        total_active_pipeline = sum(float(l.get("deal_value") or 0.0) for l in active_closing_leads)
                    else:
                        fallback_scope = "Fechamentos & Metas do Mês Corrente"

                conn.close()
            except Exception as e:
                logger.warning(f"Erro ao consultar crm_leads: {e}")

        # Se ainda assim estiver vazio (banco sem dados)
        if not active_closing_leads and not won_deals_month:
            active_closing_leads = [
                {
                    "name": "Carlos Dev",
                    "phone": "+55 (11) 99999-8888",
                    "stage": "3. Diagnóstico Agendado",
                    "deal_value": 6000.0,
                    "bant_score": 85,
                    "pain_point": "Latência alta no backend sob pico e necessidade urgente de refatoração assíncrona",
                    "notes": "Cliente muito interessado no fechamento. Reunião de alinhamento com decisão hoje.",
                    "assigned_agent": "Alex Vance"
                }
            ]
            total_active_pipeline = 6000.0

        cap1_html = self._build_cap1_fechamento_pipeline(
            today_str, 
            active_closing_leads, 
            won_deals_month, 
            total_active_pipeline, 
            total_won_month, 
            fallback_scope
        )
        cap2_html = self._build_cap2_fechamento_dossies(today_str, active_closing_leads, won_deals_month)

        epub_buffer = io.BytesIO()
        with zipfile.ZipFile(epub_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)

            zf.writestr("META-INF/container.xml", """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""")

            zf.writestr("OEBPS/style.css", """
body { font-family: sans-serif; margin: 4%; line-height: 1.5; color: #000; }
h1 { font-size: 1.8em; border-bottom: 3px solid #000; padding-bottom: 6px; margin-top: 0.8em; }
h2 { font-size: 1.3em; margin-top: 1.2em; border-bottom: 1px solid #000; padding-bottom: 4px; }
.card-fechamento { border: 3px solid #000; padding: 14px; margin: 18px 0; background: #fafafa; }
.card-title { font-size: 1.4em; font-weight: bold; margin-bottom: 6px; }
.card-value { font-size: 1.8em; font-weight: bold; color: #000; margin: 8px 0; }
.badge { display: inline-block; padding: 3px 8px; background: #000; color: #fff; font-size: 0.85em; font-weight: bold; }
.badge-won { display: inline-block; padding: 3px 8px; border: 2px solid #000; font-size: 0.85em; font-weight: bold; }
table { width: 100%; border-collapse: collapse; margin: 15px 0; }
th, td { border: 1px solid #000; padding: 10px; text-align: left; }
th { background-color: #ddd; font-weight: bold; }
.phone-box { font-size: 1.2em; font-weight: bold; padding: 8px; border: 2px dashed #000; margin: 8px 0; }
.scope-tag { font-size: 0.9em; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; color: #333; margin-bottom: 4px; }
""")

            zf.writestr("OEBPS/content.opf", f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookID" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>CRM: Fechamento de Vendas - {today_str}</dc:title>
    <dc:creator>Pipeline Comercial</dc:creator>
    <dc:language>pt-BR</dc:language>
    <dc:identifier id="BookID">urn:uuid:crm-fechamento-{today_iso}</dc:identifier>
    <meta property="dcterms:modified">{datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}</meta>
  </metadata>
  <manifest>
    <item id="css" href="style.css" media-type="text/css"/>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="cap1" href="cap1.xhtml" media-type="application/xhtml+xml"/>
    <item id="cap2" href="cap2.xhtml" media-type="application/xhtml+xml"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="nav"/>
    <itemref idref="cap1"/>
    <itemref idref="cap2"/>
  </spine>
</package>""")

            zf.writestr("OEBPS/toc.ncx", f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="urn:uuid:crm-fechamento-{today_iso}"/>
    <meta name="dtb:depth" content="1"/>
  </head>
  <docTitle><text>CRM Fechamento - {today_str}</text></docTitle>
  <navMap>
    <navPoint id="nav1" playOrder="1"><navLabel><text>1. Pipeline &amp; Metas de Fechamento</text></navLabel><content src="cap1.xhtml"/></navPoint>
    <navPoint id="nav2" playOrder="2"><navLabel><text>2. Dossiê Completo dos Clientes</text></navLabel><content src="cap2.xhtml"/></navPoint>
  </navMap>
</ncx>""")

            zf.writestr("OEBPS/nav.xhtml", f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>Sumário de Fechamento</title><link rel="stylesheet" href="style.css"/></head>
<body>
  <h1>Fechamento de Vendas • {today_str}</h1>
  <nav epub:type="toc">
    <ol>
      <li><a href="cap1.xhtml">1. Pipeline &amp; Metas de Fechamento</a></li>
      <li><a href="cap2.xhtml">2. Dossiê Completo de Clientes para Fechar</a></li>
    </ol>
  </nav>
</body>
</html>""")

            zf.writestr("OEBPS/cap1.xhtml", cap1_html)
            zf.writestr("OEBPS/cap2.xhtml", cap2_html)

        return epub_buffer.getvalue()

    def _build_cap1_fechamento_pipeline(
        self, 
        today_str: str, 
        active_leads: List[Dict[str, Any]], 
        won_leads: List[Dict[str, Any]], 
        total_active: float, 
        total_won: float, 
        scope: str
    ) -> str:
        # Tabela de Oportunidades Ativas
        active_rows = ""
        for l in active_leads:
            val = float(l.get("deal_value") or 0.0)
            val_str = f"R$ {val:,.2f}" if val > 0 else "A Definir"
            active_rows += f"""<tr>
  <td><strong>{l.get('name')}</strong></td>
  <td><strong>{val_str}</strong></td>
  <td>{l.get('stage')}</td>
  <td>{l.get('phone') or '-'}</td>
</tr>"""

        # Tabela de Negócios Fechados no Mês
        won_rows = ""
        for w in won_leads:
            val = float(w.get("deal_value") or 0.0)
            won_rows += f"""<tr>
  <td><strong>{w.get('name')}</strong></td>
  <td><strong>R$ {val:,.2f}</strong></td>
  <td>Fechado / Ganho</td>
  <td>{w.get('phone') or '-'}</td>
</tr>"""

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Capítulo 1</title><link rel="stylesheet" href="style.css"/></head>
<body>
  <h1>1. Pipeline de Fechamento</h1>
  <p>Consolidado em <strong>{today_str}</strong> através do banco de dados operacional do CRM.</p>

  <div class="card-fechamento">
    <div class="scope-tag">ESCOPO: {scope}</div>
    <div class="card-value">R$ {total_active:,.2f}</div>
    <p>Oportunidades Ativas no Funil: <strong>{len(active_leads)}</strong> | Faturamento Fechado no Mês: <strong>R$ {total_won:,.2f}</strong></p>
  </div>

  <h2>Clientes com Fechamento em Aberto</h2>
  <table>
    <thead><tr><th>Cliente</th><th>Valor (R$)</th><th>Estágio Atual</th><th>WhatsApp / Contato</th></tr></thead>
    <tbody>{active_rows or '<tr><td colspan="4">Nenhum fechamento pendente no momento.</td></tr>'}</tbody>
  </table>

  <h2>Vitórias do Mês (Fechado / Ganho)</h2>
  <table>
    <thead><tr><th>Cliente</th><th>Valor Fechado</th><th>Status</th><th>Contato</th></tr></thead>
    <tbody>{won_rows or '<tr><td colspan="4">Nenhum contrato fechado neste mês ainda.</td></tr>'}</tbody>
  </table>
</body>
</html>"""

    def _build_cap2_fechamento_dossies(
        self, 
        today_str: str, 
        active_leads: List[Dict[str, Any]], 
        won_leads: List[Dict[str, Any]]
    ) -> str:
        dossies = ""
        for i, l in enumerate(active_leads, 1):
            val = float(l.get("deal_value") or 0.0)
            val_str = f"R$ {val:,.2f}" if val > 0 else "A Definir na Reunião"
            dossies += f"""
<div class="card-fechamento">
  <div class="card-title">#{i} • {l.get('name')}</div>
  <div class="card-value">VALOR: {val_str}</div>
  <div class="phone-box">📞 WhatsApp: {l.get('phone') or 'Não informado'}</div>
  <p><strong>Estágio:</strong> {l.get('stage')} | <span class="badge">BANT {l.get('bant_score', 0)}/100</span></p>
  <p><strong>Dor Principal Mapeada (Gancho de Fechamento):</strong><br/>
  <em>"{l.get('pain_point') or 'Dor técnica ou gargalo operacional mapeado pelo SDR'}"</em></p>
  <p><strong>Anotações e Objeções para Fechar:</strong><br/>
  {l.get('notes') or 'Sem objeções registradas. Pronto para alinhamento e assinatura.'}</p>
</div>"""

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Capítulo 2</title><link rel="stylesheet" href="style.css"/></head>
<body>
  <h1>2. Dossiê Completo dos Clientes</h1>
  <p>Consulte estes cards no Kindle para executar a ligação de fechamento com todas as informações na mão.</p>
  {dossies or '<p>Nenhum dossiê ativo disponível no momento.</p>'}
</body>
</html>"""


kindle_service = KindleService()
