from aegis_api_common import AuthDependencies

from app.config import get_settings
from app.db import get_db

settings = get_settings()

auth = AuthDependencies(
    jwt_secret=settings.jwt_secret,
    jwt_algorithm=settings.jwt_algorithm,
    get_db=get_db,
)
