"""產生一個全新的「測試用」錢包。

python new_wallet.py

⚠️ 私鑰等於錢包的所有權。這支腳本產生的錢包只拿來領測試幣、跑測試，
   不要把真錢轉進去，也不要把私鑰傳給任何人或上傳到 GitHub。
"""

from eth_account import Account

acct = Account.create()
print("地址（可以公開，當收款或付款地址）：", acct.address)
print("私鑰（絕對保密，只放進 .env）：     ", "0x" + acct.key.hex().removeprefix("0x"))
