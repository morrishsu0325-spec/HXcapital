import datetime as dt
import json
import os
import sys
import time
import urllib.request

START = dt.date(2026, 9, 1)          # 從這天起補抓歷史收盤價
STOCKS = {"1303": "twse", "8045": "tpex", "8039": "tpex"}   # 上市 / 上櫃
OUT = "data/prices.json"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def roc(s):
    y, m, d = s.strip().split("/")
    return f"{int(y) + 1911:04d}-{int(m):02d}-{int(d):02d}"


def num(s):
    return float(str(s).replace(",", "").strip())


def months():
    d = START.replace(day=1)
    today = dt.date.today()
    while d <= today:
        yield d
        d = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)


def taiex(m):
    j = get(f"https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?date={m:%Y%m}01&response=json")
    i = [k for k, f in enumerate(j["fields"]) if "加權" in f][0]
    return {roc(r[0]): num(r[i]) for r in j["data"]}


def twse_stock(code, m):
    j = get(f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date={m:%Y%m}01&stockNo={code}&response=json")
    i = [k for k, f in enumerate(j["fields"]) if "收盤" in f][0]
    out = {}
    for r in j["data"]:
        try:
            out[roc(r[0])] = num(r[i])
        except ValueError:
            pass
    return out


def tpex_stock(code, m):
    rows = []
    try:
        j = get(f"https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock?code={code}&date={m:%Y/%m}/01&id=&response=json")
        rows = j["tables"][0]["data"]
    except Exception as e:
        print("  tpex new api failed:", e)
    if not rows:
        j = get(f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php?l=zh-tw&d={m.year - 1911}/{m:%m}&stkno={code}")
        rows = j["aaData"]
    out = {}
    for r in rows:
        try:
            out[roc(r[0])] = num(r[6])
        except (ValueError, IndexError):
            pass
    return out


def finmind(code):
    j = get(f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id={code}&start_date={START.isoformat()}")
    return {r["date"]: float(r["close"]) for r in j["data"] if r.get("close")}


def main():
    data = {}
    if os.path.exists(OUT):
        data = json.load(open(OUT, encoding="utf-8"))
    close = data.setdefault("close", {})
    failed = []
    series = {"TAIEX": None, **STOCKS}
    for code, mkt in series.items():
        got = {}
        try:
            for m in months():
                if code == "TAIEX":
                    got.update(taiex(m))
                elif mkt == "twse":
                    got.update(twse_stock(code, m))
                else:
                    got.update(tpex_stock(code, m))
                time.sleep(3)
        except Exception as e:
            print(code, "官方來源失敗:", e)
        if not got and code != "TAIEX":
            try:
                got = finmind(code)
                print(code, "改用 FinMind")
            except Exception as e:
                print(code, "FinMind 也失敗:", e)
        print(code, "取得", len(got), "筆,最新:", max(got) if got else "無")
        if got:
            close.setdefault(code, {}).update(got)
        else:
            failed.append(code)
    data["updated"] = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    os.makedirs("data", exist_ok=True)
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    if failed:
        print("失敗項目:", failed)
        sys.exit(1)


main()
