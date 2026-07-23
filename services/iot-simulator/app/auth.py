"""
This service's bound instance of the shared aegis_api_common auth
dependencies — every module's router imports `auth` from here rather than
constructing its own AuthDependencies, so there is exactly one place this
service's JWT verification is configured.
"""

from aegis_api_common import AuthDependencies

from app.config import get_settings
from app.db import get_db

settings = get_settings()

auth = AuthDependencies(jwt_secret=settings.jwt_secret, jwt_algorithm=settings.jwt_algorithm, get_db=get_db)
