import logging
from datetime import datetime
from typing import Annotated

from mm_base6 import CoreConfig, CoreLifecycle, ServerConfig, SettingsModel, StateModel, setting_field, state_field
from mm_web3 import Network

from app.core.constants import Naming
from app.core.types import AppCore

core_config = CoreConfig()

server_config = ServerConfig()
server_config.tags = ["bot", "network", "coin", "group"]
server_config.main_menu = {"/bot": "bot", "/groups": "groups", "/history": "history"}


class Settings(SettingsModel):
    mm_node_checker: Annotated[str, setting_field("", "mm node checker url")]
    proxies_url: Annotated[str, setting_field("http://localhost:8000", "proxies url, each proxy on new line")]
    round_ndigits: Annotated[int, setting_field(5, "round ndigits")]
    limit_network_workers: Annotated[int, setting_field(20, "How many requests to one network in parallel")]
    limit_naming_workers: Annotated[int, setting_field(20, "How many requests to one naming in parallel")]
    check_balance_interval: Annotated[int, setting_field(15, "Check balance interval in minutes")]
    check_name_interval: Annotated[int, setting_field(15, "Check name interval in minutes")]


class State(StateModel):
    check_balances: Annotated[bool, state_field(True)]
    check_namings: Annotated[bool, state_field(True)]
    proxies: Annotated[list[str], state_field([], "list of proxies")]
    proxies_updated_at: Annotated[datetime | None, state_field(None, "timestamp of last proxies update")]
    mm_node_checker: Annotated[dict[str, list[str]] | None, state_field(None, "mm_node_checker data")]
    mm_node_checker_updated_at: Annotated[datetime | None, state_field(None, "timestamp of last mm_node_checker update")]


class AppCoreLifecycle(CoreLifecycle[AppCore]):
    async def configure_scheduler(self) -> None:
        # check balances
        for network in Network:
            task_id = "balances_on_" + network.value
            self.core.scheduler.add_task(task_id, 2, self.core.services.balance.check_next_network, args=(network,))

        # check namings
        for naming in list(Naming):
            task_id = "names_on_" + naming
            self.core.scheduler.add_task(task_id, 2, self.core.services.name.check_next_naming, args=(naming,))

        # mm-node-checker
        self.core.scheduler.add_task("mm-node-checker", 30, self.core.services.network.update_mm_node_checker)
        self.core.scheduler.add_task("update_proxies", 60, self.core.services.proxy.update)

    async def on_startup(self) -> None:
        """Startup logic for the application."""
        libraries = ["httpcore", "httpx", "web3"]
        for lib in libraries:
            logging.getLogger(lib).setLevel(logging.WARNING)

        await self.core.services.network.load_rpc_urls_from_db()
        await self.core.services.coin.load_coins_from_db()

    async def on_shutdown(self) -> None:
        """Cleanup logic for the application."""
