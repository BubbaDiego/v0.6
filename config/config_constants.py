import os

# Go one level up from the current file (assuming this file is in the 'config' folder)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "data", "mother_brain.db")
CONFIG_PATH = os.path.join(BASE_DIR, "sonic_config.json")

# If you want a full OS path (like c:\v0.5\static\images\space_wall.jpg)
# but in practice, for a Flask static folder, a relative path is enough.

SPACE_WALL_IMAGE = "images/space_wall2.jpg"

BTC_LOGO_IMAGE = "images/btc_logo.png"
ETH_LOGO_IMAGE = "images/eth_logo.png"
SOL_LOGO_IMAGE = "images/sol_logo.png"

R2VAULT_IMAGE = "images/r2vault.jpg"
OBIVAULT_IMAGE = "images/obivault.jpg"
LANDOVAULT_IMAGE = "images/landovault.jpg"
VADERVAULT_IMAGE = "images/vadervault.jpg"
