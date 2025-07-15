from collections.abc import Callable

from fastapi import HTTPException, Query


def optional_bool(param_name: str) -> Callable[[str | None], bool | None]:
    def func(value: str | None = Query(None, alias=param_name)) -> bool | None:
        # Treat empty string as None
        if value == "" or value is None:
            return None
        # Convert common representations of booleans
        if value.lower() in ("true", "1", "yes"):
            return True
        if value.lower() in ("false", "0", "no"):
            return False
        raise HTTPException(status_code=400, detail="Invalid boolean value")

    return func
