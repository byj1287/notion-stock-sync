Python
import os
import requests
import yfinance as yf
from bs4 import BeautifulSoup
from notion_client import Client

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID = os.environ["NOTION_DATABASE_ID"]

notion = Client(auth=NOTION_TOKEN)

def get_krx_price(code):
    # 네이버페이 증권에서 당일 종가 수집
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    price_tag = soup.select_one(".no_today .blind")
    return int(price_tag.text.replace(",", "")) if price_tag else None

def get_us_price(ticker):
    # 야후 파이낸스에서 미국 종가 수집
    stock = yf.Ticker(ticker)
    data = stock.history(period="1d")
    return round(float(data["Close"].iloc[-1]), 2) if not data.empty else None

def get_usd_krw_rate():
    # 원/달러 기준 환율 수집
    fx = yf.Ticker("KRW=X")
    data = fx.history(period="1d")
    return round(float(data["Close"].iloc[-1]), 2) if not data.empty else 1350.0

def main():
    rate = get_usd_krw_rate()
    pages = notion.databases.query(database_id=DATABASE_ID)["results"]
    
    for page in pages:
        props = page["properties"]
        
        # 1. 티커(종목코드) 가져오기
        ticker_cell = props.get("티커", {}).get("rich_text", []) or props.get("주식 티커", {}).get("rich_text", [])
        if not ticker_cell:
            continue
        ticker = ticker_cell[0]["plain_text"].strip()
        
        # 2. 국가/시장 구분 확인
        market_select = props.get("시장", {}).get("select") or props.get("국가", {}).get("select")
        market_name = market_select.get("name", "") if market_select else ""
        
        # 3. 시세 조회
        current_price = None
        current_fx = 1
        
        if "미국" in market_name or "해외" in market_name:
            current_price = get_us_price(ticker)
            current_fx = rate
        else:
            # 6자리 숫자만 추출 (예: 005930, 214450)
            clean_code = "".join(filter(str.isdigit, ticker))
            if clean_code:
                current_price = get_krx_price(clean_code)
        
        # 4. 노션 DB 속성 갱신
        if current_price is not None:
            update_data = {
                "현재 주가": {"number": current_price}
            }
            if "현재 환율" in props:
                update_data["현재 환율"] = {"number": current_fx}
                
            notion.pages.update(page_id=page["id"], properties=update_data)
            print(f"[{ticker}] 업데이트 완료: {current_price}")

if __name__ == "__main__":
    main()
