from pathlib import Path
from fastapi.templating import Jinja2Templates

APP_DIR = Path(__file__).parent
STATIC_DIR = APP_DIR / 'static'
TEMPLATES_DIR = APP_DIR / 'templates'

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

APP_VERSION = '1.0.0'
