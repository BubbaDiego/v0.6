import os
from pathlib import Path

# Determine BASE_DIR from an environment variable, or default to one level up from this file
BASE_DIR = Path(os.getenv("BASE_DIR", Path(__file__).resolve().parent.parent))

# Use environment variables for file names, with defaults provided
DB_FILENAME = os.getenv("DB_FILENAME", "mother_brain.db")
CONFIG_FILENAME = os.getenv("CONFIG_FILENAME", "sonic_config.json")

# Construct the full paths using pathlib for cross-platform compatibility
DB_PATH = BASE_DIR / "data" / DB_FILENAME
CONFIG_PATH = BASE_DIR / CONFIG_FILENAME

# Image asset paths
SPACE_WALL_IMAGE = "images/space_wall2.jpg"

BTC_LOGO_IMAGE = "images/btc_logo.png"
ETH_LOGO_IMAGE = "images/eth_logo.png"
SOL_LOGO_IMAGE = "images/sol_logo.png"

R2VAULT_IMAGE = "images/r2vault.jpg"
OBIVAULT_IMAGE = "images/obivault.jpg"
LANDOVAULT_IMAGE = "images/landovault.jpg"
VADERVAULT_IMAGE = "images/vadervault.jpg"
