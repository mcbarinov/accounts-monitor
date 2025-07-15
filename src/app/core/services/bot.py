from mm_base6 import Service

from app.core.types import AppCore


class BotService(Service):
    core: AppCore

    def toggle_check_balances(self) -> None:
        self.core.state.check_balances = not self.core.state.check_balances

    def toggle_check_namings(self) -> None:
        self.core.state.check_namings = not self.core.state.check_namings
