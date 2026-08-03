from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.deps import get_appcfg, get_gateway, get_session_factory, get_settings
from app.pipeline.run import REFRESH_STATE, run_pipeline

router = APIRouter(prefix="/api")


@router.post("/refresh", status_code=202)
async def trigger_refresh(background: BackgroundTasks,
                          sf=Depends(get_session_factory), settings=Depends(get_settings),
                          appcfg=Depends(get_appcfg), gateway=Depends(get_gateway)):
    from app.main import DEMO_FLAG
    if DEMO_FLAG["on"]:
        raise HTTPException(409, "Refresh is disabled in demo mode (no LLM provider configured)")
    if REFRESH_STATE["running"]:
        raise HTTPException(409, "A refresh is already running")
    background.add_task(run_pipeline, sf, settings, appcfg, gateway)
    return {"started": True}


@router.get("/refresh/status")
def refresh_status():
    return REFRESH_STATE
