import pydash
import tomlkit
from eth_utils import address as ethereum_account
from mm_apt import account as aptos_account
from mm_sol import account as solana_account
from mm_strk import account as starknet_account
from mm_web3 import NetworkType


def find_invalid_address(network_type: NetworkType, addresses: list[str]) -> str | None:
    if network_type == NetworkType.EVM:
        return pydash.find(addresses, lambda a: not ethereum_account.is_address(a))
    if network_type == NetworkType.SOLANA:
        return pydash.find(addresses, lambda a: not solana_account.is_address(a))
    if network_type == NetworkType.APTOS:
        return pydash.find(addresses, lambda a: not aptos_account.is_valid_address(a))
    if network_type == NetworkType.STARKNET:
        return pydash.find(addresses, lambda a: not starknet_account.is_address(a))
    raise ValueError(f"Unknown network type: {network_type}")


def toml_loads(string: str | bytes) -> tomlkit.TOMLDocument:
    return tomlkit.loads(string)
