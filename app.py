import streamlit as st

# ✅ CONFIGURAÇÃO DA PÁGINA — PRIMEIRO COMANDO DO STREAMLIT
st.set_page_config(page_title="Validador de Compras", layout="centered")

# Agora sim pode seguir o resto
import pandas as pd
import os
from datetime import datetime, date
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import tempfile
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from dateutil.relativedelta import relativedelta
import requests # <-- NOVO: Biblioteca para buscar a cotação

# ================================
# NOVA FUNÇÃO: Buscar Cotação do Dólar
# ================================
@st.cache_data(ttl=3600) # Cache para evitar chamadas excessivas à API (atualiza a cada 1 hora)
def get_dolar_cotacao():
    """Busca a cotação atual do Dólar para Real usando a AwesomeAPI."""
    try:
        response = requests.get("https://economia.awesomeapi.com.br/last/USD-BRL")
        response.raise_for_status()  # Lança um erro se a requisição falhar
        data = response.json()
        cotacao = float(data['USDBRL']['bid'])
        return cotacao
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao buscar cotação do dólar: {e}")
        return None # Retorna None se não conseguir buscar

# ================================
# 1. Autenticação Google Sheets e Drive
# ================================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file"
]
credentials_dict = st.secrets["google_service_account"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
gc = gspread.authorize(credentials)

# PyDrive auth
gauth = GoogleAuth()
gauth.credentials = credentials
drive = GoogleDrive(gauth)

# ================================
# 2. Google Sheets
# ================================
SHEET_ID = "1CcrV5Gs3LwrLXgjLBgk2M02SAnDVJGuHhqY_pi56Mnw"
spreadsheet = gc.open_by_key(SHEET_ID)

# ================================
# 3. IDs das pastas fixas no Google Drive (por empresa)
# ================================
PASTAS_EMPRESA = {
    "Moon Ventures": "1pVdro4IFN08GEUSaCYDOwvS5dTCNAl41",
    "Minimal Club": "1c_lrNDj3s18j_vlGQCJLWjXYno9JgFrT",
    "Hoomy": "1wBwFFxuEYBnuPyMY13cH0zKEMqZtHDd9"
}

# ================================
# 4. Configuração de Usuários
# ================================
USUARIOS_CONFIG = {
    "ana_soier": {
        "nome": "Ana Soier - Facilities",
        "empresa": "Moon Ventures",
        "email": "ana.soier@moonventures.com.br",
        "limite_cartao": 100000.00
    },
    "joao": {
        "nome": "João Vicente - Marketing",
        "empresa": "Minimal Club",
        "email": "joao.vicente@moonventures.com.br",
        "limite_cartao": 10000.00
    },
    "guilherme": {
        "nome": "Guilherme Pettenati - Hoomy",
        "empresa": "Hoomy",
        "email": "guilherme.pettenati@hoomy.com.br",
        "limite_cartao": 8000.00
    },
    "linhares": {
        "nome": "Pedro Linhares - Logística",
        "empresa": "Moon Ventures",
        "email": "logistica@moonventures.com.br",
        "limite_cartao": 7500.00
    },
    "beatriz": {
        "nome": "Bia - Secretária",
        "empresa": "Moon Ventures",
        "email": "beatriz.cordeiro@moonventures.com.br",
        "limite_cartao": 20000.00
    },
    "marcella": {
        "nome": "Marcella - Compras Internas",
        "empresa": "Moon Ventures",
        "email": "marcella.leo@moonventures.com.br",
        "limite_cartao": 100000000.00
    },
    "alice": {
        "nome": "Alice - Mkt Hoomy",
        "empresa": "Hoomy",
        "email": "alice.coelho@hoomy.com.br",
        "limite_cartao": 4000.00
    },
    "ana_laura": {
        "nome": "Ana - Produtos",
        "empresa": "Moon Ventures",
        "email": "ana@moonventures.com.br",
        "limite_cartao": 4000.00
    },
}

# ================================
# Função para calcular gastos do usuário
# ================================
def calcular_gastos_usuario(usuario_info):
    """Calcula o total de gastos do usuário"""
    try:
        worksheet = get_worksheet_by_usuario(usuario_info)
        rows = worksheet.get_all_values()
        
        if len(rows) > 1:
            headers = rows[0]
            dados = rows[1:]
            
            # Criar DataFrame
            dados_limpos = []
            for linha in dados:
                if len(linha) < len(headers):
                    linha.extend([''] * (len(headers) - len(linha)))
                dados_limpos.append(linha[:len(headers)])
            
            df = pd.DataFrame(dados_limpos, columns=headers)
            
            # Converter valores
            def parse_valor(valor_str):
                try:
                    return float(str(valor_str).replace("R$", "").replace(".", "").replace(",", "."))
                except:
                    return 0.0
            
            if "Valor" in df.columns: # "Valor" aqui se refere ao valor em BRL
                df["Valor"] = df["Valor"].apply(parse_valor)
                
                # Remover duplicatas para não contar parcelas múltiplas vezes
                colunas_para_remover_duplicatas = ["Data", "Fornecedor", "Valor", "Comprador"]
                colunas_existentes = [col for col in colunas_para_remover_duplicatas if col in df.columns]
                
                if colunas_existentes:
                    df_unico = df.drop_duplicates(subset=colunas_existentes)
                    return df_unico["Valor"].sum()
        
        return 0.0
    except Exception:
        return 0.0

# ================================
# Função para exibir limite do cartão
# ================================
def exibir_limite_cartao(usuario_info, usuario_id):
    """Exibe o limite do cartão com barra de progresso"""
    limite_total = usuario_info.get("limite_cartao", 0)
    
    if limite_total > 0:
        # Calcular gastos
        total_gasto = calcular_gastos_usuario(usuario_info)
        limite_disponivel = limite_total - total_gasto
        percentual_usado = min((total_gasto / limite_total) * 100, 100)
        
        # Container para o limite
        with st.container():
            st.markdown("### 💳 Limite do Cartão")
            
            # Métricas
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Limite Total", f"R$ {limite_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            with col2:
                st.metric("Utilizado", f"R$ {total_gasto:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            with col3:
                st.metric("Disponível", f"R$ {limite_disponivel:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            
            # Barra de progresso
            if percentual_usado > 80:
                cor = "🔴"
                st.warning(f"⚠️ Atenção! Você já utilizou {percentual_usado:.1f}% do seu limite.")
            elif percentual_usado > 60:
                cor = "🟡"
            else:
                cor = "🟢"
            
            st.markdown(f"{cor} **Utilização do Limite:** {percentual_usado:.1f}%")
            st.progress(percentual_usado / 100)
            
            st.markdown("---")

# ================================
# 5. Função para obter usuário da URL
# ================================
def get_usuario_from_url():
    """Obtém o usuário dos parâmetros da URL"""
    try:
        query_params = st.query_params
        usuario_id = query_params.get("user", "")
        if usuario_id:
            usuario_id = usuario_id.lower().strip()
            if usuario_id in USUARIOS_CONFIG:
                return usuario_id, USUARIOS_CONFIG[usuario_id]
        return None, None
    except Exception as e:
        return None, None

# ================================
# 6. Função para obter a aba do usuário
# ================================
# <-- ATUALIZADO: Adicionadas novas colunas no cabeçalho
def get_worksheet_by_usuario(usuario_info):
    """Cria ou obtém a aba específica do usuário"""
    nome_aba = usuario_info["nome"]
    try:
        return spreadsheet.worksheet(nome_aba)
    except gspread.exceptions.WorksheetNotFound:
        try:
            st.info(f"Criando nova aba para {nome_aba}...")
            worksheet = spreadsheet.add_worksheet(title=nome_aba, rows="1000", cols="25") # Aumentei o número de colunas
            
            # Adiciona cabeçalhos na nova aba (com as colunas de moeda)
            headers = [
                "Data", "Empresa", "Fornecedor", "Valor", "Parcelado", "Parcelas", 
                "Valor Parcela", "Comprador", "Parcela", "Descrição", "Comprovante", "Data da Compra",
                "Moeda", "Valor Original", "Cotação (BRL)"
            ]
            worksheet.append_row(headers)
            
            st.success(f"Aba '{nome_aba}' criada com sucesso!")
            return worksheet
            
        except Exception as e:
            st.error(f"Erro ao criar aba para {nome_aba}: {e}")
            return spreadsheet.sheet1
    except Exception as e:
        st.error(f"Erro inesperado ao acessar a aba '{nome_aba}': {e}")
        return spreadsheet.sheet1

# ================================
# 7. Função para upload no Google Drive
# ================================
def upload_to_drive(file, empresa):
    folder_id = PASTAS_EMPRESA.get(empresa)
    if not folder_id:
        st.error(f"❌ ID da pasta não encontrado para a empresa: {empresa}")
        st.stop()

    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.name)[-1]) as tmp:
        tmp.write(file.read())
        tmp_path = tmp.name

    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.name}"

    try:
        gfile = drive.CreateFile({'title': filename, 'parents': [{'id': folder_id}]})
        gfile.SetContentFile(tmp_path)
        gfile.Upload()
        gfile.InsertPermission({
            'type': 'anyone',
            'value': 'anyone',
            'role': 'reader'
        })
        return gfile['alternateLink'], tmp_path

    except Exception as e:
        st.error(f"❌ Erro ao fazer upload para o Drive: {e}")
        st.stop()

# ================================
# 8. Envio de Email com Anexo
# ================================
def enviar_email(destinatario, dados, anexo_path=None, anexo_nome=None):
    config = st.secrets["email"]

    msg = MIMEMultipart()
    msg['From'] = config["sender"]
    msg['To'] = destinatario
    msg['Subject'] = "Confirmação de Registro de Compra"

    corpo = "".join([f"<b>{chave}:</b> {valor}<br>" for chave, valor in dados.items()])
    msg.attach(MIMEText(corpo, 'html'))

    if anexo_path and anexo_nome:
        try:
            with open(anexo_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={anexo_nome}")
                msg.attach(part)
        except Exception as e:
            st.warning(f"❗ Não foi possível anexar o arquivo: {e}")

    try:
        with smtplib.SMTP(config["smtp_server"], config["smtp_port"]) as server:
            server.starttls()
            server.login(config["sender"], config["password"])
            server.sendmail(config["sender"], destinatario, msg.as_string())
    except Exception as e:
        st.warning(f"❌ Email não enviado: {e}")

# ================================
# 9. Função para calcular limite utilizado
# ================================
def calcular_limite_utilizado(worksheet, usuario_info, data_referencia=None):
    """
    Calcula o limite utilizado considerando:
    - Fatura fecha no último dia do mês
    - Vencimento dia 5
    - Parcelas futuras comprometem o limite
    """
    if data_referencia is None:
        data_referencia = datetime.now()
    
    try:
        rows = worksheet.get_all_values()
        if len(rows) <= 1:
            return 0.0
        
        headers = rows[0]
        dados = rows[1:]
        
        df = pd.DataFrame(dados, columns=headers[:len(dados[0])])
        
        def parse_valor(valor_str):
            try:
                return float(str(valor_str).replace("R$", "").replace(".", "").replace(",", "."))
            except:
                return 0.0
        
        if "Valor Parcela" in df.columns: # O valor da parcela já está em BRL
            df["Valor Parcela"] = df["Valor Parcela"].apply(parse_valor)
        else:
            return 0.0
        
        if "Data da Compra" in df.columns:
            df["Data da Compra"] = pd.to_datetime(df["Data da Compra"], errors='coerce')
        else:
            return 0.0
        
        if "Comprador" in df.columns:
            df = df[df["Comprador"] == usuario_info['nome']]
        
        limite_utilizado = 0.0
        
        for idx, row in df.iterrows():
            try:
                if pd.isna(row.get("Data da Compra")) or pd.isna(row.get("Parcela")):
                    continue
                
                data_compra = row["Data da Compra"]
                parcela_info = str(row.get("Parcela", "1/1")).split("/")
                
                if len(parcela_info) != 2:
                    continue
                
                parcela_atual = int(parcela_info[0])
                valor_parcela = float(row.get("Valor Parcela", 0))
                
                data_vencimento = data_compra.replace(day=5)
                if data_vencimento <= data_compra:
                    data_vencimento = data_vencimento + relativedelta(months=1)
                
                data_vencimento = data_vencimento + relativedelta(months=parcela_atual-1)
                
                if data_vencimento > data_referencia:
                    limite_utilizado += valor_parcela
            except Exception as e:
                continue
        
        return limite_utilizado
        
    except Exception as e:
        st.error(f"Erro ao calcular limite: {e}")
        return 0.0

# ================================
# 10. Função para gerar links personalizados
# ================================
def gerar_links_usuarios():
    """Gera links personalizados para cada usuário"""
    base_url = "https://projeto-cartao-hvavcfzkhdesmg9jtrygne.streamlit.app"

    st.subheader("🔗 Links Personalizados dos Usuários")
    st.info("Compartilhe estes links com cada usuário para acesso direto:")

    for usuario_id, info in USUARIOS_CONFIG.items():
        link = f"{base_url}?user={usuario_id}"
        st.markdown(f"**{info['nome']}** ({info['empresa']})")
        st.code(link)

        if st.button(f"🧪 Testar link do {info['nome']}", key=f"test_{usuario_id}"):
            st.query_params.update({"user": usuario_id})
            st.rerun()

    st.markdown("---")


# ================================
# 11. App Principal
# ================================
usuario_id, usuario_info = get_usuario_from_url()

if not usuario_info:
    st.title("🔧 Configuração do Sistema")
    st.error("⚠️ Nenhum usuário válido identificado na URL.")
    current_url = st.query_params
    st.info(f"🔍 URL atual detectada: {dict(current_url)}")
    st.markdown("""
    ### ❗ Problema Detectado:
    Para usar o sistema, você precisa acessar através de um link personalizado.
    
    ### 📋 Como usar o sistema:
    1. Cada usuário deve ter seu próprio link personalizado
    2. Os links direcionam automaticamente para a aba correta na planilha
    3. **Use os links abaixo para acessar o sistema:**
    """)
    gerar_links_usuarios()
    st.markdown("""
    ### 🔧 Para adicionar novos usuários:
    Edite a configuração `USUARIOS_CONFIG` no código.
    """)
    if st.button("🧪 Testar com usuário João"):
        st.query_params.update({"user": "joao"})
        st.rerun()
    st.stop()

# ================================
# Interface Principal (usuário válido)
# ================================
# <-- ATUALIZADO: Adicionadas novas colunas
data_file = "data/compras.xlsx"
os.makedirs("data", exist_ok=True)
colunas_corretas = [
    "Data", "Empresa", "Fornecedor", "Valor", "Parcelado", "Parcelas", 
    "Valor Parcela", "Comprador", "Parcela", "Descrição", "Comprovante", "Data da Compra",
    "Moeda", "Valor Original", "Cotação (BRL)"
]
if not os.path.exists(data_file):
    pd.DataFrame(columns=colunas_corretas).to_excel(data_file, index=False)

if "new" in st.query_params:
    for chave in list(st.session_state.keys()):
        if chave not in ["google_service_account", "email"]:
            del st.session_state[chave]
    if "new" in st.query_params:
        del st.query_params["new"]

st.markdown("""
<style>
    .main {
        padding-left: 40px;
        padding-right: 40px;
    }
</style>
""", unsafe_allow_html=True)

st.title("💳 Gestor de Compras Corporativas")
st.markdown(f"**👤 Usuário:** {usuario_info['nome']} | **🏢 Empresa:** {usuario_info['empresa']}")

menu = st.sidebar.selectbox("📌 Navegação", ["Inserir Compra", "Visualizar Compras"])

if menu == "Inserir Compra":
    st.subheader("Inserção de Dados da Compra")
    
    if "limite_cartao" in usuario_info:
        st.markdown("### 💳 Limite do Cartão")
        worksheet = get_worksheet_by_usuario(usuario_info)
        limite_total = usuario_info.get("limite_cartao", 0)
        limite_utilizado = calcular_limite_utilizado(worksheet, usuario_info)
        limite_disponivel = limite_total - limite_utilizado
        percentual_utilizado = (limite_utilizado / limite_total * 100) if limite_total > 0 else 0
        
        progress = min(percentual_utilizado / 100, 1.0)
        st.progress(progress)
        
        col1, col2, col3 = st.columns([1.5, 1.5, 1.5])
        with col1:
            st.metric("Limite Total", f"R$ {limite_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        with col2:
            st.metric("Utilizado", f"R$ {limite_utilizado:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), delta=f"-{percentual_utilizado:.1f}%", delta_color="inverse")
        with col3:
            st.metric("Disponível", f"R$ {limite_disponivel:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        
        if percentual_utilizado > 90:
            st.error("⚠️ Atenção: Você está próximo do limite do cartão!")
        elif percentual_utilizado > 70:
            st.warning("⚠️ Atenção: Você já utilizou mais de 70% do seu limite.")
        
        hoje = datetime.now()
        proximo_vencimento = hoje.replace(day=5)
        if hoje.day >= 5:
            proximo_vencimento = (hoje.replace(day=1) + relativedelta(months=1)).replace(day=5)
        dias_para_renovacao = (proximo_vencimento - hoje).days
        st.info(f"💳 Seu limite será renovado em {dias_para_renovacao} dias (dia {proximo_vencimento.strftime('%d/%m/%Y')})")
        st.markdown("---")
    
    empresa_selecionada = usuario_info['empresa']
    if usuario_info['nome'] in ["Ana Soier - Facilities", "Pedro Linhares - Logística", "Bia - Secretária", "Marcella - Compras Internas"]:
        empresas_disponiveis = ["Moon Ventures", "Minimal Club", "Hoomy"]
        empresa_selecionada = st.selectbox("🏢 Selecione a empresa para esta compra:", options=empresas_disponiveis, index=empresas_disponiveis.index(usuario_info['empresa']) if usuario_info['empresa'] in empresas_disponiveis else 0)
    else:
        st.markdown(f"🏢 **Empresa:** {usuario_info['empresa']}")
    
    campos = {"fornecedor": "", "valor_str": "", "parcelado": "Não", "parcelas": 1, "descricao": "", "email_opcional": ""}
    for campo, valor_inicial in campos.items():
        if campo not in st.session_state:
            st.session_state[campo] = valor_inicial

    data_compra = st.date_input("📅 Data da Compra", value=date.today())
    fornecedor = st.text_input("📦 Nome do Fornecedor", key="fornecedor")
    
    # <-- INÍCIO DAS MUDANÇAS PARA DÓLAR -->
    col_moeda, col_valor = st.columns([1, 2])
    with col_moeda:
        moeda = st.selectbox("Moeda", ["BRL", "USD"])
    with col_valor:
        valor_str = st.text_input("💰 Valor da Compra (total)", placeholder="Ex: 399,80", key="valor_str")

    cotacao_dolar = None
    valor_convertido_brl = 0.0
    valor_original = 0.0

    try:
        valor_original = float(valor_str.replace(",", "."))
    except (ValueError, AttributeError):
        valor_original = 0.0

    if moeda == "USD":
        cotacao_dolar = get_dolar_cotacao()
        if cotacao_dolar:
            valor_convertido_brl = valor_original * cotacao_dolar
            st.info(f"Cotação do Dólar: R$ {cotacao_dolar:,.2f} | Valor em BRL: R$ {valor_convertido_brl:,.2f}")
        else:
            st.error("Não foi possível obter a cotação do dólar. O valor não será convertido.")
            valor_convertido_brl = valor_original # Fallback
    else:
        valor_convertido_brl = valor_original

    valor_final_brl = valor_convertido_brl
    valor_formatado = f"R$ {valor_final_brl:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    st.markdown(f"🔎 Valor final (BRL) que será registrado: **{valor_formatado}**")
    # <-- FIM DAS MUDANÇAS PARA DÓLAR -->

    parcelado = st.radio("💳 Foi parcelado?", ["Não", "Sim"], key="parcelado")
    if parcelado == "Sim":
        parcelas = st.number_input("📅 Quantidade de Parcelas", min_value=1, max_value=12, value=st.session_state["parcelas"], key="parcelas")
    else:
        parcelas = 1

    valor_parcela = valor_final_brl / parcelas if parcelas > 0 else 0.0
    st.markdown(f"💵 **Valor de cada parcela:** R$ {valor_parcela:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    email_opcional = st.text_input("📧 E-mail (opcional)", value=usuario_info['email'], key="email_opcional")
    descricao = st.text_area("📝 Descrição da Compra", key="descricao")
    comprovante = st.file_uploader("📁 Anexar Comprovante", type=["pdf", "jpg", "png"])

    if st.button("✅ Salvar Compra"):
        erros = []
        if not fornecedor: erros.append("Fornecedor não informado.")
        if valor_final_brl <= 0: erros.append("Valor deve ser maior que zero.")
        if not descricao: erros.append("Descrição da compra não informada.")
        if not comprovante: erros.append("Comprovante não anexado.")
        if moeda == "USD" and not cotacao_dolar: erros.append("Não foi possível obter a cotação do dólar para salvar.")

        limite_total = usuario_info.get('limite_cartao', 0)
        if limite_total > 0:
            worksheet_temp = get_worksheet_by_usuario(usuario_info)
            limite_utilizado_atual = calcular_limite_utilizado(worksheet_temp, usuario_info)
            limite_disponivel = limite_total - limite_utilizado_atual
            
            impacto_limite = valor_final_brl
            
            if impacto_limite > limite_disponivel:
                erros.append(f"Limite insuficiente! Disponível: R$ {limite_disponivel:,.2f}, Necessário: R$ {impacto_limite:,.2f}")

        if erros:
            st.error("\n".join(["❌ " + erro for erro in erros]))
        else:
            link_drive, path_comprovante = upload_to_drive(comprovante, empresa_selecionada)
            worksheet = get_worksheet_by_usuario(usuario_info)
            
            # <-- ATUALIZADO: Adiciona novas informações na linha a ser salva
            novas_linhas = []
            for i in range(parcelas):
                parcela_atual = f"{i+1}/{parcelas}" if parcelas > 1 else "1/1"
                linha = [
                    datetime.today().strftime('%Y-%m-%d'),
                    empresa_selecionada,
                    fornecedor,
                    valor_final_brl,
                    parcelado,
                    parcelas,
                    valor_parcela,
                    usuario_info['nome'],
                    parcela_atual,
                    descricao,
                    link_drive,
                    data_compra.strftime('%Y-%m-%d'),
                    moeda, # Nova coluna
                    valor_original, # Nova coluna
                    cotacao_dolar if cotacao_dolar else "" # Nova coluna
                ]
                novas_linhas.append(linha)
            
            df = pd.read_excel(data_file)
            if list(df.columns) != colunas_corretas:
                df = df.reindex(columns=colunas_corretas)
            
            df = pd.concat([df, pd.DataFrame(novas_linhas, columns=colunas_corretas)], ignore_index=True)
            df.to_excel(data_file, index=False)
            
            for linha in novas_linhas:
                worksheet.append_row(linha)
            
            if email_opcional:
                dados_email = {
                    "Data": datetime.today().strftime('%Y-%m-%d'),
                    "Empresa": usuario_info['empresa'],
                    "Fornecedor": fornecedor,
                    "Valor Total": f"{moeda} {valor_original:,.2f}" if moeda == "USD" else f"R$ {valor_final_brl:,.2f}",
                    "Cotação Utilizada": f"R$ {cotacao_dolar:,.2f}" if cotacao_dolar else "N/A",
                    "Valor Final em BRL": valor_formatado,
                    "Parcelas": parcelas,
                    "Comprador": usuario_info['nome'],
                    "Descrição": descricao,
                }
                enviar_email(email_opcional, dados_email, anexo_path=path_comprovante, anexo_nome=comprovante.name)
            
            st.success("✅ Compra registrada com sucesso!")
            st.session_state["compra_salva"] = True

    if st.session_state.get("compra_salva", False):
        st.markdown("---")
        if st.button("🆕 Nova Compra"):
            st.query_params["new"] = "1"
            st.session_state["compra_salva"] = False
            st.rerun()

elif menu == "Visualizar Compras":
    st.subheader(f"📊 Compras de {usuario_info['nome']}")
    exibir_limite_cartao(usuario_info, usuario_id)
    
    try:
        worksheet = get_worksheet_by_usuario(usuario_info)
        rows = worksheet.get_all_values()
        
        if len(rows) > 1:
            headers = rows[0]
            dados = rows[1:]
            
            dados_limpos = []
            for linha in dados:
                if len(linha) < len(headers):
                    linha.extend([''] * (len(headers) - len(linha)))
                dados_limpos.append(linha[:len(headers)])
            
            df = pd.DataFrame(dados_limpos, columns=headers)

            def parse_valor(valor_str):
                try:
                    return float(str(valor_str).replace(",", ".")) # Ajuste para aceitar o formato da API
                except:
                    return 0.0
            
            # <-- ATUALIZADO: Converte também as novas colunas
            colunas_valor = ["Valor", "Valor Parcela", "Valor Original", "Cotação (BRL)"]
            for col in colunas_valor:
                if col in df.columns:
                    df[col] = df[col].apply(parse_valor)

            col1, col2 = st.columns(2)
            with col1:
                if "Fornecedor" in df.columns:
                    filtro_fornecedor = st.selectbox("Filtrar por Fornecedor:", options=["Todos"] + sorted(df["Fornecedor"].dropna().unique().tolist()))
                else: filtro_fornecedor = "Todos"
            with col2:
                if "Data da Compra" in df.columns:
                    datas_unicas = sorted(df["Data da Compra"].dropna().unique().tolist(), reverse=True)
                    filtro_data = st.selectbox("Filtrar por Data:", options=["Todas"] + datas_unicas)
                else: filtro_data = "Todas"

            if filtro_fornecedor != "Todos" and "Fornecedor" in df.columns:
                df = df[df["Fornecedor"] == filtro_fornecedor]
            if filtro_data != "Todas" and "Data da Compra" in df.columns:
                df = df[df["Data da Compra"] == filtro_data]

            # <-- ATUALIZADO: Formata as novas colunas para exibição
            df_exibicao = df.copy()
            df_exibicao["Valor"] = df_exibicao["Valor"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            df_exibicao["Valor Parcela"] = df_exibicao["Valor Parcela"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            df_exibicao["Valor Original"] = df_exibicao["Valor Original"].apply(lambda x: f"{x:,.2f}")
            df_exibicao["Cotação (BRL)"] = df_exibicao["Cotação (BRL)"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if x > 0 else "")
            
            # Reordenar colunas para melhor visualização
            ordem_colunas = [
                "Data da Compra", "Fornecedor", "Descrição", "Moeda", "Valor Original", 
                "Cotação (BRL)", "Valor", "Parcela", "Valor Parcela", "Comprovante"
            ]
            colunas_existentes_reordenadas = [col for col in ordem_colunas if col in df_exibicao.columns]
            
            st.dataframe(df_exibicao[colunas_existentes_reordenadas], use_container_width=True)

            if not df.empty and "Valor" in df.columns:
                st.markdown("---")
                st.markdown("### 💰 Resumo Financeiro")
                
                colunas_para_remover_duplicatas = ["Data", "Fornecedor", "Valor", "Comprador"]
                colunas_existentes = [col for col in colunas_para_remover_duplicatas if col in df.columns]
                
                if colunas_existentes:
                    df_unico = df.drop_duplicates(subset=colunas_existentes)
                    total_gasto = df_unico["Valor"].sum()
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Gasto", f"R$ {total_gasto:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    with col2:
                        st.metric("Número de Compras", len(df_unico))
                    with col3:
                        valor_medio = total_gasto / len(df_unico) if len(df_unico) > 0 else 0
                        st.metric("Valor Médio", f"R$ {valor_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                
                if "Fornecedor" in df.columns:
                    st.markdown("### 📊 Gastos por Fornecedor")
                    grafico_fornecedor = df_unico.groupby("Fornecedor")["Valor"].sum().reset_index()
                    grafico_fornecedor = grafico_fornecedor.sort_values("Valor", ascending=False)
                    st.bar_chart(data=grafico_fornecedor, x="Fornecedor", y="Valor")
        else:
            st.info(f"Nenhuma compra registrada ainda para {usuario_info['nome']}.")
    except Exception as e:
        st.error(f"Erro ao carregar suas compras: {e}")

# Rodapé com informações do usuário
st.sidebar.markdown("---")
st.sidebar.markdown("### 👤 Informações do Usuário")
st.sidebar.markdown(f"**Nome:** {usuario_info['nome']}")
st.sidebar.markdown(f"**Empresa:** {usuario_info['empresa']}")
st.sidebar.markdown(f"**Email:** {usuario_info['email']}")

# Botão para gerar links - apenas para admins (determine quem são os admins)
admin_usuarios = ["joao"]  # Defina aqui quais usuários são administradores
is_admin = usuario_id in admin_usuarios

if is_admin and st.sidebar.button("🔗 Ver Links de Todos Usuários"):
    with st.sidebar:
        gerar_links_usuarios(mostrar_todos=True)
else:
    # Botão para ver apenas o próprio link
    if st.sidebar.button("🔗 Ver Meu Link de Acesso"):
        with st.sidebar:
            gerar_links_usuarios(mostrar_todos=False, usuario_atual=usuario_id)
