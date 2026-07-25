import io
from datetime import date

import streamlit as st
from cubagem import (
    Veiculo, ItemBobina, agrupar_por_diametro,
    calcular_lastro, calcular_lastro_misto, calcular_remontagem,
    gerar_trilhas, rotulo_celula, pode_empilhar, calcular_altura_fiada_mm,
    construir_mapa_fiadas, gerar_pdf_cubagem,
)

st.set_page_config(page_title="Sistema de Cubagem", layout="wide")
st.title("🚛 Sistema de Cubagem de Veículos")

NOME_EXIBICAO = {"esquerda": "Direita", "centro": "Centro", "direita": "Esquerda"}


def _gerar_secao_pdf(veiculo, mapa_fiadas, total_fiadas, niveis_qtd_max):
    """Bloco reutilizável de geração/salvamento do PDF (usado no caso simples e no misto)."""
    st.divider()
    st.header("5. Salvar Mapa de Carregamento (PDF)")

    nome_arquivo = st.text_input("Nome do arquivo (sem extensão):", value="mapa_carregamento")

    if st.button("💾 Salvar"):
        buffer = io.BytesIO()
        gerar_pdf_cubagem(
            buffer, veiculo, st.session_state.itens, st.session_state.grade,
            mapa_fiadas, total_fiadas, niveis_qtd_max,
        )
        st.session_state.pdf_bytes = buffer.getvalue()
        st.session_state.pdf_filename = f"{nome_arquivo}_{date.today().isoformat()}.pdf"
        st.success("PDF gerado com sucesso!")

    if st.session_state.get("pdf_bytes"):
        st.download_button(
            "⬇️ Baixar PDF",
            data=st.session_state.pdf_bytes,
            file_name=st.session_state.pdf_filename,
            mime="application/pdf",
        )


# --- Inicializa o estado da sessão ---
if "itens" not in st.session_state:
    st.session_state.itens = []

# ==========================================
# ETAPA 1 - DADOS DO VEÍCULO
# ==========================================
st.header("1. Dados do Veículo")

col1, col2 = st.columns(2)
with col1:
    tipo_veiculo = st.selectbox("Tipo de veículo", ["Toco", "Truck", "Carreta"])
with col2:
    comprimento_m = st.selectbox("Comprimento (m)", [7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0, 12.0, 14.0, 15.0])

veiculo = Veiculo(tipo=tipo_veiculo, comprimento_mm=int(comprimento_m * 1000))
st.caption(f"Largura fixa: 2,40 m | Comprimento: {comprimento_m} m")

st.divider()

# ==========================================
# ETAPA 2 - DADOS DA CARGA (BOBINAS)
# ==========================================
st.header("2. Itens da Carga (Bobinas)")

with st.form("form_item", clear_on_submit=True):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        tipo_papel = st.selectbox("Tipo de papel", ["Tissue", "Mono"])
    with c2:
        formato_mm = st.number_input("Formato/Altura (mm)", min_value=1, value=600, step=10)
    with c3:
        diametro_mm = st.number_input("Diâmetro (mm)", min_value=1, value=800, step=10)
    with c4:
        quantidade = st.number_input("Quantidade", min_value=1, value=1, step=1)

    adicionar = st.form_submit_button("➕ Adicionar item")

    if adicionar:
        novo_item = ItemBobina(
            tipo_papel=tipo_papel,
            formato_mm=formato_mm,
            diametro_mm=diametro_mm,
            quantidade=quantidade,
        )
        st.session_state.itens.append(novo_item)
        st.success(f"Item adicionado: {quantidade}x {tipo_papel} (formato {formato_mm}mm, diâmetro {diametro_mm}mm)")

if st.session_state.itens:
    st.subheader("Itens adicionados")

    for i, item in enumerate(st.session_state.itens):
        col_a, col_b = st.columns([5, 1])
        with col_a:
            st.write(
                f"**{item.tipo_papel}** — Formato: {item.formato_mm}mm | "
                f"Diâmetro: {item.diametro_mm}mm | Quantidade: {item.quantidade}"
            )
        with col_b:
            if st.button("🗑️ Remover", key=f"remover_{i}"):
                st.session_state.itens.pop(i)
                st.rerun()

    total_bobinas = sum(item.quantidade for item in st.session_state.itens)
    st.metric("Total de bobinas informadas", total_bobinas)

    st.divider()

    # ==========================================
    # ETAPA 3 - RESUMO POR DIÂMETRO
    # ==========================================
    st.header("3. Resumo por Diâmetro")

    grupos = agrupar_por_diametro(st.session_state.itens)
    st.table([{"Diâmetro (mm)": diam, "Quantidade total": qtd} for diam, qtd in grupos.items()])

    diametros = list(grupos.keys())

    # ==============================================================
    # CASO 1: DIÂMETRO ÚNICO
    # ==============================================================
    if len(diametros) == 1:
        diametro_unico = diametros[0]
        total_diametro = grupos[diametro_unico]

        st.success(f"Apenas um diâmetro ({diametro_unico}mm) — cálculo de lastro simples.")

        resultado_lastro = calcular_lastro(veiculo, diametro_unico)
        sobra = total_diametro - resultado_lastro["capacidade_lastro"]

        c1, c2, c3 = st.columns(3)
        c1.metric("Fiadas no comprimento", resultado_lastro["fiadas"])
        c2.metric("Posições por fiada", resultado_lastro["posicoes_por_fiada"])
        c3.metric("Capacidade do lastro", resultado_lastro["capacidade_lastro"])

        remontagem = {"niveis_necessarios": 0, "distribuicao_por_nivel": []}
        if sobra > 0:
            remontagem = calcular_remontagem(sobra, resultado_lastro["capacidade_lastro"])
            st.info(f"Sobra de {sobra} bobinas → {remontagem['niveis_necessarios']} nível(is) de remontagem: {remontagem['distribuicao_por_nivel']}")
        else:
            st.info("Toda a carga cabe no lastro, sem necessidade de remontagem.")

        st.session_state.plano_cubagem = {
            "tipo": "simples",
            "diametro": diametro_unico,
            "lastro": resultado_lastro,
            "sobra": sobra,
        }

        # ==========================================
        # ETAPA 4 - MONTAGEM INTERATIVA (GRADE) - MODO PINCEL
        # ==========================================
        st.divider()
        st.header("4. Montagem da Carga")

        trilhas = gerar_trilhas(diametro_unico)
        fiadas_qtd = resultado_lastro["fiadas"]
        niveis_qtd = 1 + remontagem["niveis_necessarios"]

        chave_grade = f"grade_{diametro_unico}_{fiadas_qtd}_{niveis_qtd}"
        if "grade_chave_atual" not in st.session_state or st.session_state.grade_chave_atual != chave_grade:
            st.session_state.grade = {}
            st.session_state.grade_chave_atual = chave_grade
            st.session_state.itens_restantes = {
                i: item.quantidade for i, item in enumerate(st.session_state.itens)
            }

        restantes_diametro = {
            i: st.session_state.itens_restantes.get(i, 0)
            for i, item in enumerate(st.session_state.itens)
            if item.diametro_mm == diametro_unico
        }
        total_restante = sum(restantes_diametro.values())
        indices_disponiveis = [i for i, qtd in restantes_diametro.items() if qtd > 0]

        st.metric("Bobinas ainda não posicionadas", total_restante)

        if indices_disponiveis:
            if "bobina_ativa_idx" not in st.session_state or st.session_state.bobina_ativa_idx not in indices_disponiveis:
                st.session_state.bobina_ativa_idx = indices_disponiveis[0]

            def formatar_opcao(i):
                item = st.session_state.itens[i]
                return f"{item.tipo_papel} - {item.formato_mm}mm (restam {restantes_diametro[i]})"

            idx_ativo = st.selectbox(
                "🖌️ Bobina selecionada (clique nas células para posicionar):",
                options=indices_disponiveis,
                format_func=formatar_opcao,
                index=indices_disponiveis.index(st.session_state.bobina_ativa_idx),
                key=f"select_bobina_ativa_{total_restante}",
            )
            st.session_state.bobina_ativa_idx = idx_ativo
            item_ativo = st.session_state.itens[idx_ativo]
        else:
            idx_ativo, item_ativo = None, None
            st.success("Todas as bobinas já foram posicionadas! ✅")

        st.caption("Clique numa célula vazia (➕) para posicionar a bobina selecionada. Clique numa célula preenchida para removê-la.")

        for trilha in trilhas:
            st.subheader(f"Trilha: {NOME_EXIBICAO[trilha]}")

            # --- Altura acumulada (topo) ---
            cols_altura = st.columns(fiadas_qtd)
            for f in range(1, fiadas_qtd + 1):
                altura_mm = calcular_altura_fiada_mm(st.session_state.grade, trilha, f)
                altura_m = altura_mm / 1000
                cols_altura[f - 1].caption(f"📏 {altura_m:.2f}m" if altura_mm > 0 else "—")

            # --- Células (nível mais alto no topo, nível 1 embaixo) ---
            for nivel in range(niveis_qtd, 0, -1):
                cols = st.columns(fiadas_qtd)
                for f in range(1, fiadas_qtd + 1):
                    chave_celula = (trilha, f, nivel)
                    item_na_celula = st.session_state.grade.get(chave_celula)

                    with cols[f - 1]:
                        if item_na_celula:
                            rotulo = rotulo_celula(item_na_celula)
                            if st.button(rotulo, key=f"cel_{trilha}_{f}_{nivel}"):
                                st.session_state.grade.pop(chave_celula)
                                idx_item = item_na_celula._idx_origem
                                st.session_state.itens_restantes[idx_item] += 1
                                st.rerun()
                        else:
                            if st.button("➕", key=f"cel_{trilha}_{f}_{nivel}", disabled=(item_ativo is None)):
                                pode_colocar = True
                                if nivel > 1:
                                    item_abaixo = st.session_state.grade.get((trilha, f, nivel - 1))
                                    if item_abaixo is None or not pode_empilhar(item_ativo, item_abaixo):
                                        pode_colocar = False

                                if pode_colocar:
                                    item_marcado = ItemBobina(
                                        tipo_papel=item_ativo.tipo_papel,
                                        formato_mm=item_ativo.formato_mm,
                                        diametro_mm=item_ativo.diametro_mm,
                                        quantidade=1,
                                    )
                                    item_marcado._idx_origem = idx_ativo
                                    st.session_state.grade[chave_celula] = item_marcado
                                    st.session_state.itens_restantes[idx_ativo] -= 1
                                    st.rerun()
                                else:
                                    st.toast("❌ Não é possível empilhar aqui (regra de diâmetro/tipo de papel).")

            # --- Número da fiada (rodapé) ---
            cols_num = st.columns(fiadas_qtd)
            for f in range(1, fiadas_qtd + 1):
                cols_num[f - 1].caption(f"{f}")

            st.write("")

        # ==========================================
        # ETAPA 5 - SALVAR PDF (caso simples)
        # ==========================================
        mapa_fiadas_pdf = {
            f: {"diametro": diametro_unico, "trilhas": trilhas, "niveis": niveis_qtd}
            for f in range(1, fiadas_qtd + 1)
        }
        _gerar_secao_pdf(veiculo, mapa_fiadas_pdf, fiadas_qtd, niveis_qtd)

    # ==============================================================
    # CASO 2: DIÂMETROS MISTOS
    # ==============================================================
    elif len(diametros) == 2:
        diametro_maior = max(diametros)
        diametro_menor = min(diametros)
        st.warning(f"Diâmetros mistos detectados: {diametro_menor}mm e {diametro_maior}mm.")

        qtd_maior_lastro = st.number_input(
            f"Quantas bobinas de {diametro_maior}mm entrarão no lastro?",
            min_value=1,
            max_value=grupos[diametro_maior],
            value=min(grupos[diametro_maior], 1),
            step=1,
        )

        resultado_misto = calcular_lastro_misto(veiculo, diametro_maior, qtd_maior_lastro, diametro_menor)
        sec_maior = resultado_misto["secao_diametro_maior"]
        sec_menor = resultado_misto["secao_diametro_menor"]

        st.write(f"**Seção {diametro_maior}mm:** {sec_maior['fiadas']} fiadas x {sec_maior['posicoes_por_fiada']} posições = {sec_maior['capacidade_secao']} bobinas")
        st.write(f"**Seção {diametro_menor}mm:** {sec_menor['fiadas']} fiadas x {sec_menor['posicoes_por_fiada']} posições = {sec_menor['capacidade_secao']} bobinas")
        st.metric("Capacidade total do lastro", resultado_misto["capacidade_total_lastro"])

        sobra_maior = grupos[diametro_maior] - sec_maior["capacidade_secao"]
        sobra_menor = grupos[diametro_menor] - sec_menor["capacidade_secao"]

        remontagem_maior = calcular_remontagem(sobra_maior, sec_maior["capacidade_secao"]) if sobra_maior > 0 else {"niveis_necessarios": 0}
        remontagem_menor = calcular_remontagem(sobra_menor, sec_menor["capacidade_secao"]) if sobra_menor > 0 else {"niveis_necessarios": 0}

        if sobra_maior > 0:
            st.info(f"Sobra de {sobra_maior} bobinas de {diametro_maior}mm → {remontagem_maior['niveis_necessarios']} nível(is): {remontagem_maior.get('distribuicao_por_nivel', [])}")
        if sobra_menor > 0:
            st.info(f"Sobra de {sobra_menor} bobinas de {diametro_menor}mm → {remontagem_menor['niveis_necessarios']} nível(is): {remontagem_menor.get('distribuicao_por_nivel', [])}")

        st.session_state.plano_cubagem = {
            "tipo": "misto",
            "diametro_maior": diametro_maior,
            "diametro_menor": diametro_menor,
            "resultado_misto": resultado_misto,
            "sobra_maior": sobra_maior,
            "sobra_menor": sobra_menor,
        }

        # ==========================================
        # ETAPA 4 (MISTO) - GRADE ÚNICA E CONTÍNUA
        # ==========================================
        st.divider()
        st.header("4. Montagem da Carga")

        trilhas_maior = gerar_trilhas(diametro_maior)
        trilhas_menor = gerar_trilhas(diametro_menor)
        niveis_maior = 1 + remontagem_maior["niveis_necessarios"]
        niveis_menor = 1 + remontagem_menor["niveis_necessarios"]

        ordem_escolha = st.radio(
            f"Posição das {sec_maior['fiadas']} fiadas de {diametro_maior}mm no veículo:",
            ["No início", "No final"],
            horizontal=True,
        )
        ordem = "maior_primeiro" if ordem_escolha == "No início" else "menor_primeiro"

        mapa_fiadas = construir_mapa_fiadas(
            sec_maior["fiadas"], diametro_maior, trilhas_maior, niveis_maior,
            sec_menor["fiadas"], diametro_menor, trilhas_menor, niveis_menor,
            ordem=ordem,
        )
        total_fiadas = sec_maior["fiadas"] + sec_menor["fiadas"]
        niveis_qtd = max(niveis_maior, niveis_menor)

        chave_grade = f"grade_misto_{diametro_maior}_{qtd_maior_lastro}_{diametro_menor}_{total_fiadas}_{ordem}"
        if "grade_chave_atual" not in st.session_state or st.session_state.grade_chave_atual != chave_grade:
            st.session_state.grade = {}
            st.session_state.grade_chave_atual = chave_grade
            st.session_state.itens_restantes = {
                i: item.quantidade for i, item in enumerate(st.session_state.itens)
            }

        restantes_todos = {
            i: st.session_state.itens_restantes.get(i, 0)
            for i, item in enumerate(st.session_state.itens)
        }
        total_restante = sum(restantes_todos.values())
        indices_disponiveis = [i for i, qtd in restantes_todos.items() if qtd > 0]

        st.metric("Bobinas ainda não posicionadas", total_restante)

        if indices_disponiveis:
            if "bobina_ativa_idx" not in st.session_state or st.session_state.bobina_ativa_idx not in indices_disponiveis:
                st.session_state.bobina_ativa_idx = indices_disponiveis[0]

            def formatar_opcao_misto(i):
                item = st.session_state.itens[i]
                return f"{item.tipo_papel} - {item.formato_mm}/{item.diametro_mm}mm (restam {restantes_todos[i]})"

            idx_ativo = st.selectbox(
                "🖌️ Bobina selecionada (clique nas células para posicionar):",
                options=indices_disponiveis,
                format_func=formatar_opcao_misto,
                index=indices_disponiveis.index(st.session_state.bobina_ativa_idx),
                key=f"select_bobina_ativa_misto_{total_restante}",
            )
            st.session_state.bobina_ativa_idx = idx_ativo
            item_ativo = st.session_state.itens[idx_ativo]
        else:
            idx_ativo, item_ativo = None, None
            st.success("Todas as bobinas já foram posicionadas! ✅")

        st.caption(
            "Clique numa célula vazia (➕) para posicionar. "
            f"As fiadas do diâmetro {diametro_maior}mm ficam "
            f"{'no início' if ordem == 'maior_primeiro' else 'no final'} da numeração."
        )

        for trilha in ["esquerda", "centro", "direita"]:
            st.subheader(f"Trilha: {NOME_EXIBICAO[trilha]}")

            # --- Altura acumulada (topo) ---
            cols_altura = st.columns(total_fiadas)
            for f in range(1, total_fiadas + 1):
                if trilha in mapa_fiadas[f]["trilhas"]:
                    altura_mm = calcular_altura_fiada_mm(st.session_state.grade, trilha, f)
                    altura_m = altura_mm / 1000
                    cols_altura[f - 1].caption(f"📏 {altura_m:.2f}m" if altura_mm > 0 else "—")
                else:
                    cols_altura[f - 1].caption("")

            # --- Células, níveis do mais alto pro nível 1 ---
            for nivel in range(niveis_qtd, 0, -1):
                cols = st.columns(total_fiadas)
                for f in range(1, total_fiadas + 1):
                    info_fiada = mapa_fiadas[f]
                    with cols[f - 1]:
                        if trilha not in info_fiada["trilhas"] or nivel > info_fiada["niveis"]:
                            st.write("")
                            continue

                        chave_celula = (trilha, f, nivel)
                        item_na_celula = st.session_state.grade.get(chave_celula)

                        if item_na_celula:
                            rotulo = rotulo_celula(item_na_celula)
                            if st.button(rotulo, key=f"cel_{trilha}_{f}_{nivel}"):
                                st.session_state.grade.pop(chave_celula)
                                idx_item = item_na_celula._idx_origem
                                st.session_state.itens_restantes[idx_item] += 1
                                st.rerun()
                        else:
                            if st.button("➕", key=f"cel_{trilha}_{f}_{nivel}", disabled=(item_ativo is None)):
                                pode_colocar = True
                                if item_ativo.diametro_mm != info_fiada["diametro"]:
                                    pode_colocar = False
                                elif nivel > 1:
                                    item_abaixo = st.session_state.grade.get((trilha, f, nivel - 1))
                                    if item_abaixo is None or not pode_empilhar(item_ativo, item_abaixo):
                                        pode_colocar = False

                                if pode_colocar:
                                    item_marcado = ItemBobina(
                                        tipo_papel=item_ativo.tipo_papel,
                                        formato_mm=item_ativo.formato_mm,
                                        diametro_mm=item_ativo.diametro_mm,
                                        quantidade=1,
                                    )
                                    item_marcado._idx_origem = idx_ativo
                                    st.session_state.grade[chave_celula] = item_marcado
                                    st.session_state.itens_restantes[idx_ativo] -= 1
                                    st.rerun()
                                else:
                                    st.toast("❌ Diâmetro incompatível com esta fiada, ou regra de empilhamento violada.")

            # --- Número da fiada (rodapé) ---
            cols_num = st.columns(total_fiadas)
            for f in range(1, total_fiadas + 1):
                cols_num[f - 1].caption(f"{f}")

            st.write("")

        # ==========================================
        # ETAPA 5 - SALVAR PDF (caso misto)
        # ==========================================
        _gerar_secao_pdf(veiculo, mapa_fiadas, total_fiadas, niveis_qtd)

    else:
        st.error("O sistema hoje suporta no máximo 2 diâmetros diferentes por carga.")
else:
    st.info("Nenhum item adicionado ainda.")