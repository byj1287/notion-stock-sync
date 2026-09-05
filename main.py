import os
import requests
import yfinance as yf
from bs4 import BeautifulSoup

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID = os.environ["NOTION_DATABASE_ID"].strip()

# 노션 공식 API 헤더
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def get_krx_price(code):
    # 네이버페이 증권 종가 크롤링
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    price_tag = soup.select_one(".no_today .blind")
    return int(price_tag.text.replace(",", "")) if price_tag else None

def get_us_price(ticker):
    # 야후 파이낸스 미국 주가
    stock = yf.Ticker(ticker)
    data = stock.history(period="1d")
    return round(float(data["Close"].iloc[-1]), 2) if not data.empty else None

def get_usd_krw_rate():
    # 원/달러 환율
    fx = yf.Ticker("KRW=X")
    data = fx.history(period="1d")
    return round(float(data["Close"].iloc[-1]), 2) if not data.empty else 1350.0

def main():
    rate = get_usd_krw_rate()
    
    # 노션 데이터베이스 직접 조회 (REST API)
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    res = requests.post(url, headers=NOTION_HEADERS)
    
    if res.status_code != 200:
        print(f"노션 조회 실패: {res.status_code}, {res.text}")
        return
        
    pages = res.json().get("results", [])
    
    for page in pages:
        props = page["properties"]
        
        # 1. 티커 확인
        ticker_cell = props.get("티커", {}).get("rich_text", []) or props.get("주식 티커", {}).get("rich_text", [])
        if not ticker_cell:
            continue
        ticker = ticker_cell[0]["plain_text"].strip()
        
        # 2. 국가/시장 확인
        country_select = props.get("국가", {}).get("select") or props.get("시장", {}).get("select")
        country_name = country_select.get("name", "") if country_select else ""
        
        # 3. 가격 및 환율 수집
        current_price = None
        current_fx = 1
        
        if "미국" in country_name or "해외" in country_name:
            current_price = get_us_price(ticker)
            current_fx = rate
        else:
            clean_code = "".join(filter(str.isdigit, ticker))
            if clean_code:
                current_price = get_krx_price(clean_code)
        
        # 4. 노션 DB 속성 업데이트
        if current_price is not None:
            update_data = {}
            if "현재 주가" in props:
                update_data["현재 주가"] = {"number": current_price}
            elif "현재 주가 (작성)" in props:
                update_data["현재 주가 (작성)"] = {"number": current_price}
                
            if "현재 환율" in props:
                update_data["현재 환율"] = {"number": current_fx}
            elif "현재 환율 (작성)" in props:
                update_data["현재 환율 (작성)"] = {"number": current_fx}
                
            if update_data:
                patch_url = f"https://api.notion.com/v1/pages/{page['id']}"
                patch_res = requests.patch(patch_url, headers=NOTION_HEADERS, json={"properties": update_data})
                if patch_res.status_code == 200:
                    print(f"[{ticker}] 업데이트 완료: {current_price}")
                else:
                    print(f"[{ticker}] 업데이트 실패: {patch_res.text}")

if __name__ == "__main__":
    main()
