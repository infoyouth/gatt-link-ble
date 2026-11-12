# Copilot Instructions — `gatt-link-ble`

- **Architecture:** Always follow `ARCHITECTURE.md` in the repo root. Execute one phase at a time.
- **Strict Boundary:** NEVER import `homeassistant` or `habluetooth`. This is a pure Python PyPI library.
- **Tooling:** Always use `uv run` for commands (`uv run pytest`, `uv run mypy src tests`, `uv run ruff check .`). Never use raw `pip`.
- **BLE Rules:** Use `bleak-retry-connector` (`establish_connection` + `BleakClientWithServiceCache`). Unpack binary payloads strictly with Python's `struct` module—never slice hex strings.
- **Code Quality:** Enforce Python 3.12+ type annotations (`mypy --strict`) and immutable `@dataclass(frozen=True)` state models.
- **Verification:** Before finishing any task, run `uv run ruff check . && uv run mypy src tests && uv run pytest` and fix all errors in the same turn.
