"""Configure Groq privately on EC2; run interactively with sudo over SSM."""
import getpass
import os
from pathlib import Path
import re
import sys
import tempfile


def write_configuration(destination: Path, key: str, model: str) -> None:
    if not re.fullmatch(r"gsk_[A-Za-z0-9_-]+", key):
        raise ValueError("Enter a valid Groq key without spaces or line breaks.")
    if not re.fullmatch(r"[A-Za-z0-9_./:-]+", model):
        raise ValueError("Invalid model identifier.")
    content = (
        "DATAFORGE_COPILOT_PROVIDER=groq\n"
        f"GROQ_MODEL_ID={model}\n"
        f"GROQ_API_KEY={key}\n"
    )
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent,
                                         prefix=".env.copilot-", delete=False) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, 0o600)
            stream.write(content)
        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main() -> None:
    if os.geteuid() != 0 or not sys.stdin.isatty():
        raise SystemExit("Run with sudo in an interactive EC2 SSM shell; do not pass the key as an argument.")
    root = Path("/opt/dataforge")
    if not (root / "compose.aws.yml").is_file():
        raise SystemExit("DataForge installation not found.")
    key = getpass.getpass("Groq API key (hidden): ").strip()
    model = input("Groq model [openai/gpt-oss-120b]: ").strip() or "openai/gpt-oss-120b"
    write_configuration(root / ".env.copilot", key, model)
    print("Groq configuration saved privately. Recreate only the API service to load it.")


if __name__ == "__main__":
    main()
