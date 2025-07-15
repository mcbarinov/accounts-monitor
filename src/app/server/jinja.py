from mm_base6 import JinjaConfig
from mm_web3 import Network, NetworkType

from app.core.types import AppCore


class AppJinjaConfig(JinjaConfig[AppCore]):
    filters = {}
    globals = {"networks": list(Network), "network_types": list(NetworkType)}
    header_info_new_line = False
