from datetime import datetime
from decimal import Decimal

import pydash
from bson import ObjectId
from mm_base6 import BaseDb
from mm_mongo import AsyncMongoCollection, MongoModel
from mm_std import utc_now
from mm_web3 import Network, NetworkType
from pydantic import Field, field_validator
from pymongo import IndexModel

from app.core.constants import Naming


class RpcUrl(MongoModel[str]):  # id = network
    urls: list[str] = Field(default_factory=list)

    __collection__: str = "rpc_url"


class Coin(MongoModel[str]):  # id = {network}__{symbol}, lowercased
    network: Network
    symbol: str  # symbol is not lowercase
    token: str | None = None  # if None, then it's a native coin
    decimals: int
    notes: str = ""

    __collection__: str = "coin"

    @field_validator("id", mode="before")
    def ensure_lowercase_id(cls, v: str) -> str:
        if isinstance(v, str):
            return v.lower()
        return v


class Group(MongoModel[ObjectId]):
    name: str
    network_type: NetworkType
    notes: str
    coins: list[str] = Field(default_factory=list)  # coin_id list
    namings: list[Naming] = Field(default_factory=list)
    accounts: list[str] = Field(default_factory=list)
    account_notes: dict[str, str] = Field(default_factory=dict)  # account -> note

    __collection__: str = "group"

    def get_coin_networks(self) -> list[str]:
        networks = [c.split("__")[0] for c in self.coins]
        return pydash.sort(pydash.uniq(networks))

    def get_coin_symbols(self, network: str) -> list[str]:
        symbols = [c.split("__")[1] for c in self.coins if c.startswith(f"{network}__")]
        return pydash.sort(pydash.uniq(symbols))


class AccountBalance(MongoModel[ObjectId]):
    group: ObjectId
    account: str
    network: Network  # network_id
    coin: str
    balance: Decimal | None = None
    balance_raw: str | None = None  # mongo can't store very large integers
    checked_at: datetime | None = None

    __collection__: str = "account_balance"
    __indexes__ = ["!group:account:coin", "group", "account", "coin", "network", "checked_at"]


class AccountName(MongoModel[ObjectId]):
    group: ObjectId
    account: str
    network: Network  # network_id
    naming: Naming
    name: str | None = None  # domains, ids, etc..
    checked_at: datetime | None = None

    __collection__: str = "account_name"
    __indexes__ = ["group", "account", "network", "naming", "checked_at"]


class GroupBalance(MongoModel[ObjectId]):
    group: ObjectId
    coin: str
    balances: dict[str, Decimal] = Field(default_factory=dict)  # account -> balance
    checked_at: dict[str, datetime] = Field(default_factory=dict)  # account -> checked_at # TODO: is it needed?

    __collection__: str = "group_balance"
    __indexes__ = ["!group:coin", "group"]


class GroupName(MongoModel[ObjectId]):
    group: ObjectId
    naming: Naming
    names: dict[str, str] = Field(default_factory=dict)  # account -> name, name can be empty string
    checked_at: dict[str, datetime] = Field(default_factory=dict)  # account -> checked_at

    __collection__: str = "group_name"
    __indexes__ = ["!group:naming", "group"]


class NamingProblem(MongoModel[ObjectId]):
    network: Network
    naming: Naming
    account: str
    message: str
    created_at: datetime = Field(default_factory=utc_now)

    __collection__: str = "naming_problem"
    __indexes__ = ["network", "naming", "account", "created_at"]


class RpcMonitoring(MongoModel[ObjectId]):
    network: Network
    rpc_url: str
    success: bool
    account: str
    response_time: float
    coin: str | None = None
    proxy: str | None = None
    error: str | None = None
    data: object | None = None
    created_at: datetime = Field(default_factory=utc_now)

    __collection__: str = "rpc_monitoring"
    __indexes__ = [
        "network",
        "rpc_url",
        "account",
        "coin",
        "proxy",
        "success",
        IndexModel([("created_at", -1)], expireAfterSeconds=3 * 60 * 60),
    ]


class History(MongoModel[ObjectId]):
    group: Group
    notes: str = ""
    balances: dict[str, dict[str, Decimal]]  # coin -> account -> balance
    balances_checked_at: dict[str, dict[str, datetime]]  # coin -> account -> checked_at
    names: dict[Naming, dict[str, str]]  # naming -> account -> name
    names_checked_at: dict[str, dict[str, datetime]]  # naming -> account -> checked_at
    created_at: datetime = Field(default_factory=utc_now)

    __collection__: str = "history"


class Db(BaseDb):
    rpc_url: AsyncMongoCollection[str, RpcUrl]
    coin: AsyncMongoCollection[str, Coin]
    group: AsyncMongoCollection[ObjectId, Group]
    account_balance: AsyncMongoCollection[ObjectId, AccountBalance]
    account_name: AsyncMongoCollection[ObjectId, AccountName]
    group_balance: AsyncMongoCollection[ObjectId, GroupBalance]
    group_name: AsyncMongoCollection[ObjectId, GroupName]
    naming_problem: AsyncMongoCollection[ObjectId, NamingProblem]
    rpc_monitoring: AsyncMongoCollection[ObjectId, RpcMonitoring]
    history: AsyncMongoCollection[ObjectId, History]
