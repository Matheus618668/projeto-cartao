import streamlit as st
import pandas as pd
import os
from datetime import datetime
import gspread

# Conectar com o Google Sheets (credenciais)
gc = gspread.service_account(filename="credentials.json")  # Arquivo JSON salvo no projeto
SHEET_ID = "1CcrV5Gs3LwrLXgjLBgk2M02SAnDVJGuHhqY_pi56Mnw"
worksheet = gc.open_by_key(SHEET_ID).sheet1

# Caminhos locais
data_file = "data/compras.xlsx"
comprovante_folder = r"G:\Drives compartilhados\Moon Ventures - Admin Fin\Comprovantes"
os.makedirs(comprovante_folder, exist_ok=True)
os.makedirs("data", exist_ok=True)

# Colunas esperadas
colunas_corretas = ["Data", "Cartão", "Fornecedor", "Valor", "Parcelado", "Parcelas", "Comprador", "Comprovante"]

# Criar planilha local se não existir
if not os.path.exists(data_file):
    df = pd.DataFrame(columns=colunas_corretas)
    df.to_excel(data_file, index=False)

# Streamlit UI
st.set_page_config(page_title="Validador de Compras", layout="centered")
st.title("🧾 Validador de Compras com Cartão de Crédito")
st.subheader("Inserção de Dados da Compra")

# Entradas
data = datetime.today().strftime('%Y-%m-%d')
cartão = st.text_input("💳 Nome do cartão")
fornecedor = st.text_input("📦 Nome do Fornecedor")
valor = st.number_input("💰 Valor da Compra", min_value=0.0, format="%.2f")
parcelado = st.radio("💳 Foi parcelado?", ["Não", "Sim"])
parcelas = st.number_input("📅 Quantidade de Parcelas", min_value=1, max_value=12, value=1) if parcelado == "Sim" else 1
comprador = st.text_input("👤 Nome do Comprador")
comprovante = st.file_uploader("📁 Anexar Comprovante", type=["pdf", "jpg", "png"])

# Botão de salvar
if st.button("✅ Salvar Compra"):
    if fornecedor and valor > 0 and comprador and cartão:
        # Salvar comprovante localmente
        comprovante_path = ""
        filename = "Nenhum"
        if comprovante:
            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{comprovante.name}"
            comprovante_path = os.path.join(comprovante_folder, filename)
            with open(comprovante_path, "wb") as f:
                f.write(comprovante.read())

        # Atualizar planilha local
        df = pd.read_excel(data_file)

        # Corrigir colunas se necessário
        if list(df.columns) != colunas_corretas:
            df = df.reindex(columns=colunas_corretas)

        nova_linha = pd.DataFrame(
            [[data, cartão, fornecedor, valor, parcelado, parcelas, comprador, comprovante_path]],
            columns=colunas_corretas
        )
        df = pd.concat([df, nova_linha], ignore_index=True)
        df.to_excel(data_file, index=False)

        # Enviar ao Google Sheets
        worksheet.append_row([data, cartão, fornecedor, valor, parcelado, parcelas, comprador, filename])

        st.success("✅ Compra registrada com sucesso!")
    else:
        st.error("❌ Por favor, preencha todos os campos obrigatórios.")
