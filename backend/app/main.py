import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes_admin import router as admin_router
from app.api.routes_read import router as read_router
from app.config import Settings
from app.config_data import AppConfig
from app.llm.gateway import LLMGateway
from app.models import init_db
from app.pipeline.run import run_pipeline

log = logging.getLogger("ribbit")
DEMO_FLAG = {"on": False}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_engine(settings.database_url)
        init_db(engine)
        if not hasattr(app.state, "session_factory"):
            app.state.session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        if not hasattr(app.state, "gateway"):
            app.state.gateway = LLMGateway(settings)

        from app.demo import maybe_enter_demo_mode  # Task 15
        DEMO_FLAG["on"] = maybe_enter_demo_mode(app.state.session_factory,
                                                app.state.gateway, settings)

        scheduler = None
        if settings.enable_scheduler and not DEMO_FLAG["on"]:
            scheduler = AsyncIOScheduler()

            async def scheduled_run():
                await run_pipeline(app.state.session_factory, settings,
                                   app.state.appcfg, app.state.gateway)

            scheduler.add_job(scheduled_run,
                              CronTrigger(hour=settings.refresh_hour, minute=0))
            scheduler.start()
            log.info("daily refresh scheduled at %02d:00", settings.refresh_hour)
        yield
        if scheduler:
            scheduler.shutdown(wait=False)

    app = FastAPI(title="Ribbit", lifespan=lifespan)
    app.state.settings = settings
    app.state.appcfg = AppConfig.load(settings.config_dir)
    app.include_router(read_router)
    app.include_router(admin_router)
    return app
