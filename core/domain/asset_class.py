from enum import StrEnum


class AssetClass(StrEnum):
    EQUITY = "equity"
    ETF = "etf"
    BOND = "bond"
    FUTURE = "future"
    OPTION = "option"
    FX = "fx"
    COMMODITY = "commodity"
    CRYPTO = "crypto"
    CASH = "cash"