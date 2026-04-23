from fastapi import APIRouter
from core.config import config_manager
from core.logging import log_event

router = APIRouter()

@router.get("")
def get_config():
    return {
        "config": config_manager.config,
        "version": config_manager.version
    }

@router.patch("")
def update_config(updates: dict):
    config_manager.update(updates)
    log_event("info", "config", "Configuration updated", updates)
    return {
        "config": config_manager.config,
        "version": config_manager.version
    }
