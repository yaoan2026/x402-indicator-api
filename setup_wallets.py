"""產生兩個「測試網專用」錢包，並寫進 .env。

- 收款錢包（賣方）：PAY_TO 填它的地址；私鑰存在 SELLER_PRIVATE_KEY，之後想查看或轉出收到的測試幣時用
- 付款錢包（買方）：BUYER_PRIVATE_KEY，smoke_test.py 和 client.py 用它付款

私鑰只在這台電腦上產生、只存在 .env，不會上傳到任何地方。
這兩個錢包只拿來測試，不要轉真錢進去。

用法：雙擊 setup_wallets.bat（或執行 .venv\\Scripts\\python setup_wallets.py）
"""

from __future__ import annotations

import re
import subprocess
import sys
import webbrowser
from pathlib import Path

from eth_account import Account

HERE = Path(__file__).resolve().parent
ENV = HERE / ".env"
EXAMPLE = HERE / ".env.example"
FAUCET_URL = "https://faucet.circle.com/"
KEY_RE = re.compile(r"^[ \t]*BUYER_PRIVATE_KEY[ \t]*=[ \t]*['\"]?(?:0x)?[0-9a-fA-F]{64}['\"]?[ \t]*$", re.M)


def new_wallet() -> tuple[str, str]:
    acct = Account.create()
    return acct.address, "0x" + acct.key.hex().removeprefix("0x")


def set_line(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^[ \t]*#?[ \t]*{key}[ \t]*=.*$", re.M)
    line = f"{key}={value}"
    if pattern.search(text):
        return pattern.sub(line, text, count=1)
    return text.rstrip("\n") + f"\n{line}\n"


def copy_to_clipboard(text: str) -> bool:
    if sys.platform != "win32":
        return False
    try:
        subprocess.run("clip", input=text.encode("ascii"), check=True, shell=True)
        return True
    except Exception:
        return False


def main() -> None:
    existing = ENV.read_text(encoding="utf-8") if ENV.exists() else ""
    if KEY_RE.search(existing):
        key = KEY_RE.search(existing).group(0).split("=", 1)[1].strip().strip("'\"")
        buyer_addr = Account.from_key(key).address
        print(".env 裡已經有付款錢包了，不會覆蓋。")
    else:
        seller_addr, seller_key = new_wallet()
        buyer_addr, buyer_key = new_wallet()
        text = existing or EXAMPLE.read_text(encoding="utf-8")
        text = set_line(text, "PAY_TO", seller_addr)
        text = set_line(text, "BUYER_PRIVATE_KEY", buyer_key)
        if "SELLER_PRIVATE_KEY" not in text:
            text = text.rstrip("\n") + (
                "\n\n# 收款錢包的私鑰（測試網專用，main.py 不會用到；"
                "想在 MetaMask 查看收到的測試 USDC 時才需要）\n"
            )
        text = set_line(text, "SELLER_PRIVATE_KEY", seller_key)
        ENV.write_text(text, encoding="utf-8")
        print("已產生兩個測試錢包，寫入 .env")
        print(f"  收款錢包 PAY_TO：{seller_addr}")

    print(f"  付款錢包地址：  {buyer_addr}")
    print()
    copied = copy_to_clipboard(buyer_addr)
    if copied:
        print("✔ 付款錢包地址已經複製到剪貼簿")
    print("接下來：")
    print("  1. 在打開的 Circle Faucet 網頁選 USDC、網路選 Base Sepolia")
    print("  2. 把付款錢包地址貼上（Ctrl+V），送出領取測試 USDC")
    print(f"  3. 可以到 https://sepolia.basescan.org/address/{buyer_addr} 確認入帳")
    print("  4. 入帳後，雙擊 run_tests.bat，這次會真的付 0.001 測試 USDC")
    try:
        webbrowser.open(FAUCET_URL)
    except Exception:
        print(f"（請自行打開 {FAUCET_URL}）")


if __name__ == "__main__":
    main()
