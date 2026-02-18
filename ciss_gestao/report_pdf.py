from io import BytesIO
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.graphics.shapes import Drawing, Rect, String, Path, Circle
import os
import re
import unicodedata
from io import BytesIO
from urllib.parse import urlparse
from urllib.request import urlopen, build_opener, ProxyHandler
from urllib.error import URLError, HTTPError
from django.conf import settings
from django.core.files.storage import default_storage

def build_campaign_report_pdf(report_context: dict) -> bytes:
    """
    Build the campaign report PDF with ReportLab.
    This is a minimal layout scaffold that can be expanded as the report evolves.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=14 * mm,
        title="Relatorio de Saude Organizacional",
    )
    doc.width = doc.pagesize[0] - doc.leftMargin - doc.rightMargin
    doc.height = doc.pagesize[1] - doc.topMargin - doc.bottomMargin

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        alignment=1,
        fontSize=14,
        spaceAfter=10,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        alignment=1,
        fontSize=10,
        textColor=colors.HexColor("#475569"),
        spaceAfter=6,
    )
    section_style = ParagraphStyle(
        "ReportSection",
        parent=styles["Heading2"],
        fontSize=11,
        spaceBefore=12,
        spaceAfter=6,
    )
    section_caps_style = ParagraphStyle(
        "ReportSectionCaps",
        parent=styles["Heading2"],
        fontSize=11,
        spaceBefore=10,
        spaceAfter=6,
    )
    sub_section_style = ParagraphStyle(
        "ReportSubSection",
        parent=styles["Heading3"],
        fontSize=10,
        spaceBefore=8,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        fontSize=9.5,
        leading=13,
    )
    label_style = ParagraphStyle(
        "ReportLabel",
        parent=styles["BodyText"],
        fontSize=8.5,
        textColor=colors.HexColor("#64748b"),
    )
    small_style = ParagraphStyle(
        "ReportSmall",
        parent=styles["BodyText"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#64748b"),
    )

    def add_section_header(number, title):
        badge = Drawing(18, 18)
        badge.add(Circle(9, 9, 9, fillColor=colors.HexColor("#1d4ed8"), strokeColor=None))
        badge.add(String(9, 5.5, str(number), fontName="Helvetica-Bold", fontSize=9, fillColor=colors.white, textAnchor="middle"))
        header = Table(
            [[
                badge,
                Paragraph(title, ParagraphStyle(f"SectionTitle{number}", parent=section_style, alignment=0, fontSize=12, spaceAfter=0)),
            ]],
            colWidths=[22, doc.width - 22],
            hAlign="LEFT",
        )
        header.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        story.append(header)
        story.append(Spacer(1, 4))
        story.append(Table([[""]], colWidths=[doc.width], rowHeights=[2], style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1d4ed8"))])))
        story.append(Spacer(1, 6))

    def zone_color(percent):
        if percent >= 75:
            return colors.HexColor("#22c55e")
        if percent >= 40:
            return colors.HexColor("#f59e0b")
        return colors.HexColor("#ef4444")

    def normalize_zone_label(zone):
        if not zone:
            return "Sem dados"
        zone_text = str(zone).strip()
        zone_upper = zone_text.upper()
        zone_ascii = "".join(
            ch for ch in unicodedata.normalize("NFKD", zone_upper) if not unicodedata.combining(ch)
        )
        zone_ascii = re.sub(r"[^A-Z]", "", zone_ascii)
        if zone_ascii.startswith("ATEN") and zone_ascii.endswith("AO"):
            return "ATENÇÃO"
        if "BOM" in zone_ascii:
            return "BOM"
        if "RUIM" in zone_ascii:
            return "RUIM"
        return zone_text

    def make_bar(percent, width, height, fill_color, label_text=None, show_container=True):
        d = Drawing(width, height)
        radius = max(0, height / 2)

        def rounded_rect(x, y, w, h, r, fill, stroke):
            r = min(r, w / 2, h / 2)
            p = Path()
            p.moveTo(x + r, y)
            p.lineTo(x + w - r, y)
            p.curveTo(x + w, y, x + w, y, x + w, y + r)
            p.lineTo(x + w, y + h - r)
            p.curveTo(x + w, y + h, x + w, y + h, x + w - r, y + h)
            p.lineTo(x + r, y + h)
            p.curveTo(x, y + h, x, y + h, x, y + h - r)
            p.lineTo(x, y + r)
            p.curveTo(x, y, x, y, x + r, y)
            p.closePath()
            p.fillColor = fill
            p.strokeColor = stroke
            return p

        if show_container:
            d.add(rounded_rect(0, 0, width, height, radius, colors.HexColor("#e2e8f0"), colors.HexColor("#cbd5e1")))
        fill_width = max(0, min(width, width * (percent / 100.0)))
        if fill_width > 0:
            fill_radius = min(radius, fill_width / 2)
            d.add(rounded_rect(0, 0, fill_width, height, fill_radius, fill_color, None))
        if label_text:
            d.add(
                String(
                    width / 2,
                    height / 2 - 3,
                    label_text,
                    fontName="Helvetica-Bold",
                    fontSize=7,
                    fillColor=colors.HexColor("#0f172a"),
                    textAnchor="middle",
                )
            )
        return d

    def make_checkbox(checked):
        d = Drawing(10, 10)
        d.add(Rect(0, 0, 10, 10, strokeColor=colors.HexColor("#94a3b8"), fillColor=colors.white))
        if checked:
            d.add(String(5, 2.5, "✓", fontName="Helvetica-Bold", fontSize=8, fillColor=colors.HexColor("#16a34a"), textAnchor="middle"))
        return d


    def chunk_list(items, size):
        if size <= 0:
            return [items]
        return [items[i:i + size] for i in range(0, len(items), size)]


    def graph_separator():
        line = Table([[""]], colWidths=[doc.width])
        line.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.6, colors.HexColor("#e2e8f0"))]))
        return line

    def make_card(flowables, width):
        card = Table([[flowables]], colWidths=[width])
        card.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#e2e8f0")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ffffff")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        return card

    story = []

    company_logo = (report_context.get("company_logo") or "").strip()
    if company_logo:
        try:
            logo_img = None
            if os.path.exists(company_logo):
                logo_img = Image(company_logo)
            else:
                with default_storage.open(company_logo, "rb") as logo_handle:
                    logo_img = Image(BytesIO(logo_handle.read()))
            if logo_img is not None:
                max_width = doc.width * 0.34
                max_height = 22 * mm
                img_width, img_height = logo_img.imageWidth, logo_img.imageHeight
                if img_width and img_height:
                    scale = min(max_width / img_width, max_height / img_height, 1.0)
                    logo_img.drawWidth = img_width * scale
                    logo_img.drawHeight = img_height * scale
                logo_img.hAlign = "CENTER"
                story.append(logo_img)
                story.append(Spacer(1, 6))
        except Exception:
            pass

    story.append(Paragraph("RELATÓRIO DE SAÚDE ORGANIZACIONAL", title_style))
    story.append(
        Paragraph(
            "Avaliação ergonômica preliminar dos fatores riscos psicossociais relacionados ao ambiente de trabalho",
            subtitle_style,
        )
    )
    story.append(Paragraph("AEP-FRPRT NR01/HSE-SIT-UK", subtitle_style))
    story.append(Spacer(1, 6))

    company_name = report_context.get("company_name", "-")
    company_cnpj = report_context.get("company_cnpj", "-")
    company_address = report_context.get("company_address", "-")
    company_cnae = report_context.get("company_cnae", "-")
    company_risk = report_context.get("company_risk", "-")
    ghes = report_context.get("company_ghes", "-")
    company_group_list_label = report_context.get("company_group_list_label", "GHEs")
    company_group_list = report_context.get("company_group_list", ghes)
    responses_count = report_context.get("responses_count", "-")
    evaluation_date = report_context.get("evaluation_date", "-")

    story.append(Paragraph("RELATÓRIO DE FATORES RISCOS PSICOSSOCIAIS RELACIONADOS AO TRABALHO (FRPRT)", section_style))
    story.append(Paragraph("AVALIAÇÃO ERGONÔMICA PRELIMINAR (AEP)", section_style))
    story.append(Paragraph("NR-1. NR-17, GUIA DE FATORES PSICOSSOCIAIS HSE-SIT-UK", body_style))
    story.append(Spacer(1, 6))

    story.append(PageBreak())
    story.append(Paragraph("SUMARIO", section_style))
    summary_items = [
        (1, "IDENTIFICAÇÃO"),
        (2, "OBJETIVO"),
        (3, "METODOLOGIA"),
        (4, "IMPORTÂNCIA DA PARTICIPAÇÃO DOS TRABALHADORES"),
        (5, "RESULTADOS GERAIS"),
        (6, "CONCLUSÕES E RECOMENDAÇÕES PRELIMINARES"),
        (7, "LIMITAÇÕES"),
        (8, "RESPONSABILIDADES"),
        (9, "ANEXOS"),
    ]
    for number, title in summary_items:
        badge = Drawing(14, 14)
        badge.add(Circle(7, 7, 7, fillColor=colors.HexColor("#1d4ed8"), strokeColor=None))
        badge.add(String(7, 4.5, str(number), fontName="Helvetica-Bold", fontSize=7, fillColor=colors.white, textAnchor="middle"))
        row = Table(
            [[badge, Paragraph(title, body_style)]],
            colWidths=[18, doc.width - 18],
            hAlign="LEFT",
        )
        row.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(row)
    story.append(Spacer(1, 6))
    story.append(PageBreak())

    add_section_header(1, "IDENTIFICAÇÃO")
    story.append(Paragraph(f"<b>Empresa:</b> {company_name}", body_style))
    story.append(Paragraph(f"<b>CNPJ:</b> {company_cnpj}", body_style))
    story.append(Paragraph(f"<b>Endereço:</b> {company_address}", body_style))
    story.append(Paragraph(f"<b>CNAE:</b> {company_cnae}", body_style))
    story.append(Paragraph(f"<b>Classe de risco:</b> {company_risk}", body_style))
    story.append(Paragraph(f"<b>{company_group_list_label} avaliados:</b> {company_group_list}", body_style))
    story.append(Paragraph(f"<b>Número de trabalhadores avaliados:</b> {responses_count}", body_style))
    story.append(Paragraph(f"<b>Data da avaliação:</b> {evaluation_date}", body_style))
    story.append(Paragraph("<b>Reavaliação recomendada:</b> 3 meses", body_style))
    story.append(Spacer(1, 6))

    story.append(
        Paragraph(
            "1.1 Responsáveis técnicos pela ferramenta de avaliação FRPRT",
            ParagraphStyle(
                "SectionSubBlue",
                parent=section_style,
                textColor=colors.HexColor("#1e3a8a"),
            ),
        )
    )
    tech_rows = [["Nome", "Formação", "Registro"]]
    tech_entries = report_context.get("technical_responsibles") or []
    if tech_entries:
        for item in tech_entries:
            tech_rows.append(
                [
                    item.get("name") or "-",
                    item.get("education") or "-",
                    item.get("registration") or "-",
                ]
            )
    else:
        tech_rows.append(["Nenhum responsavel tecnico informado.", "", ""])
    tech_table = Table(
        tech_rows,
        colWidths=[doc.width * 0.36, doc.width * 0.44, doc.width * 0.20],
        hAlign="LEFT",
    )

    tech_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ]
        )
    )
    story.append(tech_table)

    story.append(PageBreak())
    add_section_header(2, "OBJETIVO")
    story.append(
        Paragraph(
            "Esta Avaliação Ergonômica Preliminar (AEP) tem por finalidade identificar e examinar tecnicamente os "
            "fatores de riscos psicossociais existentes no contexto de trabalho, que possam contribuir para o estresse "
            "ocupacional e afetar a saúde, o bem-estar e o desempenho dos colaboradores. O presente relatório encontra-se "
            "em plena conformidade com a NR-17 e a NR-1 (GRO e PGR), observando o Guia de Informações sobre Fatores de "
            "Riscos Psicossociais Relacionados ao Trabalho (MTE) e as diretrizes do HSE-SIT-UK, assegurando alinhamento "
            "com as melhores práticas nacionais e internacionais em saúde e segurança do trabalho. Além de atender às "
            "exigências legais, este AEP-FRPRT fornece fundamentos técnicos consistentes para subsidiar decisões quanto "
            "à necessidade de aprofundamento por meio da Análise Ergonômica do Trabalho (AET), à priorização de medidas "
            "de controle e à definição de planos de ação integrados ao PGR, com o propósito de promover ambientes laborais "
            "mais seguros, saudáveis e produtivos.",
            body_style,
        )
    )

    story.append(PageBreak())
    add_section_header(3, "METODOLOGIA")
    story.append(
        Paragraph(
            "Para a condução desta Avaliação Ergonômica Preliminar (AEP), foi empregado o Stress Indicator Tool "
            "(SIT), instrumento de avaliação psicossocial reconhecido internacionalmente e validado pelo Health and "
            "Safety Executive (HSE) do Reino Unido (UK), devidamente adaptado à realidade organizacional brasileira, "
            "em conformidade com as disposições da NR-01, da NR-07 e do Guia de Fatores Psicossociais Relacionados ao "
            "Trabalho, elaborado pelo Ministério do Trabalho e Emprego (MTE).",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "O instrumento é composto por 35 questões estruturadas, organizadas nos domínios Demandas, Controle, "
            "Apoio, Relacionamentos, Papel e Mudanças, reconhecidos pela literatura científica e pelas normas "
            "técnicas como fatores determinantes relevantes para a saúde mental e o bem-estar dos trabalhadores.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "A aplicação da metodologia permite a realização de uma análise técnica detalhada dos fatores críticos "
            "presentes no ambiente laboral, contemplando as seguintes etapas:",
            body_style,
        )
    )

    story.append(Paragraph("• Realização de coleta estruturada e sigilosa das percepções dos trabalhadores, garantindo confidencialidade e confiabilidade das respostas;", body_style))
    story.append(Paragraph("• Classificação, consolidação e análise estatística das informações obtidas, possibilitando a identificação de áreas sensíveis e pontos prioritários de intervenção;", body_style))
    story.append(Paragraph("• Avaliação técnica dos resultados em conformidade com a legislação vigente e com as melhores práticas nacionais e internacionais de Saúde e Segurança do Trabalho, assegurando a rastreabilidade dos dados e subsidiando a elaboração de ações integradas ao GRO e ao PGR.", body_style))

    story.append(
        Paragraph(
            "A utilização do Stress Indicator Tool (SIT) neste processo permite a identificação estruturada e confiável "
            "dos riscos psicossociais existentes no ambiente laboral, configurando-se como base para a definição e "
            "priorização de medidas preventivas e corretivas, além de possibilitar o acompanhamento contínuo da "
            "evolução das condições psicossociais ao longo do tempo.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "Ressalta-se que o SIT é uma das ferramentas indicadas pelo Health and Safety Executive (HSE-UK), "
            "em virtude de sua efetividade na coleta estruturada e objetiva das percepções dos trabalhadores. "
            "Cabe destacar que os resultados obtidos refletem a percepção dos colaboradores em um contexto "
            "e período específicos, o que reforça a importância de reavaliações periódicas, em alinhamento "
            "com o ciclo de monitoramento previsto no GRO e no PGR.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "A eficácia da metodologia adotada está diretamente vinculada ao comprometimento institucional e à "
            "participação ativa dos trabalhadores ao longo de todo o processo, considerando que são os próprios "
            "colaboradores que vivenciam as rotinas laborais e detêm a experiência prática necessária para fornecer "
            "informações confiáveis e relevantes sobre os fatores que influenciam sua saúde, bem-estar e desempenho.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "Adicionalmente, a metodologia empregada favorece a promoção de ambientes laborais mais seguros, "
            "equilibrados e produtivos, permitindo que a organização atue de forma preventiva, estruturada e "
            "sistematizada na gestão dos fatores psicossociais relacionados ao trabalho, em conformidade com a "
            "legislação brasileira vigente e com os referenciais internacionais de gestão em saúde e segurança ocupacional.",
            body_style,
        )
    )

    story.append(Paragraph("Selecionando uma amostra", sub_section_style))
    story.append(
        Paragraph(
            "Há várias questões a serem consideradas na seleção de uma população de pesquisa:",
            body_style,
        )
    )

    story.append(Paragraph("• Quais listas de trabalhadores podem ser utilizadas;", body_style))
    story.append(Paragraph("• Quantos trabalhadores devem compor a amostra; e", body_style))
    story.append(Paragraph("• Como selecionar a amostra de trabalhadores.", body_style))

    story.append(Paragraph("Lista de trabalhadores", sub_section_style))
    story.append(
        Paragraph(
            "Ao selecionar uma amostra de trabalhadores — ou mesmo a totalidade dos colaboradores da organização — "
            "é fundamental assegurar a disponibilidade de uma lista atualizada dos participantes incluídos na pesquisa. "
            "Essa relação pode ser obtida por meio da folha de pagamento, cadastros de empregados, registros de segurança "
            "ou outras fontes equivalentes. É imprescindível que a lista utilizada esteja correta e atualizada, a fim de "
            "garantir que todos os integrantes da amostra recebam o questionário. Tal cuidado contribui para o aumento da "
            "taxa de resposta e para a confiabilidade dos resultados obtidos.",
            body_style,
        )
    )

    story.append(Paragraph("Tamanho mínimo de amostra recomendado", sub_section_style))
    story.append(
        Paragraph(
            "A realização de uma pesquisa envolvendo todos os colaboradores tende a proporcionar um retrato mais fiel "
            "da realidade organizacional do que a utilização de uma amostra. Por outro lado, optar pelo tamanho mínimo "
            "de amostra recomendado apresenta como benefícios a redução de custos e a diminuição do tempo demandado "
            "pela equipe. Os quantitativos mínimos foram definidos de modo a assegurar que os resultados obtidos sejam "
            "estatisticamente representativos das percepções do conjunto de trabalhadores da organização.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "A adoção de uma amostra ampliada possibilita análises mais aprofundadas de subgrupos "
            "(como por categoria profissional) e amplia a oportunidade para que um número maior de "
            "colaboradores manifeste suas percepções. Em contrapartida, essa escolha pode implicar "
            "maior investimento de tempo e recursos para sua execução.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "Os tamanhos de amostra recomendados são fornecidos na tabela abaixo:",
            body_style,
        )
    )
    sample_table = Table(
        [
            ["Número total de trabalhadores", "Tamanho de amostra recomendado"],
            ["<= 500", "Todos os funcionários"],
            ["501 - 1.000", "500 respostas"],
            ["1.001 - 2.000", "650 respostas"],
            ["2.001 - 3.000", "700 respostas"],
            ["> 3.000", "800 respostas"],
        ],
        colWidths=[doc.width * 0.55, doc.width * 0.45],
        hAlign="LEFT",
    )
    sample_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ]
        )
    )
    story.append(sample_table)
    story.append(
        Paragraph(
            "Referência: Northumberland, Tyne and Wear NHS Foundation Trust SeW-PGN-1 - Apêndice 7 - Manual do "
            "Usuário da Ferramenta Indicadora HSE - V03. Edição 1 - Emitido em setembro de 2014. Parte da NTW(HR) 12 - "
            "Política de Estresse no Trabalho.",
            small_style,
        )
    )

    story.append(PageBreak())
    add_section_header(4, "IMPORTÂNCIA DA PARTICIPAÇÃO DOS TRABALHADORES")
    story.append(
        Paragraph(
            "A participação ativa, consciente e transparente dos trabalhadores constitui elemento fundamental "
            "para a efetividade desta Avaliação Ergonômica Preliminar (AEP), em consonância com os princípios "
            "de participação estabelecidos na NR-1 (item 1.5.3.1) e na NR-17, que ressaltam a relevância do "
            "envolvimento dos colaboradores na identificação e no gerenciamento dos riscos ocupacionais, "
            "inclusive daqueles relacionados aos fatores psicossociais do trabalho.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "Os trabalhadores são aqueles que vivenciam cotidianamente os processos, as exigências e os desafios do "
            "ambiente de trabalho, detendo conhecimento prático e percepções concretas acerca dos fatores que influenciam "
            "sua saúde, bem-estar, segurança e desempenho. Esse saber experiencial, de caráter insubstituível, "
            "complementa as análises e observações técnicas realizadas no decorrer da avaliação.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "A obtenção das percepções diretamente junto aos trabalhadores, de maneira anônima e confidencial, "
            "minimiza vieses de avaliação e permite a identificação de aspectos subjetivos que não seriam "
            "evidenciados apenas por meio de observações técnicas ou análise documental. Ademais, a participação "
            "efetiva dos colaboradores fortalece o compromisso coletivo com a saúde e a segurança, estimulando "
            "o engajamento nas ações de melhoria que venham a ser implementadas posteriormente.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "A ausência de engajamento dos trabalhadores pode resultar em lacunas relevantes nas informações "
            "coletadas, tornando o diagnóstico impreciso ou parcial e comprometendo a efetividade das medidas "
            "preventivas e corretivas propostas. Por essa razão, ressalta-se que a qualidade dos dados obtidos "
            "está diretamente vinculada à existência de um ambiente de confiança, no qual os colaboradores se "
            "sintam seguros para manifestar suas percepções de forma transparente, sem receio de retaliações "
            "ou julgamentos.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "A promoção da transparência, da escuta ativa e do diálogo permanente constitui estratégia essencial "
            "para assegurar essa participação, em consonância com o ciclo de melhoria contínua do Gerenciamento "
            "de Riscos Ocupacionais (GRO) e do Programa de Gerenciamento de Riscos (PGR). Essa abordagem participativa "
            "fortalece a cultura de saúde e segurança na organização, contribuindo para a construção de um ambiente "
            "de trabalho mais seguro, saudável, equilibrado e produtivo.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "Por fim, destaca-se que a participação do trabalhador no processo de identificação e avaliação dos "
            "riscos psicossociais está em consonância com as melhores práticas internacionais recomendadas pela "
            "HSE-UK, configurando-se como um diferencial para organizações que buscam excelência em seus sistemas "
            "de gestão de saúde e segurança do trabalho, promovendo resultados sustentáveis e valorizando o "
            "bem-estar de seus colaboradores.",
            body_style,
        )
    )

    # 5. RESULTADOS GERAIS
    results = report_context.get("results") or {}
    domains = results.get("domains") or []
    domain_details = results.get("domain_details") or []
    overall_percent = results.get("overall_percent", 0)
    overall_avg = results.get("overall_avg", 0)
    overall_label = results.get("overall_label", "Sem dados")

    story.append(PageBreak())
    add_section_header(5, "RESULTADOS GERAIS")

    card_width = (doc.width - 10) / 2
    domain_card_width = doc.width
    overall_color = zone_color(overall_percent) if overall_percent else colors.HexColor("#94a3b8")
    overall_label_center = ParagraphStyle(
        "OverallLabelCenter",
        parent=label_style,
        alignment=1,
    )
    overall_value_center = ParagraphStyle(
        "OverallValueCenter",
        parent=body_style,
        alignment=1,
    )
    overall_base_flow = [
        Paragraph("Média geral da empresa", overall_label_center),
        Paragraph(
            f"<font size=18 color='{overall_color.hexval()}'><b>{overall_percent}%</b></font>",
            overall_value_center,
        ),
        Spacer(1, 2),
        Paragraph(f"<b>{overall_avg}</b> {overall_label}", overall_value_center),
    ]

    domain_bar_width = (domain_card_width - 20) * 0.55
    domain_rows = [[Paragraph("Média por domínio", label_style), "", ""]]
    if domains:
        for domain in domains:
            label = domain.get("label", "-")
            percent = domain.get("percent", 0)
            avg = domain.get("avg", 0)
            color = zone_color(percent)
            domain_rows.append(
                [
                    Paragraph(f"<b>{label}</b>", body_style),
                    make_bar(percent, domain_bar_width, 10, color, show_container=True),
                    Paragraph(f"<b>{percent}%</b> | {avg}", body_style),
                ]
            )
    else:
        domain_rows.append([Paragraph("Sem dados", body_style), "", ""])

    overall_card = Table([[overall_base_flow]], colWidths=[card_width])
    overall_card.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    domain_card_inner = Table(
        domain_rows,
        colWidths=[(domain_card_width - 20) * 0.30, (domain_card_width - 20) * 0.55, (domain_card_width - 20) * 0.15],
        hAlign="LEFT",
    )
    domain_card_inner.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (2, 0)),
                ("ALIGN", (2, 1), (2, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (1, 1), (1, -1), 8),
                ("LEFTPADDING", (2, 1), (2, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    domain_card = make_card([domain_card_inner], domain_card_width)

    responses_count = report_context.get("responses_count", 0)
    total_workers = report_context.get("total_workers", 0)
    response_rate = report_context.get("response_rate", 0)
    response_label = report_context.get("response_label", "Sem dados")
    sample_label_center = ParagraphStyle(
        "SampleLabelCenter",
        parent=label_style,
        alignment=1,
    )
    sample_text_center = ParagraphStyle(
        "SampleTextCenter",
        parent=small_style,
        alignment=1,
    )
    sample_value_center = ParagraphStyle(
        "SampleValueCenter",
        parent=body_style,
        alignment=1,
    )
    sample_flow = [
        Paragraph("Amostra de Respostas", sample_label_center),
        Paragraph(f"{responses_count} de {total_workers} funcionários responderam", sample_text_center),
        Paragraph(f"<font size=18 color='#ef4444'><b>{response_rate}%</b></font>", sample_value_center),
        Paragraph(f"<b>{response_label}</b>", sample_value_center),
    ]
    sample_card = Table([[sample_flow]], colWidths=[card_width])
    sample_card.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    cards_table = Table(
        [
            [overall_card, sample_card],
        ],
        colWidths=[card_width, card_width],
        hAlign="LEFT",
    )
    cards_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBEFORE", (1, 0), (1, 0), 0.8, colors.HexColor("#cbd5e1")),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 16),
                ("LEFTPADDING", (1, 0), (1, 0), 16),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(cards_table)
    story.append(Spacer(1, 10))

    domain_table = Table([[domain_card]], colWidths=[doc.width], hAlign="CENTER")
    domain_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(domain_table)
    story.append(Spacer(1, 8))

    zone_legend_text = ParagraphStyle(
        "ZoneLegendText",
        parent=small_style,
        textColor=colors.black,
    )
    zone_legend = Table(
        [
            [
                Paragraph("<b>Zona Vermelha (0% a 39.99%)</b><br/>Risco elevado: ação corretiva imediata", zone_legend_text),
                Paragraph("<b>Zona Amarela (40% a 74.99%)</b><br/>Atenção: possível risco psicossocial; revisar práticas.", zone_legend_text),
                Paragraph("<b>Zona Verde (75% a 100%)</b><br/>Boa percepção: manutenção recomendada.", zone_legend_text),
            ]
        ],
        colWidths=[doc.width / 3] * 3,
        rowHeights=[32],
        hAlign="CENTER",
    )
    zone_legend.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (0, 0), 0.8, colors.HexColor("#991b1b")),
                ("BOX", (1, 0), (1, 0), 0.8, colors.HexColor("#92400e")),
                ("BOX", (2, 0), (2, 0), 0.8, colors.HexColor("#166534")),
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#ef4444")),
                ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#f59e0b")),
                ("BACKGROUND", (2, 0), (2, 0), colors.HexColor("#22c55e")),
                ("TEXTCOLOR", (0, 0), (0, 0), colors.black),
                ("TEXTCOLOR", (1, 0), (1, 0), colors.black),
                ("TEXTCOLOR", (2, 0), (2, 0), colors.black),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(zone_legend)
    story.append(Spacer(1, 10))

    chart_title_center = ParagraphStyle(
        "ReportChartTitle",
        parent=sub_section_style,
        alignment=1,
    )
    domain_title_center = ParagraphStyle(
        "ReportDomainTitleCenter",
        parent=section_caps_style,
        alignment=1,
        fontSize=14,
        spaceAfter=6,
    )
    chart_text_center = ParagraphStyle(
        "ReportChartTextCenter",
        parent=body_style,
        alignment=1,
    )
    chart_text_left = ParagraphStyle(
        "ReportChartTextLeft",
        parent=body_style,
        alignment=0,
    )
    chart_title_big = ParagraphStyle(
        "ReportChartTitleBig",
        parent=section_caps_style,
        alignment=1,
        fontSize=14,
        spaceAfter=6,
    )
    chart_subtitle_big = ParagraphStyle(
        "ReportChartSubtitleBig",
        parent=body_style,
        alignment=1,
        fontSize=11,
        spaceAfter=4,
    )
    chart_title_mid = ParagraphStyle(
        "ReportChartTitleMid",
        parent=body_style,
        alignment=1,
        fontSize=12,
        spaceAfter=4,
        fontName="Helvetica-Bold",
    )
    chart_small_center = ParagraphStyle(
        "ReportChartSmallCenter",
        parent=small_style,
        alignment=1,
    )
    chart_small_left = ParagraphStyle(
        "ReportChartSmallLeft",
        parent=small_style,
        alignment=0,
    )

    story.append(Paragraph("Grafico dos resultados", chart_title_center))
    chart_left_col = doc.width * 0.28
    chart_right_col = doc.width * 0.18
    bar_width = doc.width - chart_left_col - chart_right_col
    bar_width = max(80, bar_width)

    for idx, domain in enumerate(domain_details):
        if idx > 0:
            story.append(PageBreak())
        story.append(Paragraph(domain.get("label", "-").upper(), domain_title_center))
        legend_row = Table(
            [
                [
                    Drawing(8, 8, Rect(0, 0, 8, 8, fillColor=colors.HexColor("#22c55e"), strokeColor=None)),
                    Paragraph("NUNCA - POSITIVO | BOM", chart_small_left),
                    Drawing(8, 8, Rect(0, 0, 8, 8, fillColor=colors.HexColor("#f59e0b"), strokeColor=None)),
                    Paragraph("Às vezes - ATENÇÃO", chart_small_left),
                    Drawing(8, 8, Rect(0, 0, 8, 8, fillColor=colors.HexColor("#ef4444"), strokeColor=None)),
                    Paragraph("SEMPRE - NEGATIVO | RUIM", chart_small_left),
                ]
            ],
            colWidths=[10, 150, 10, 130, 10, 170],
            hAlign="LEFT",
        )
        legend_row.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )

        right_block = []
        percent = domain.get("percent", 0)
        avg = domain.get("avg", 0)
        color = zone_color(percent)
        summary_row = Table(
            [
                [
                    Paragraph("Média Geral", chart_text_center),
                    make_bar(percent, bar_width, 12, color, show_container=True),
                    Paragraph(f"<b>{percent}%</b> | {avg}", chart_text_center),
                ]
            ],
            colWidths=[chart_left_col, bar_width, chart_right_col],
            hAlign="CENTER",
        )
        summary_row.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        right_block.append(summary_row)
        right_block.append(Spacer(1, 4))
        right_block.append(graph_separator())
        right_block.append(Spacer(1, 6))

        ghes = domain.get("ghes") or []
        if ghes:
            right_block.extend([Paragraph("Análise por Setor", chart_text_center), Spacer(1, 2)])
            for ghe in ghes:
                percent = ghe.get("percent", 0)
                avg = ghe.get("avg", 0)
                color = zone_color(percent)
                row = Table(
                    [
                        [
                            Paragraph(ghe.get("name", "-"), chart_text_center),
                            make_bar(percent, bar_width, 12, color, show_container=True),
                            Paragraph(f"<b>{percent}%</b> | {avg}", chart_text_center),
                        ]
                    ],
                    colWidths=[chart_left_col, bar_width, chart_right_col],
                    hAlign="CENTER",
                )
                row.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                            ("TOPPADDING", (0, 0), (-1, -1), 2),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        ]
                    )
                )
                right_block.append(row)
            right_block.append(Spacer(1, 6))

        story.extend(right_block)
        story.append(Spacer(1, 6))
        story.append(graph_separator())
        story.append(Spacer(1, 6))

        questions = domain.get("questions") or []
        if questions:
            story.append(Paragraph(f"{domain.get('label', '').upper()} (Análise Geral)", chart_title_mid))
            story.append(legend_row)
            story.append(Spacer(1, 6))
            for chunk in chunk_list(questions, 6):
                block = []
                for q in chunk:
                    q_percent = q.get("percent", 0)
                    q_avg = q.get("avg", 0)
                    zone = q.get("zone", "Sem dados")
                    zone_label = normalize_zone_label(zone)
                    if zone_label == "BOM":
                        q_color = colors.HexColor("#22c55e")
                    elif zone_label == "ATENÇÃO":
                        q_color = colors.HexColor("#f59e0b")
                    elif zone_label == "RUIM":
                        q_color = colors.HexColor("#ef4444")
                    else:
                        q_color = colors.HexColor("#94a3b8")

                    question_bar_width = max(80, bar_width - 90)
                    question_table_left = max(120, bar_width - 20)
                    question_left = [
                        Paragraph(q.get("text", "-"), chart_text_left),
                    ]
                    score_cell = Table(
                        [[Paragraph(f"{q_avg}", chart_text_center)], [Paragraph("Score", chart_small_center)]],
                        colWidths=[60],
                    )
                    score_cell.setStyle(
                        TableStyle(
                            [
                                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                ("TOPPADDING", (0, 0), (-1, -1), 0),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                            ]
                        )
                    )
                    question_right = Table(
                        [[make_bar(q_percent, question_bar_width, 18, q_color, f"{q_percent}% | {zone_label}"), score_cell]],
                        colWidths=[question_bar_width, 60],
                    )
                    question_right.setStyle(
                        TableStyle(
                            [
                                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (0, 0), 8),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                ("TOPPADDING", (0, 0), (-1, -1), 0),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                            ]
                        )
                    )
                    question_table = Table(
                        [[question_left, question_right]],
                        colWidths=[question_table_left, question_bar_width + 60],
                        hAlign="LEFT",
                    )
                    question_table.setStyle(
                        TableStyle(
                            [
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                                ("RIGHTPADDING", (0, 0), (0, 0), 8),
                                ("TOPPADDING", (0, 0), (-1, -1), 0),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                            ]
                        )
                    )
                    block.append(question_table)
                story.extend(block)
                story.append(Spacer(1, 6))
                story.append(Spacer(1, 6))

        ghe_questions = domain.get("ghe_questions") or []
        if ghe_questions:
            for ghe in ghe_questions:
                qs = ghe.get("questions", [])
                if not qs:
                    continue
                block = [
                    Paragraph(f"{domain.get('label', '').upper()} (Análise por Setor)", chart_title_big),
                    Paragraph(f"SETOR: {ghe.get('name', '-')}", chart_subtitle_big),
                    Spacer(1, 2),
                ]
                for q in qs:
                    q_percent = q.get("percent", 0)
                    q_avg = q.get("avg", 0)
                    zone = q.get("zone", "Sem dados")
                    zone_label = normalize_zone_label(zone)
                    if zone_label == "BOM":
                        q_color = colors.HexColor("#22c55e")
                    elif zone_label == "ATENÇÃO":
                        q_color = colors.HexColor("#f59e0b")
                    elif zone_label == "RUIM":
                        q_color = colors.HexColor("#ef4444")
                    else:
                        q_color = colors.HexColor("#94a3b8")

                    question_bar_width = max(80, bar_width - 90)
                    question_table_left = max(120, bar_width - 20)
                    question_left = [
                        Paragraph(q.get("text", "-"), chart_text_left),
                    ]
                    score_cell = Table(
                        [[Paragraph(f"{q_avg}", chart_text_center)], [Paragraph("Score", chart_small_center)]],
                        colWidths=[60],
                    )
                    score_cell.setStyle(
                        TableStyle(
                            [
                                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                ("TOPPADDING", (0, 0), (-1, -1), 0),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                            ]
                        )
                    )
                    question_right = Table(
                        [[make_bar(q_percent, question_bar_width, 18, q_color, f"{q_percent}% | {zone_label}"), score_cell]],
                        colWidths=[question_bar_width, 60],
                    )
                    question_right.setStyle(
                        TableStyle(
                            [
                                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (0, 0), 8),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                ("TOPPADDING", (0, 0), (-1, -1), 0),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                            ]
                        )
                    )
                    question_table = Table(
                        [[question_left, question_right]],
                        colWidths=[question_table_left, question_bar_width + 60],
                        hAlign="LEFT",
                    )
                    question_table.setStyle(
                        TableStyle(
                            [
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                                ("RIGHTPADDING", (0, 0), (0, 0), 8),
                                ("TOPPADDING", (0, 0), (-1, -1), 0),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                            ]
                        )
                    )
                    block.append(question_table)
                story.extend(block)
                story.append(Spacer(1, 6))
                story.append(Spacer(1, 6))

    # 6. CONCLUSOES E RECOMENDACOES PRELIMINARES
    story.append(PageBreak())
    add_section_header(6, "CONCLUSÕES E RECOMENDAÇÕES PRELIMINARES")

    bullet_style = ParagraphStyle("BulletBody", parent=body_style, leftIndent=10, bulletIndent=0)
    story.append(Paragraph("<bullet>&bull;</bullet> Priorizar domínios com risco elevado.", bullet_style))
    reeval_value = report_context.get("reevaluate_months", 3) or 3
    story.append(Paragraph(f"<bullet>&bull;</bullet> Reavaliar periodicamente: daqui {reeval_value} meses.", bullet_style))
    story.append(Paragraph("<bullet>&bull;</bullet> Promover treinamentos sobre saúde mental e fatores psicossociais.", bullet_style))
    story.append(Paragraph("<bullet>&bull;</bullet> Caso necessário, realizar AET aprofundada conforme NR-17.", bullet_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Plano de Ação Recomendado", ParagraphStyle("PlanTitle", parent=body_style, fontName="Helvetica-Bold", textColor=colors.HexColor("#92400e"))))
    question_scores = {}
    for domain in (report_context.get("results") or {}).get("domain_details", []):
        for q in domain.get("questions") or []:
            question_scores[q.get("text")] = (q.get("percent"), q.get("avg"))

    report_actions = report_context.get("report_actions") or []
    actions_filtered = [
        action
        for action in report_actions
        if (action.get("measures") or []) and (action.get("implantation_months") or [])
    ]
    if actions_filtered:
        story.append(Spacer(1, 10))
        story.append(Spacer(1, 6))
        for action in actions_filtered:
            measures = action.get("measures") or []
            months = action.get("implantation_months") or []
            status = action.get("status") or {}
            concluded_on = action.get("concluded_on") or ""
            if not measures or not months:
                continue
            months_sorted = sorted(
                months,
                key=lambda m: (int(m.split('/')[1]), int(m.split('/')[0])),
            )
            date_range = f"{months_sorted[0]} - {months_sorted[-1]}"
            question_text = action.get("question_text", "-")
            action_header = Paragraph(
                f"<b>{question_text}</b>",
                ParagraphStyle("ActionHeader", parent=body_style),
            )
            score_line = None
            if question_text in question_scores:
                q_percent, q_avg = question_scores.get(question_text, (None, None))
                if q_percent is not None and q_avg is not None:
                    score_line = Paragraph(f"<b>Média:</b> {q_percent}% | <b>Score:</b> {q_avg}", small_style)
            measures_list = [Paragraph(f"- {m}", body_style) for m in measures]
            measures_block = measures_list if measures_list else [Paragraph("- Sem medidas", body_style)]
            inner_width = doc.width - 20
            status_col_widths = [
                inner_width * 0.21,
                inner_width * 0.20,
                inner_width * 0.08,
                inner_width * 0.08,
                inner_width * 0.08,
                inner_width * 0.10,
                inner_width * 0.25,
            ]
            status_row = Table(
                [
                    [
                        Paragraph(company_name, small_style),
                        Paragraph(date_range, small_style),
                        make_checkbox(bool(status.get("a_fazer"))),
                        make_checkbox(bool(status.get("fazendo"))),
                        make_checkbox(bool(status.get("adiado"))),
                        make_checkbox(bool(status.get("concluido"))),
                        Paragraph(concluded_on or "___/___/___", small_style),
                    ]
                ],
                colWidths=status_col_widths,
                hAlign="LEFT",
            )
            status_row.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (2, 0), (5, 0), "CENTER"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 2),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ]
                )
            )

            status_header_text = ParagraphStyle(
                "StatusHeaderText",
                parent=small_style,
                fontSize=7,
                leading=9,
            )
            status_header = Table(
                [
                    [
                        Paragraph("<b>Responsável</b>", status_header_text),
                        Paragraph("<b>Data de aplicação</b>", status_header_text),
                        Paragraph("<b>A fazer</b>", status_header_text),
                        Paragraph("<b>Fazendo</b>", status_header_text),
                        Paragraph("<b>Adiado</b>", status_header_text),
                        Paragraph("<b>Concluído</b>", status_header_text),
                        Paragraph("<b>Data de conclusão</b>", status_header_text),
                    ]
                ],
                colWidths=status_col_widths,
                hAlign="LEFT",
            )
            status_header.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (2, 0), (5, 0), "CENTER"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 2),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ]
                )
            )

            action_rows = [[action_header]]
            if score_line:
                action_rows.append([score_line])
            action_rows.extend(
                [
                    [measures_block],
                    [status_header],
                    [status_row],
                ]
            )
            action_table = Table(
                action_rows,
                colWidths=[doc.width],
                hAlign="LEFT",
            )
            action_table.setStyle(
                TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#e2e8f0")),
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ffffff")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            story.append(action_table)
            story.append(Spacer(1, 6))

    # 7. LIMITAÇÕES
    story.append(PageBreak())
    add_section_header(7, "LIMITAÇÕES")
    story.append(
        Paragraph(
            "Esta Avaliação Ergonômica Preliminar (AEP) possui caráter preliminar, sendo realizada em "
            "conformidade com os requisitos da NR-17 (Portaria MTP nº 423/2021), item 17.3.2, que determina a "
            "necessidade de avaliação inicial para subsidiar o gerenciamento dos fatores de risco relacionados "
            "à ergonomia no ambiente de trabalho.",
            body_style,
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "A AEP tem como objetivo identificar indícios de fatores de risco, subsidiar o Programa de "
            "Gerenciamento de Riscos (PGR) e o Gerenciamento de Riscos Ocupacionais (GRO), conforme exigido "
            "pela NR-1 (Portaria SEPRT nº 6.730/2020), e auxiliar na priorização de medidas corretivas e "
            "preventivas no ambiente laboral. No entanto, este instrumento não substitui a Análise Ergonômica "
            "do Trabalho (AET), que possui caráter aprofundado e investigativo, exigindo observações diretas em "
            "campo, medições ambientais e biomecânicas, entrevistas e avaliações detalhadas das condições de "
            "trabalho.",
            body_style,
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "A NR-17 dispõe que \"as condições de trabalho que possam afetar a saúde dos trabalhadores devem ser "
            "objeto de AET\", especialmente quando forem identificados riscos significativos ou quando houver "
            "indícios de que os fatores psicossociais, físicos ou organizacionais estão impactando de forma "
            "relevante a saúde e a produtividade dos trabalhadores. Nesse sentido, a AET torna-se obrigatória em "
            "situações em que a AEP aponta a necessidade de medidas adicionais de controle ou quando os resultados "
            "indicam a presença de condições críticas que requeiram investigação aprofundada.",
            body_style,
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "Conforme o Guia de Fatores de Riscos Psicossociais Relacionados ao Trabalho (MTE), a avaliação "
            "preliminar deve ser parte de um processo contínuo de monitoramento, sendo considerada um ponto de "
            "partida no gerenciamento de riscos psicossociais, mas não encerrando o processo de análise de forma "
            "definitiva.",
            body_style,
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "Além disso, os resultados obtidos por meio desta plataforma representam a percepção dos trabalhadores "
            "sobre o ambiente de trabalho em um período específico, podendo sofrer alterações em virtude de "
            "mudanças organizacionais, tecnológicas ou de processos de trabalho. Portanto, os dados devem ser "
            "utilizados de forma crítica, sendo recomendada sua atualização periódica para manter a "
            "rastreabilidade das informações e a efetividade das ações de prevenção e controle implementadas.",
            body_style,
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "Por fim, destaca-se que a participação dos trabalhadores nesta avaliação é voluntária e "
            "confidencial, e, embora a amostra seja representativa, podem existir limitações relacionadas a "
            "fatores como receio de exposição, interpretação subjetiva das perguntas e condições específicas do "
            "local de trabalho não observadas no momento da avaliação, reforçando a necessidade de utilização da "
            "AEP como ferramenta de triagem e priorização dentro do sistema de gestão de SST, e não como avaliação "
            "conclusiva sobre todos os aspectos ergonômicos da organização.",
            body_style,
        )
    )

    # 8. RESPONSABILIDADES
    story.append(PageBreak())
    add_section_header(8, "RESPONSABILIDADES")
    today = date.today()
    month_names = [
        'janeiro',
        'fevereiro',
        'marco',
        'abril',
        'maio',
        'junho',
        'julho',
        'agosto',
        'setembro',
        'outubro',
        'novembro',
        'dezembro',
    ]
    month_label = month_names[today.month - 1]
    date_label = f"{today.day:02d} de {month_label} de {today.year}"
    location_label = (report_context.get("evaluation_representative_location") or "").strip()
    if location_label and location_label != "-":
        date_output = f"{location_label}, {date_label}"
    else:
        date_output = date_label
    story.append(Paragraph(date_output, body_style))
    story.append(Spacer(1, 18))

    signature_name_style = ParagraphStyle(
        "SignatureName",
        parent=body_style,
        alignment=1,
    )
    signature_role_style = ParagraphStyle(
        "SignatureRole",
        parent=small_style,
        alignment=1,
    )
    signature_bold_style = ParagraphStyle(
        "SignatureBold",
        parent=small_style,
        alignment=1,
        fontName="Helvetica-Bold",
    )

    evaluator_name = report_context.get("evaluation_representative_name") or "-"
    evaluator_company = report_context.get("evaluation_company_name") or "CISS CONSULTORIA"
    approver_name = report_context.get("company_legal_representative_name") or "-"
    approver_company = report_context.get("company_legal_representative_company") or "-"

    left_signature = Table(
        [
            [Paragraph(" ", body_style)],
            [Paragraph(f"<b>{evaluator_name}</b>", signature_name_style)],
            [Paragraph("Representante Legal", signature_role_style)],
            [Paragraph(evaluator_company, signature_role_style)],
            [Paragraph("Responsável pela avaliação", signature_bold_style)],
        ],
        colWidths=[doc.width * 0.45],
    )
    left_signature.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, 1), (0, 1), 0.6, colors.HexColor("#94a3b8")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )

    right_signature = Table(
        [
            [Paragraph(" ", body_style)],
            [Paragraph(f"<b>{approver_name}</b>", signature_name_style)],
            [Paragraph("Representante Legal", signature_role_style)],
            [Paragraph(approver_company, signature_role_style)],
            [Paragraph("Responsável pela aprovação", signature_bold_style)],
        ],
        colWidths=[doc.width * 0.45],
    )
    right_signature.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, 1), (0, 1), 0.6, colors.HexColor("#94a3b8")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )

    signatures_row = Table(
        [[left_signature, right_signature]],
        colWidths=[doc.width * 0.5, doc.width * 0.5],
        hAlign="CENTER",
    )
    signatures_row.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(signatures_row)
    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            "Ressalta-se que a responsabilidade pela implementação, monitoramento e acompanhamento das ações "
            "corretivas e preventivas recomendadas neste relatório é integralmente da empresa, conforme "
            "estabelece a NR-1 (item 1.5.3.1) e o Programa de Gerenciamento de Riscos (PGR), cabendo à organização "
            "avaliar a aplicabilidade das medidas no contexto de suas operações, garantindo a conformidade com as "
            "normas regulamentadoras vigentes e as melhores práticas de saúde, segurança e ergonomia ocupacional.",
            body_style,
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "Este relatório, elaborado com rigor técnico e em conformidade com a NR-1, NR-17 e o Guia de Fatores "
            "de Riscos Psicossociais Relacionados ao Trabalho, visa subsidiar a gestão da empresa na tomada de "
            "decisões informadas, mantendo rastreabilidade e evidências técnicas para auditorias, fiscalizações "
            "e processos de melhoria contínua do sistema de gestão de SST.",
            body_style,
        )
    )

    # 9. ANEXOS
    story.append(PageBreak())
    add_section_header(9, "ANEXOS")
    attachments = report_context.get("attachments") or []
    image_exts = {".png", ".jpg", ".jpeg", ".gif", ".bmp"}
    if attachments:
        for idx, attachment in enumerate(attachments, start=1):
            title = attachment.get("title") or f"Anexo {idx}"
            description = attachment.get("description") or ""
            original_name = attachment.get("original_name") or ""
            stored_path = attachment.get("stored_path") or ""
            stored_name = attachment.get("stored_name") or ""
            line = f"<b>{title}</b>"
            if description:
                line += f" - {description}"
            if original_name:
                line += f" (Arquivo: {original_name})"
            story.append(Paragraph(line, body_style))
            story.append(Spacer(1, 4))

            if stored_path or stored_name:
                campaign_uuid = report_context.get("campaign_uuid") or ""
                normalized_path = stored_path.strip()
                if stored_name and campaign_uuid:
                    normalized_path = f"report_attachments/{campaign_uuid}/{stored_name}"
                public_url = getattr(settings, 'AWS_S3_PUBLIC_URL', '').strip().rstrip('/')
                if public_url and normalized_path.startswith(public_url):
                    normalized_path = normalized_path[len(public_url):]
                if '://' in normalized_path:
                    try:
                        parsed = urlparse(normalized_path)
                        normalized_path = parsed.path or ''
                    except Exception:
                        normalized_path = stored_path
                normalized_path = normalized_path.lstrip('/')
                for marker in (
                    'storage/v1/object/public/',
                    'storage/v1/object/',
                    'storage/v1/s3/',
                ):
                    if marker in normalized_path:
                        normalized_path = normalized_path.split(marker, 1)[1]
                        break
                bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '').strip('/')
                if bucket and normalized_path.startswith(bucket + '/'):
                    normalized_path = normalized_path[len(bucket) + 1:]
                if stored_name and campaign_uuid and not normalized_path.startswith('report_attachments/'):
                    normalized_path = f"report_attachments/{campaign_uuid}/{stored_name}"
                _, ext = os.path.splitext(normalized_path.lower())
                if ext in image_exts:
                    try:
                        if os.path.exists(normalized_path):
                            img = Image(normalized_path)
                        else:
                            try:
                                with default_storage.open(normalized_path, 'rb') as handle:
                                    img = Image(ImageReader(handle))
                            except Exception:
                                public_url = getattr(settings, 'AWS_S3_PUBLIC_URL', '').strip().rstrip('/')
                                bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '').strip('/')
                                if public_url and bucket:
                                    object_url = f"{public_url}/{bucket}/{normalized_path.lstrip('/')}"
                                    print(f"[report_pdf] Loading attachment from URL: {object_url}")
                                    try:
                                        opener = build_opener(ProxyHandler({}))
                                        response = opener.open(object_url, timeout=15)
                                        content_type = response.headers.get('Content-Type', '')
                                        print(
                                            f"[report_pdf] URL status: {getattr(response, 'status', 'unknown')} "
                                            f"content-type: {content_type}"
                                        )
                                        data = response.read()
                                        # try:
                                        #     from PIL import Image as PILImage
                                        #     pil_img = PILImage.open(BytesIO(data)).convert('RGB')
                                        #     img = Image(ImageReader(pil_img))
                                        # except Exception:
                                        #     img = Image(ImageReader(BytesIO(data)))
                                        image_stream = BytesIO(data)
                                        img = Image(image_stream)
                                        print("IMG WIDTH:", img.imageWidth)
                                        print("IMG HEIGHT:", img.imageHeight)
                                    except (HTTPError, URLError, OSError) as fetch_err:
                                        print(f"[report_pdf] Failed to fetch attachment: {fetch_err}")
                                        raise
                                else:
                                    raise
                        max_width = doc.width
                        max_height = doc.height * 0.45
                        img_width, img_height = img.imageWidth, img.imageHeight
                        if img_width and img_height:
                            scale = min(max_width / img_width, max_height / img_height, 1.0)
                            img.drawWidth = img_width * scale
                            img.drawHeight = img_height * scale
                        story.append(img)
                        story.append(Spacer(1, 6))
                    except Exception:
                        story.append(Paragraph("Imagem não pôde ser carregada.", small_style))
                        story.append(Spacer(1, 4))
    else:
        story.append(Paragraph("Nenhum anexo informado.", body_style))
    
    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf



