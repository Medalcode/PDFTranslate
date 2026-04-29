from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def project_path(*parts: str) -> Path:
    return (BASE_DIR.joinpath(*parts)).resolve()


def resolve_user_path(raw_path: str | None, default_path: str) -> Path:
    path = Path(raw_path or default_path)
    if path.is_absolute():
        return path.resolve()
    return (BASE_DIR / path).resolve()
