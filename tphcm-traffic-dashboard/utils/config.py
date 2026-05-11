import os
from pathlib import Path
from dotenv import load_dotenv

_env = Path(__file__).parent.parent / ".env"
load_dotenv(_env)

TRINO_HOST = os.getenv("TRINO_HOST", "trino")
TRINO_PORT = int(os.getenv("TRINO_PORT", "8080"))
TRINO_USER = os.getenv("TRINO_USER", "admin")
TRINO_CATALOG = os.getenv("TRINO_CATALOG", "iceberg")
TRINO_SCHEMA = os.getenv("TRINO_SCHEMA", "traffic")
TRINO_PASSWORD = os.getenv("TRINO_PASSWORD", "")

DEFAULT_DISTRICT = os.getenv("DEFAULT_DISTRICT", "Quận 1")
DEFAULT_TIME_RANGE_DAYS = int(os.getenv("DEFAULT_TIME_RANGE_DAYS", "7"))
DEFAULT_AUTO_REFRESH_SECONDS = int(os.getenv("DEFAULT_AUTO_REFRESH_SECONDS", "300"))

CACHE_TTL_SHORT = int(os.getenv("CACHE_TTL_SHORT", "300"))
CACHE_TTL_MEDIUM = int(os.getenv("CACHE_TTL_MEDIUM", "600"))
CACHE_TTL_LONG = int(os.getenv("CACHE_TTL_LONG", "1800"))

TRINO_CONNECTION_URL = (
    f"trino://{TRINO_USER}"
    f":{TRINO_PASSWORD}@{TRINO_HOST}:{TRINO_PORT}"
    f"/{TRINO_CATALOG}/{TRINO_SCHEMA}"
)

DISTRICTS = [
    "Quận 1", "Quận 3", "Quận 4", "Quận 5", "Quận 6",
    "Quận 7", "Quận 8", "Quận 10", "Quận 11", "Quận 12",
    "Quận Bình Tân", "Quận Bình Thạnh", "Quận Gò Vấp",
    "Quận Phú Nhuận", "Quận Tân Bình", "Quận Tân Phú",
    "Thành phố Thủ Đức", "Huyện Bình Chánh", "Huyện Cần Giờ",
    "Huyện Củ Chi", "Huyện Hóc Môn", "Huyện Nhà Bè",
]

WEATHER_CONDITIONS = [
    "Clear", "Clouds", "Rain", "Drizzle",
    "Thunderstorm", "Snow", "Mist", "Fog",
]

COLOR_PALETTE = {
    "primary": "#2E86AB",
    "secondary": "#A23B72",
    "success": "#6BCB77",
    "warning": "#FFD93D",
    "danger": "#FF6B6B",
    "info": "#4ECDC4",
    "dark": "#1A1A2E",
    "darker": "#16213E",
    "surface": "#0F3460",
    "text": "#EAEAEA",
    "muted": "#9E9E9E",
    "chart_colors": [
        "#2E86AB", "#E94F37", "#F39C12", "#6BCB77",
        "#9B59B6", "#1ABC9C", "#E74C3C", "#3498DB",
        "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4",
    ],
}

# Light Mode Color Palette
COLOR_PALETTE_LIGHT = {
    "primary": "#4ECDC4",     # Teal
    "secondary": "#A29BFE",   # Lavender
    "success": "#52C41A",    # Green
    "warning": "#FAAD14",     # Yellow
    "danger": "#FF7875",      # Red-light
    "danger_light": "#FFB3AB", # Red-very-light (congestion)
    "info": "#45B7D1",        # Blue
    "teal": "#4ECDC4",
    "purple": "#DDA0DD",
    "orange": "#FDCB6E",
    "green": "#96CEB4",
    "cyan": "#81ECEC",
    "blue_light": "#74B9FF",
    "lavender": "#A29BFE",
    "text": "#1A2332",
    "text_secondary": "#5A6478",
    "muted": "#8B95A8",
    "bg_card": "#FFFFFF",
    "bg_page": "#F4F6F9",
    "bg_secondary": "#EBEDF2",
    "border": "#DDE1E9",
    "chart_colors": [
        "#4ECDC4", "#45B7D1", "#96CEB4", "#FDCB6E",
        "#A29BFE", "#DDA0DD", "#FFB3AB", "#74B9FF",
        "#81ECEC", "#55EFC4", "#F39C12", "#FF9F43",
    ],
    "pastel": [
        "#74B9FF", "#A29BFE", "#55EFC4", "#FDCB6E",
        "#81ECEC", "#FFB3AB", "#DDA0DD", "#96CEB4",
    ],
}
