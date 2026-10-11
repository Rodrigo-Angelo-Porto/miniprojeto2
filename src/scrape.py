"""
Etapa 1 — coleta de dados de tabuademares.com/br/paraiba/joao-pessoa.

Objetivo: gravar em data/raw/ os CSVs que as Etapas 2 e 3 vão consumir.

    mares_<ano>.csv      tábua de marés do ano (4 marés por dia)
    mares_previsao.csv   marés do mês corrente, para cruzar com a previsão
    ondas.csv            altura de onda hora a hora (~7 dias à frente)
    vento.csv            velocidade do vento hora a hora (~7 dias à frente)

As funções abaixo estão vazias de propósito. Abra o site no navegador, use o
DevTools para descobrir onde cada dado vive no HTML e implemente o parse.
As colunas de cada CSV são sua decisão — só precisam sustentar as etapas
seguintes (ver README).

Rodar com: uv run python src/scrape.py
"""

import re
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Os imports acima são o ponto de partida: você vai usar todos eles.
# Seu editor pode marcá-los como não usados até você preencher as funções.

URL_BASE = "https://tabuademares.com/br/paraiba/joao-pessoa"
URL_ONDAS = f"{URL_BASE}/previsao/ondas"
URL_VENTO = f"{URL_BASE}/previsao/vento"

# Servidores rejeitam clientes sem User-Agent. Identifique-se.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Segundos de pausa entre requests. Não tire isso.
PAUSA = 1.5

DIR_RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


def baixar_html(url: str, dados_post: dict | None = None) -> str:
    if dados_post is None:
        resp = requests.get(url, headers=HEADERS)
    else:
        resp = requests.post(url, headers=HEADERS, data=dados_post)
    resp.raise_for_status()
    return resp.text


def parsear_mares(html: str, ano: int, mes: int) -> list[dict]:
    """Extrai da tábua mensal uma linha por evento de maré.

    Cada dia tem cerca de 4 eventos (duas altas, duas baixas). Além de
    horário e altura, a página traz informação de coeficiente de maré e de
    fase da lua — decida o que vale a pena capturar.

    TODO: localizar a tabela no HTML e percorrer as linhas.
    """
    soup = BeautifulSoup(html, "lxml")
    tabela = soup.find("table", id="tabla_mareas")
    
    linhas = [tr for tr in tabela.find_all("tr") if tr.get("onclick")]

    resultado = []

    for tr in linhas:
        dia = int(tr.find("div", class_="tabla_mareas_dia_numero").get_text(strip=True))
        coef = int(tr.find("div", class_="tabla_mareas_coeficiente_numero").find(string=True, recursive=False).strip())

        # a fase da lua vem como ícone; o número está na classe "icon-hsNN"
        lua = tr.find("td", class_="tabla_mareas_luna").find("span")
        idade_lua = int(re.search(r"icon-hs(\d+)", " ".join(lua["class"])).group(1))

        for celula in tr.find_all("td", class_="tabla_mareas_marea"):
            hora_div = celula.find("div", class_="tabla_mareas_marea_hora")
            if hora_div is None or not hora_div.get_text(strip=True):
                continue
            hora = hora_div.get_text(strip=True)
            altura = celula.find("span", class_="tabla_mareas_marea_altura_numero").get_text(strip=True)
            altura = float(altura.replace(",", "."))
            tipo = "baixa" if "tabla_mareas_hora_bajamar" in hora_div["class"] else "alta"    
    
            resultado.append({
                "data": datetime(ano, mes, dia).date(),
                "hora": hora,
                "altura_m": altura,
                "tipo": tipo,
                "coeficiente": coef,
                "idade_lua": idade_lua,
            })

    return resultado


MESES = {
    "JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12
}

def parsear_previsao(html: str, ano: int) -> list[dict]:
    """Extrai leituras horárias das páginas de previsão de onda e de vento.

    As duas páginas têm o mesmo layout: um bloco por dia, com uma linha por
    hora dentro. Uma função só deve dar conta das duas.

    TODO: percorrer os blocos de dia e, dentro deles, as linhas de hora.
    Atenção à data: o bloco mostra dia e mês abreviado, sem o ano.
    """
    soup = BeautifulSoup(html, "lxml")
    resultado = []
    mes_anterior = 0

    for bloco in soup.find_all("div", class_="f_cont"):
        dia = int(bloco.find("span", class_="dia").get_text(strip=True))
        mes = MESES[bloco.find("span", class_="mes").get_text(strip=True).upper()]
        if mes < mes_anterior:
            ano += 1
        mes_anterior = mes

        for linha in bloco.find_all("div", class_="f_temp_horas"):
            hora, direcao = [d.get_text(strip=True) for d in linha.find_all("div", class_="f_temp_hora")]
            texto = linha.find("div", class_="grafico_temp_barra_relleno").get_text(" ", strip=True)
            valor = float(texto.split()[0].replace(",", "."))
            resultado.append({
                "data": datetime(ano, mes, dia).date(),
                "hora": hora,
                "valor": valor,
                "direcao": direcao,
            })
    return resultado


def coletar_mares_do_ano(ano: int) -> pd.DataFrame:
    """Junta os 12 meses da tábua de marés de `ano` num DataFrame.

    TODO: iterar de janeiro a dezembro, chamar `baixar_html` + `parsear_mares`
    e dormir `PAUSA` entre requisições.
    """
    linhas = []

    for mes in range(1, 13):
        html = baixar_html(URL_BASE, {"fecha": f"{ano}-{mes:02d}-01"})
        linhas.extend(parsear_mares(html, ano, mes))
        time.sleep(PAUSA)
        
    return pd.DataFrame(linhas)


def main(ano: int = 2025) -> None:
    DIR_RAW.mkdir(parents=True, exist_ok=True)
    hoje = datetime.now()

    mares_ano = coletar_mares_do_ano(ano)
    mares_ano.to_csv(DIR_RAW / f"mares_{ano}.csv", index=False)
    print(f"mares_{ano}.csv: {len(mares_ano)} linhas")
    time.sleep(PAUSA)

    html = baixar_html(URL_BASE)
    mares_mes = pd.DataFrame(parsear_mares(html, hoje.year, hoje.month))
    mares_mes.to_csv(DIR_RAW / "mares_previsao.csv", index=False)
    print(f"mares_previsao.csv: {len(mares_mes)} linhas")
    time.sleep(PAUSA)

    ondas = pd.DataFrame(parsear_previsao(baixar_html(URL_ONDAS), hoje.year))
    ondas.to_csv(DIR_RAW / "ondas.csv", index=False)
    print(f"ondas.csv: {len(ondas)} linhas")
    time.sleep(PAUSA)

    vento = pd.DataFrame(parsear_previsao(baixar_html(URL_VENTO), hoje.year))
    vento.to_csv(DIR_RAW / "vento.csv", index=False)
    print(f"vento.csv: {len(vento)} linhas")


if __name__ == "__main__":
    main()
