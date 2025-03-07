import os
import requests
import json
from bs4 import BeautifulSoup
from sec_api import XbrlApi

HTTP_USER_AGENT_NAME = "IramLee"
HTTP_USER_AGENT_EMAIL = "iram.lee@gmail.com"


def get_cik_from_ticker(ticker : str) -> str:
    with open("company_tickers.json", "r") as file:
        data = json.load(file)

        cik = ""
        for company in data.keys():
            if data[company]["ticker"] == ticker:
                cik = str(data[company]["cik_str"])
                break

        if len(cik) < 10:
            # Pad with leading zeros
            cik = "0" * (10 - len(cik)) + cik

        return cik


def get_most_recent_10k_balance_sheet(ticker : str) -> dict:
    """ Obtains the most recent cash flow statement in a 10-K report filing to the SEC for the given ticker symbol.
        The returned python dict contains the financial data and follows the US GAAP taxonomy.
    Args:
        ticker (str): The ticker symbol for the company.
    """
    cik = get_cik_from_ticker(ticker)

    # Step 1: Get submission history
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    headers = {"User-Agent": f"{HTTP_USER_AGENT_NAME} ({HTTP_USER_AGENT_EMAIL})"}
    response = requests.get(url, headers=headers)
    data = response.json()

    # Step 2: Find the most recent 10-K
    recent_filings = data["filings"]["recent"]
    for i, form in enumerate(recent_filings["form"]):
        if form == "10-K":
            accession_number = recent_filings["accessionNumber"][i]
            break

    # Step 3: Construct the filing URL
    accession_number_no_dashes = accession_number.replace("-", "")
    cik_no_leading_zeros = cik.lstrip("0")
    filing_text_file_url = f"https://www.sec.gov/Archives/edgar/data/{cik_no_leading_zeros}/{accession_number_no_dashes}/{accession_number}-index.html"

    ten_k_url = get_10k_main_doc(filing_text_file_url) 
    filing_data = extract_financial_statements(ten_k_url)
    
    return filing_data


def get_10k_main_doc(filing_text_file_url : str) -> str:
    headers = {"User-Agent": f"{HTTP_USER_AGENT_NAME} ({HTTP_USER_AGENT_EMAIL})"}
    
    response = requests.get(filing_text_file_url, headers=headers)
    if response.status_code != 200:
        return f"Error: {response.status_code}"
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Find the main 10-K filing document (usually the first HTML file)
    for row in soup.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) >= 2 and "10-K" in cols[1].text:
            doc_link = cols[2].a["href"]
            return f"https://www.sec.gov{doc_link}"

    return "Main filing document not found."


def extract_financial_statements(ten_k_url : str) -> dict:
    MY_SEC_API_KEY = os.environ.get("MY_SEC_API_KEY")
    xbrlApi = XbrlApi(MY_SEC_API_KEY)

    # 10-K HTM file URL
    xbrl_json = xbrlApi.xbrl_to_json(
        htm_url=ten_k_url
    )

    financial_data = {
        #"IncomeStatement": xbrl_json["StatementsOfIncome"],
        #"BalanceSheet": xbrl_json["BalanceSheets"],
        "CashFlowStatement": xbrl_json["StatementsOfCashFlows"]
    }

    return financial_data