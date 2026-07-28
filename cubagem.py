import math
from dataclasses import dataclass
from collections import defaultdict
from collections import defaultdict as _defaultdict


@dataclass
class Veiculo:
    tipo: str  # "Toco", "Truck" ou "Carreta"
    comprimento_mm: int  # ex: 8000 (em vez de 8.0 metros)
    largura_mm: int = 2400  # fixa (2,4m em mm)


@dataclass
class ItemBobina:
    tipo_papel: str  # "Tissue" ou "Mono"
    formato_mm: int  # altura da bobina
    diametro_mm: int  # diâmetro da bobina
    quantidade: int
    formato_real_mm: int = None  # calculado automaticamente se não informado

    def __post_init__(self):
        if self.formato_real_mm is None:
            self.formato_real_mm = calcular_formato_real(self.formato_mm, self.tipo_papel)

def calcular_posicoes_por_fiada(largura_veiculo_mm: int, diametro_mm: int) -> int:
    """Quantas bobinas cabem lado a lado na largura do veículo (esq/centro/dir)."""
    return largura_veiculo_mm // diametro_mm


def calcular_fiadas_maximas(comprimento_veiculo_mm: int, diametro_mm: int) -> int:
    """Quantas fiadas cabem no comprimento do veículo, para um dado diâmetro."""
    return comprimento_veiculo_mm // diametro_mm


def calcular_lastro(veiculo: Veiculo, diametro_mm: int) -> dict:
    """Calcula a capacidade do 1º nível (lastro) para bobinas de um diâmetro específico."""
    fiadas = calcular_fiadas_maximas(veiculo.comprimento_mm, diametro_mm)
    posicoes = calcular_posicoes_por_fiada(veiculo.largura_mm, diametro_mm)
    capacidade = fiadas * posicoes
    return {
        "fiadas": fiadas,
        "posicoes_por_fiada": posicoes,
        "capacidade_lastro": capacidade,
    }

def calcular_secao_diametro_maior(veiculo: Veiculo, diametro_maior_mm: int, quantidade_desejada: int) -> dict:
    """Calcula quantas fiadas e qual comprimento a seção do diâmetro maior vai ocupar."""
    posicoes = calcular_posicoes_por_fiada(veiculo.largura_mm, diametro_maior_mm)
    fiadas_necessarias = math.ceil(quantidade_desejada / posicoes)  # arredonda pra cima
    comprimento_usado_mm = fiadas_necessarias * diametro_maior_mm
    capacidade_real = fiadas_necessarias * posicoes  # pode ser > quantidade_desejada (fiada incompleta)

    return {
        "fiadas": fiadas_necessarias,
        "posicoes_por_fiada": posicoes,
        "capacidade_secao": capacidade_real,
        "quantidade_desejada": quantidade_desejada,
        "vagas_sobrando_na_secao": capacidade_real - quantidade_desejada,
        "comprimento_usado_mm": comprimento_usado_mm,
    }


def calcular_secao_diametro_menor(veiculo: Veiculo, diametro_menor_mm: int, comprimento_usado_mm: int) -> dict:
    """Calcula a seção do diâmetro menor no comprimento restante do veículo."""
    comprimento_restante_mm = veiculo.comprimento_mm - comprimento_usado_mm
    fiadas = comprimento_restante_mm // diametro_menor_mm
    posicoes = calcular_posicoes_por_fiada(veiculo.largura_mm, diametro_menor_mm)
    capacidade = fiadas * posicoes

    return {
        "comprimento_restante_mm": comprimento_restante_mm,
        "fiadas": fiadas,
        "posicoes_por_fiada": posicoes,
        "capacidade_secao": capacidade,
    }


def calcular_lastro_misto(veiculo: Veiculo, diametro_maior_mm: int, quantidade_maior_desejada: int, diametro_menor_mm: int) -> dict:
    """Calcula o lastro completo quando há dois diâmetros diferentes."""
    secao_maior = calcular_secao_diametro_maior(veiculo, diametro_maior_mm, quantidade_maior_desejada)
    secao_menor = calcular_secao_diametro_menor(veiculo, diametro_menor_mm, secao_maior["comprimento_usado_mm"])

    return {
        "secao_diametro_maior": secao_maior,
        "secao_diametro_menor": secao_menor,
        "capacidade_total_lastro": secao_maior["capacidade_secao"] + secao_menor["capacidade_secao"],
    }


def calcular_remontagem(sobra_quantidade: int, capacidade_por_nivel: int) -> dict:
    """Distribui a sobra de bobinas em níveis acima do lastro (mesmo diâmetro)."""
    if sobra_quantidade <= 0 or capacidade_por_nivel <= 0:
        return {"niveis_necessarios": 0, "distribuicao_por_nivel": []}

    niveis_necessarios = math.ceil(sobra_quantidade / capacidade_por_nivel)
    distribuicao = []
    restante = sobra_quantidade

    for _ in range(niveis_necessarios):
        qtd_nivel = min(capacidade_por_nivel, restante)
        distribuicao.append(qtd_nivel)
        restante -= qtd_nivel

    return {
        "niveis_necessarios": niveis_necessarios,
        "distribuicao_por_nivel": distribuicao,
    }


def agrupar_por_diametro(itens: list[ItemBobina]) -> dict:
    """Agrupa os itens cadastrados por diâmetro, somando as quantidades."""
    grupos = defaultdict(int)
    for item in itens:
        grupos[item.diametro_mm] += item.quantidade
    return dict(sorted(grupos.items()))


def gerar_trilhas(diametro_mm: int) -> list:
    """Retorna as trilhas disponíveis conforme o diâmetro (2 ou 3 posições)."""
    posicoes = 2400 // diametro_mm  # largura fixa do veículo
    if posicoes >= 3:
        return ["esquerda", "centro", "direita"]
    elif posicoes == 2:
        return ["esquerda", "direita"]
    else:
        return ["centro"]


def rotulo_celula(item: ItemBobina) -> str:
    """Gera o texto exibido no quadradinho: ícone + formato/primeiro dígito do diâmetro."""
    primeiro_digito = str(item.diametro_mm)[0]
    icone = "🟦" if item.tipo_papel == "Branca" else "🟩"
    return f"{icone} {item.formato_mm}/{primeiro_digito}"


def pode_empilhar(item_superior: ItemBobina, item_inferior: ItemBobina) -> bool:
    """Valida a regra de empilhamento: mesmo diâmetro + Mono nunca sobre Tissue."""
    if item_superior.diametro_mm != item_inferior.diametro_mm:
        return False
    if item_superior.tipo_papel == "Marron" and item_inferior.tipo_papel == "Branca":
        return False
    return True

def calcular_altura_fiada_mm(grade: dict, trilha: str, fiada: int) -> int:
    """Soma o formato (altura) de todas as bobinas empilhadas numa trilha/fiada específica."""
    return sum(
        item.formato_real_mm
        for (t, f, n), item in grade.items()
        if t == trilha and f == fiada
    )

def construir_mapa_fiadas(
    fiadas_maior: int, diametro_maior: int, trilhas_maior: list, niveis_maior: int,
    fiadas_menor: int, diametro_menor: int, trilhas_menor: list, niveis_menor: int,
    ordem: str = "maior_primeiro",
) -> dict:
    """Mapeia cada número de fiada (numeração contínua) às regras da seção correspondente.
    ordem: 'maior_primeiro' (diâmetro maior no início) ou 'menor_primeiro' (diâmetro maior no final)."""
    mapa = {}

    if ordem == "maior_primeiro":
        for f in range(1, fiadas_maior + 1):
            mapa[f] = {"diametro": diametro_maior, "trilhas": trilhas_maior, "niveis": niveis_maior}
        for f in range(fiadas_maior + 1, fiadas_maior + fiadas_menor + 1):
            mapa[f] = {"diametro": diametro_menor, "trilhas": trilhas_menor, "niveis": niveis_menor}
    else:  # menor_primeiro
        for f in range(1, fiadas_menor + 1):
            mapa[f] = {"diametro": diametro_menor, "trilhas": trilhas_menor, "niveis": niveis_menor}
        for f in range(fiadas_menor + 1, fiadas_menor + fiadas_maior + 1):
            mapa[f] = {"diametro": diametro_maior, "trilhas": trilhas_maior, "niveis": niveis_maior}

    return mapa

def gerar_pdf_cubagem(buffer, veiculo, itens, grade, mapa_fiadas, total_fiadas, niveis_qtd_max):
    """Gera o PDF do mapa de carregamento (paisagem, 1 página) e escreve no buffer."""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm

    NOME_EXIBICAO_PDF = {"esquerda": "Direita", "centro": "Centro", "direita": "Esquerda"}

    largura_pagina, altura_pagina = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    margem = 1.0 * cm
    y = altura_pagina - margem

    # --- Cabeçalho ---
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margem, y, "Mapa de Carregamento - Sistema de Cubagem")
    y -= 0.8 * cm

    c.setFont("Helvetica", 10)
    c.drawString(
        margem, y,
        f"Veículo: {veiculo.tipo}  |  Comprimento: {veiculo.comprimento_mm / 1000:.1f} m  |  "
        f"Largura: {veiculo.largura_mm / 1000:.2f} m"
    )
    y -= 0.5 * cm

    # --- Total de bobinas por trilha (ordem: Esquerda / Centro / Direita) ---
    total_por_trilha = _defaultdict(int)
    for (trilha_chave, _f, _n) in grade.keys():
        total_por_trilha[trilha_chave] += 1

    partes_trilha = []
    for trilha_chave in ["direita", "centro", "esquerda"]:  # internamente invertido -> exibe Esquerda/Centro/Direita
        if trilha_chave in total_por_trilha:
            nome_exib = NOME_EXIBICAO_PDF[trilha_chave]
            partes_trilha.append(f"{nome_exib}: {total_por_trilha[trilha_chave]} bobinas")

    c.drawString(margem, y, "  |  ".join(partes_trilha))
    y -= 0.7 * cm

    # --- Resumo da carga (tabela: Papel | Itens | Qtd.) ---
    resumo = _defaultdict(int)
    for item in itens:
        resumo[(item.tipo_papel, item.formato_mm, item.diametro_mm)] += item.quantidade

    col_papel_x = margem
    col_itens_x = margem + 4 * cm
    col_qtd_x = margem + 7 * cm

    c.setFont("Helvetica-Bold", 10)
    c.drawString(margem, y, "Resumo da carga:")
    y -= 0.55 * cm

    c.setFont("Helvetica-Bold", 9)
    c.drawString(col_papel_x, y, "Papel")
    c.drawRightString(col_itens_x, y, "Itens")
    c.drawRightString(col_qtd_x, y, "Qtd.")
    y -= 0.15 * cm
    c.line(margem, y, col_qtd_x, y)
    y -= 0.35 * cm

    c.setFont("Helvetica", 9)
    total_geral = 0
    for (tipo_papel, formato, diametro), qtd in sorted(resumo.items()):
        c.drawString(col_papel_x, y, tipo_papel)
        c.drawRightString(col_itens_x, y, f"{formato} x {diametro}")
        c.drawRightString(col_qtd_x, y, str(qtd))
        y -= 0.42 * cm
        total_geral += qtd

    y -= 0.15 * cm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margem, y, f"Total Geral: {total_geral}")
    y -= 0.9 * cm

    # --- Mapa de carregamento ---
    largura_util = largura_pagina - 2 * margem
    largura_coluna = largura_util / total_fiadas
    altura_linha = 0.85 * cm

    for trilha in ["esquerda", "centro", "direita"]:
        if not any(trilha in info["trilhas"] for info in mapa_fiadas.values()):
            continue

        c.setFont("Helvetica-Bold", 11)
        c.drawString(margem, y, f"Trilha: {NOME_EXIBICAO_PDF[trilha]}")
        y -= 0.65 * cm

        for nivel in range(niveis_qtd_max, 0, -1):
            x = margem
            c.setFont("Helvetica", 11)
            for f in range(1, total_fiadas + 1):
                info = mapa_fiadas[f]
                if trilha in info["trilhas"] and nivel <= info["niveis"]:
                    item = grade.get((trilha, f, nivel))
                    if item:
                        texto = f"{item.formato_mm}/{str(item.diametro_mm)[0]}"
                        c.drawCentredString(x + largura_coluna / 2, y, texto)
                x += largura_coluna
            y -= altura_linha

        x = margem
        c.setFont("Helvetica", 9)
        for f in range(1, total_fiadas + 1):
            c.drawCentredString(x + largura_coluna / 2, y, str(f))
            x += largura_coluna
        y -= 0.9 * cm

    c.save()

TABELA_PACOTES_MM = {
    100: 6, 120: 6, 130: 6,
    140: 5, 145: 5, 160: 5,
    170: 4, 180: 4, 190: 4,
    200: 3, 210: 3, 220: 3, 230: 3, 240: 3, 250: 3, 260: 3,
    270: 2, 280: 2, 290: 2, 300: 2, 310: 2, 320: 2, 330: 2,
    340: 2, 350: 2, 360: 2, 370: 2, 380: 2, 390: 2,
}

def calcular_formato_real(formato_mm: int, tipo_papel: str) -> int:
    """Calcula a altura física real da bobina, considerando a regra de empacotamento."""
    if tipo_papel == "Branca" and formato_mm == 400:
        return formato_mm * 2  # exceção: 400mm Branca também é pacote (2 unidades)

    qtd_pacote = TABELA_PACOTES_MM.get(formato_mm)
    if qtd_pacote:
        return formato_mm * qtd_pacote

    return formato_mm  # não se enquadra em nenhuma regra de pacote

if __name__ == "__main__":
    veiculo = Veiculo(tipo="Truck", comprimento_mm=8000)

    itens = [
        ItemBobina(tipo_papel="Tissue", formato_mm=540, diametro_mm=800, quantidade=5),
        ItemBobina(tipo_papel="Mono", formato_mm=600, diametro_mm=800, quantidade=30),
    ]

    total_bobinas = sum(item.quantidade for item in itens)
    print(f"Total de bobinas informadas: {total_bobinas}")

    resultado = calcular_lastro(veiculo, diametro_mm=800)
    print(f"Fiadas no comprimento: {resultado['fiadas']}")
    print(f"Posições por fiada: {resultado['posicoes_por_fiada']}")
    print(f"Capacidade do lastro: {resultado['capacidade_lastro']}")

    sobra = total_bobinas - resultado["capacidade_lastro"]
    print(f"Sobra (vai para remontagem): {sobra}")

    print("\n--- Teste com diâmetros mistos ---")
    resultado_misto = calcular_lastro_misto(
        veiculo,
        diametro_maior_mm=1000,
        quantidade_maior_desejada=7,
        diametro_menor_mm=800,
    )
    sec_maior = resultado_misto["secao_diametro_maior"]
    sec_menor = resultado_misto["secao_diametro_menor"]
    print(f"[Diâmetro 1000mm] Fiadas: {sec_maior['fiadas']}, Posições: {sec_maior['posicoes_por_fiada']}, "
          f"Capacidade: {sec_maior['capacidade_secao']}")
    print(f"[Diâmetro 800mm] Fiadas: {sec_menor['fiadas']}, Posições: {sec_menor['posicoes_por_fiada']}, "
          f"Capacidade: {sec_menor['capacidade_secao']}")
    print(f"Capacidade total do lastro misto: {resultado_misto['capacidade_total_lastro']}")

    print("\n--- Teste de remontagem ---")
    remontagem = calcular_remontagem(sobra_quantidade=sobra, capacidade_por_nivel=resultado["capacidade_lastro"])
    print(f"Níveis necessários: {remontagem['niveis_necessarios']}")
    print(f"Distribuição por nível: {remontagem['distribuicao_por_nivel']}")
