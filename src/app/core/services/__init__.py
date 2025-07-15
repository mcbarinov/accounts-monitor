from app.core.services.balance import BalanceService
from app.core.services.bot import BotService
from app.core.services.coin import CoinService
from app.core.services.group import GroupService
from app.core.services.history import HistoryService
from app.core.services.name import NameService
from app.core.services.network import NetworkService
from app.core.services.proxy import ProxyService


class ServiceRegistry:
    balance: BalanceService
    bot: BotService
    coin: CoinService
    group: GroupService
    history: HistoryService
    name: NameService
    network: NetworkService
    proxy: ProxyService
