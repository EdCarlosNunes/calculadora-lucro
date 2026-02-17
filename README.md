# 💰 Calculadora de Lucro para Marketplaces

Uma aplicação web premium desenvolvida com Streamlit para calcular a precificação e margem de lucro real em vendas no **Mercado Livre**, **Amazon** e **Shopee**.

🔗 **[Acesse a Calculadora Online](#)** *(Insira seu link do Streamlit Cloud aqui)*

## ✨ Funcionalidades

### 📊 Mercados Suportados
*   **Mercado Livre**: Cálculo detalhado considerando Clássico/Premium, taxas por categoria, e custos de envio.
*   **Amazon**: Suporte a planos Individual/Profissional, categorias e taxas de fechamento.
*   **Shopee**: Cálculo de comissões (Padrão/Oficial), Programa de Frete Grátis e taxas de transação.

### 💼 Gestão de Custos
*   **Despesas Fixas Mensais**: Rateio automático de custos fixos (aluguel, internet, salários) baseado na estimativa de vendas mensais.
*   **Custos Variáveis**: Impostos, embalagem, frete e custos extras por produto.

### 💾 Salvar e Exportar
*   **Simulações**: Salve múltiplos cenários de precificação para diferentes produtos.
*   **Comparativo**: Visualize uma tabela com todas as suas simulações salvas.
*   **Exportação**: Baixe seus dados em **CSV** para abrir no Excel ou Google Sheets.

### 🎨 Interface Premium
*   Design moderno e responsivo (Glassmorphism).
*   Gráficos interativos (Sunburst/Donut) para visualização de custos vs. lucro.
*   Indicadores claros de ROI, Margem Líquida e Markup.

## 🚀 Como Rodar Localmente

1.  **Clone o repositório**
    ```bash
    git clone https://github.com/seu-usuario/calculadora-lucro.git
    cd calculadora-lucro
    ```

2.  **Instale as dependências**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Execute a aplicação**
    ```bash
    streamlit run app.py
    ```

## 🛠️ Tecnologias Utilizadas
*   **Python 3.10+**
*   **Streamlit**: Framework para web apps de dados.
*   **Pandas**: Manipulação de dados e exportação.
*   **Plotly**: Gráficos interativos.

## 📦 Estrutura do Projeto
*   `app.py`: Código principal da aplicação.
*   `requirements.txt`: Lista de dependências.
*   `.streamlit/config.toml`: Configurações de tema e aparência.

---
Desenvolvido com ❤️ para vendedores de e-commerce.
