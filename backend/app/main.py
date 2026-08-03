from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes_read import router as read_router
from app.config import Settings
from app.config_data import AppConfig
from app.llm.gateway import LLMGateway
from app.models import init_db

DEMO_FLAG = {"on": False}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_engine(settings.database_url)
        init_db(engine)
        # don't clobber test-injected doubles
        if not hasattr(app.state, "session_factory"):
            app.state.session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        if not hasattr(app.state, "gateway"):
            app.state.gateway = LLMGateway(settings)
        yield

    app = FastAPI(title="Ribbit", lifespan=lifespan)
    app.state.settings = settings
    app.state.appcfg = AppConfig.load(settings.config_dir)
    app.include_router(read_router)
    return app
