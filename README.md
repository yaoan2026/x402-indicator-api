# 技術指標 API（x402 付費版）

送一串收盤價進來，API 會回傳 **RSI、MACD、布林通道、SMA、EMA**，再附上一段機器好讀的訊號摘要，例如超買／超賣、黃金交叉／死亡交叉。

每次呼叫用 **x402** 收 USDC（預設 0.001 美元）。買方不用註冊帳號，也不用申請 API key，AI 代理可以自己付款、自己呼叫。

預設跑在 **Base Sepolia 測試網**，用的是測試幣，不會花到真錢。

---

## 檔案說明

| 檔案 | 用途 |
|---|---|
| `main.py` | API 伺服器（FastAPI）＋ x402 收費設定 |
| `service.py` | 請求格式驗證、計算邏輯、摘要判斷 |
| `indicators.py` | 純 Python 的指標公式 |
| `client.py` | 買方測試腳本：自動付款並呼叫付費端點 |
| `new_wallet.py` | 產生一個測試錢包（只印出來） |
| `setup_wallets.bat` | Windows：產生收款＋付款兩個測試錢包、寫進 `.env`，並打開測試幣水龍頭 |
| `smoke_test.py` | 端到端測試：開啟收費啟動伺服器，驗證 402 和付款流程 |
| `run_tests.bat` | Windows 一鍵測試（雙擊執行，結果存到 `test_log.txt`） |
| `pay_remote.bat` | Windows：對已部署的網址實際付款一次（結果存到 `remote_log.txt`） |
| `render.yaml` | Render 部署設定 |
| `tests/` | 自動測試（`pytest`） |
| `.env.example` | 設定範本 |

## 端點

| 端點 | 收費 | 說明 |
|---|---|---|
| `GET /` | 免費 | 服務說明、價格、收款地址 |
| `GET /health` | 免費 | 健康檢查 |
| `POST /v1/preview` | 免費 | 試用版，只回傳 RSI，最多 100 筆價格 |
| `POST /v1/indicators` | **付費** | 全部指標加摘要，最多 5000 筆價格 |
| `GET /docs` | 免費 | 自動產生的互動式文件 |

---

## 快速開始（測試網，約 15 分鐘）

### 1. 安裝

需要 Python 3.10 以上。

```bash
cd x402-indicator-api
python -m venv .venv
source .venv/bin/activate        # Windows 用：.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 準備兩個錢包

- **收款錢包（賣方）**：只需要地址。用 MetaMask 之類的錢包地址，或用下面的腳本產生都可以。
- **付款錢包（買方，測試用）**：需要私鑰，`client.py` 會用它付款。

```bash
python new_wallet.py   # 產生一個錢包；要兩個就跑兩次
```

> ⚠️ 私鑰就是錢包的所有權。只放進 `.env`，不要貼給任何人，也不要上傳 GitHub（`.gitignore` 已經排除 `.env`）。

### 3. 領測試 USDC

到 Circle 的水龍頭 <https://faucet.circle.com>，網路選 **Base Sepolia**，把 USDC 領到**付款錢包**的地址。

x402 的 exact 付款方式由 facilitator 代付 gas，所以買方只需要 USDC。

### 4. 設定 `.env`

```bash
cp .env.example .env
```

打開 `.env`，填入兩個值：

- `PAY_TO`：收款錢包地址
- `BUYER_PRIVATE_KEY`：付款錢包私鑰

### 5. 啟動伺服器

```bash
uvicorn main:app --port 4021
```

### 6. 測試

```bash
# 免費試用：應該回 200
curl -X POST localhost:4021/v1/preview \
  -H 'Content-Type: application/json' \
  -d '{"prices":[100,101,102,101,103,104,103,105,106,105,107,108,107,109,110,111]}'

# 付費端點、不付錢：應該回 402 Payment Required
curl -i -X POST localhost:4021/v1/indicators \
  -H 'Content-Type: application/json' -d '{"prices":[1,2,3]}'

# 用測試錢包付款：應該回 200，並印出付款結算資訊
python client.py
```

付款成功後，到 <https://sepolia.basescan.org> 搜尋你的 `PAY_TO` 地址，就會看到收到的 0.001 USDC。🎉

---

## 請求與回應格式

**請求**（`POST /v1/indicators`）：

```json
{
  "prices": [101.2, 102.5, 101.9, 103.4, 104.1, ...],
  "indicators": ["rsi", "macd", "bollinger", "sma", "ema"],
  "params": {
    "rsi_period": 14,
    "macd_fast": 12, "macd_slow": 26, "macd_signal": 9,
    "bb_period": 20, "bb_std": 2,
    "sma_period": 20, "ema_period": 20,
    "rsi_overbought": 70, "rsi_oversold": 30
  },
  "full_series": false
}
```

只有 `prices` 是必填，其他欄位都有預設值。價格要由舊到新排列。`full_series: true` 會回傳整段序列，不只最新值。

**回應範例**：

```json
{
  "count": 60,
  "latest_price": 125.79,
  "latest": {
    "sma": 119.922,
    "rsi": 86.35531084,
    "macd": { "macd": 2.86744954, "signal": 2.53597332, "histogram": 0.33147623 },
    "bollinger": {
      "middle": 119.922, "upper": 124.44480267, "lower": 115.39919733,
      "percent_b": 1.1487128, "bandwidth": 0.07542907
    }
  },
  "summary": {
    "price_vs_sma": "above",
    "rsi_state": "overbought",
    "macd_momentum": "bullish",
    "bollinger_position": "above_upper"
  },
  "disclaimer": "Computed indicators only. Not financial advice."
}
```

摘要欄位：

- `rsi_state`：`overbought`（超買）、`oversold`（超賣）、`neutral`（中性）
- `macd_momentum`：`bullish` 或 `bearish`
- `macd_cross`：只有最後一根剛交叉時才出現，值是 `bullish_cross`（黃金交叉）或 `bearish_cross`（死亡交叉）
- `bollinger_position`：`above_upper`、`below_lower`、`inside`
- `price_vs_sma`／`price_vs_ema`：價格在均線之上（`above`）或之下（`below`）

資料筆數不夠算某個指標時，該指標的值是 `null`，並會出現 `warnings` 欄位。

---

## 不收費的本機開發

在 `.env` 設 `PAYMENTS_ENABLED=false`，所有端點都變免費，方便修改和除錯。

```bash
pytest               # 指標、格式驗證、API 路由的測試
python smoke_test.py # 開啟收費實際跑一次：免費端點、402 回應、付款流程
```

Windows 可以直接雙擊 `run_tests.bat`，它會自動建立虛擬環境、安裝套件，再依序跑上面兩項測試。

`smoke_test.py` 一律使用測試網。`.env` 裡如果有 `BUYER_PRIVATE_KEY`，而且錢包有測試 USDC，就會真的付一筆 0.001 測試 USDC；沒有的話，會用一個空的臨時錢包走流程，預期因為餘額不足被拒絕。

RSI 的計算已經對照 StockCharts 的經典範例資料驗證過。

---

## 上線賺真錢

1. **部署到 Render（免費）**：專案裡的 `render.yaml` 已經寫好設定。在 Render 選 **New → Blueprint**，連到這個 GitHub repo，填入 `PAY_TO`（你的 MetaMask 地址）就會開始部署，預設先跑在測試網。
   - 免費方案閒置 15 分鐘會休眠，下一次請求要等約 1 分鐘喚醒。
   - 部署好後，Windows 可以雙擊 `pay_remote.bat`，貼上 Render 給你的網址，實際付一次 0.001 測試 USDC。結果存在 `remote_log.txt`。
2. **換成主網**，在 Render 的 Environment 頁面修改：
   - `NETWORK=eip155:8453`（Base 主網）
   - `USE_CDP_FACILITATOR=true`
   - `CDP_API_KEY_ID`、`CDP_API_KEY_SECRET`：到 Coinbase Developer Platform 申請
   - 另外執行 `pip install cdp-sdk`（`requirements.txt` 裡有註解）
3. **收款地址**：換成你自己長期保管的正式錢包，不要用 `new_wallet.py` 產生的測試錢包。
4. **讓別人找到你**：把服務登記到 x402 生態的服務目錄，例如 Bazaar、Agentic.market，讓 AI 代理找得到。也可以到 GitHub、X、Discord 的 x402 社群分享。
5. **定價**：可以先維持 0.001～0.01 美元，看呼叫量再調整。`PRICE` 改環境變數就好，不用改程式。

> 收到的 USDC 如果要換成台幣，會經過交易所出金，也可能牽涉所得申報，請自行確認相關規定。這個專案只計算指標，不構成投資建議。

---

## 疑難排解

- **`ImportError`／`ModuleNotFoundError: x402...`**：x402 Python SDK 從 v1 到 v2 改過套件路徑。先執行 `pip install -U "x402[evm,fastapi,httpx]"`；如果還是不行，對照官方文件 <https://docs.cdp.coinbase.com/x402> 的 Python 範例調整 `main.py` 裡 `_setup_payments()` 的 import。
- **`RuntimeError: PAY_TO 沒有設定`**：`.env` 沒填收款地址，或 `.env` 不在你執行指令的資料夾。
- **`client.py` 一直拿到 402**：付款錢包可能沒有 Base Sepolia 的 USDC，或 `.env` 裡的 `NETWORK` 跟伺服器不一致。
- **付款失敗、facilitator 錯誤**：測試網的公開 facilitator 偶爾會忙碌，等一下再試。

## 可以加的功能

- KD、ATR、威廉指標（需要高低價，可以把 `prices` 擴充成 OHLC 格式）
- 一次分析多檔標的的批次端點（可以收比較高的價格）
- 依呼叫量調整價格，或提供付費的完整歷史序列
