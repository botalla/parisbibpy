"""Authentication and setup helper for live sample scripts."""

import getpass
import os
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError):
        pass

from parisbibpy import ParisBibClient


def load_env_file() -> None:
    """Load variables from .env file in the project root if it exists."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k not in os.environ:
                        os.environ[k] = v


def get_authenticated_client() -> ParisBibClient:
    """Create and authenticate a ParisBibClient against the real Syracuse portal.

    Credentials are read from:
    1. Environment variables: PARISBIB_USERNAME and PARISBIB_PASSWORD
    2. A .env file in the project root
    3. Interactive prompt if not set
    """
    load_env_file()
    username = os.environ.get("PARISBIB_USERNAME")
    password = os.environ.get("PARISBIB_PASSWORD")

    if not username or not password:
        print("=" * 60)
        print(" PARIS PUBLIC LIBRARIES - LIVE AUTHENTICATION")
        print("=" * 60)
        print("No PARISBIB_USERNAME or PARISBIB_PASSWORD found in environment or .env file.")
        print("Please enter your library card credentials to connect to the live backend:\n")
        try:
            username = input("Card barcode (e.g. 222723...): ").strip()
            password = getpass.getpass("PIN / Password: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)

        if not username or not password:
            print("Error: Card barcode and PIN are required.")
            sys.exit(1)

    print(f"Connecting to bibliotheques.paris.fr as {username[:6]}... ", end="", flush=True)
    client = ParisBibClient(username=username, password=password)
    client.login()
    print("Authentication successful!\n")
    return client
