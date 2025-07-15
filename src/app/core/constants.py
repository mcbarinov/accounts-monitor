from enum import StrEnum, unique

from mm_web3 import Network, NetworkType


@unique
class Naming(StrEnum):
    ENS = "ens"
    ANS = "ans"
    STARKNET_ID = "starknet_id"

    @property
    def network(self) -> Network:
        match self:
            case Naming.ENS:
                return Network.ETHEREUM
            case Naming.ANS:
                return Network.APTOS
            case Naming.STARKNET_ID:
                return Network.STARKNET
        raise ValueError("no network found")

    @property
    def network_type(self) -> NetworkType:
        match self:
            case Naming.ENS:
                return NetworkType.EVM
            case Naming.ANS:
                return NetworkType.APTOS
            case Naming.STARKNET_ID:
                return NetworkType.STARKNET
        raise ValueError("no network type found")

    def is_consistent(self, network_type: NetworkType) -> bool:
        match self:
            case Naming.ENS:
                return network_type == NetworkType.EVM
            case Naming.ANS:
                return network_type == NetworkType.APTOS
            case Naming.STARKNET_ID:
                return network_type == NetworkType.STARKNET
            case _:
                return False
