import os
import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Request
from pydantic import BaseModel

from src.core.kart_mechanical import parse_kart_mechanical
from src.api.kart_service import KartService
from src.api.auth import get_current_user
from src.api.config import settings

router = APIRouter()

# Feature Flag
def is_mon_kart_enabled() -> bool:
    env_flag = os.getenv("MON_KART_ENABLED", getattr(settings, "MON_KART_ENABLED", "true"))
    return str(env_flag).lower() in ["true", "1", "yes"]

class ResetComponentRequest(BaseModel):
    component_type: str
    notes: Optional[str] = None

class AddHistoryRequest(BaseModel):
    component_type: str
    notes: str
    date: Optional[str] = None

@router.get("/api/kart/profile")
async def get_kart_profile(current_user: str = Depends(get_current_user)):
    if not is_mon_kart_enabled():
        raise HTTPException(status_code=404, detail="Mon Kart is currently disabled.")
        
    try:
        profile = KartService.get_or_create_kart_profile(current_user)
        sessions = KartService.get_sessions(current_user, limit=50)
        history = KartService.get_component_history(current_user, limit=20)
        return {"profile": profile, "recent_sessions": sessions, "history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/api/kart/profile")
async def update_kart_profile(updates: Dict[str, Any], current_user: str = Depends(get_current_user)):
    if not is_mon_kart_enabled():
        raise HTTPException(status_code=404, detail="Mon Kart is currently disabled.")
    
    if not KartService.is_racer_or_team(current_user):
        raise HTTPException(status_code=403, detail="Mon Kart is only available for Racer and Team plans.")
        
    try:
        updated = KartService.update_kart_profile(current_user, updates)
        return {"profile": updated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/kart/bulk-import")
async def bulk_import_sessions(files: List[UploadFile] = File(...), current_user: str = Depends(get_current_user)):
    if not is_mon_kart_enabled():
        raise HTTPException(status_code=404, detail="Mon Kart is currently disabled.")
        
    if not KartService.is_racer_or_team(current_user):
        raise HTTPException(status_code=403, detail="Mon Kart is only available for Racer and Team plans.")

    results = []
    os.makedirs(settings.TEMP_DIR, exist_ok=True)
    
    for file in files:
        temp_path = None
        try:
            temp_path = os.path.join(settings.TEMP_DIR, f"kart_imp_{uuid.uuid4().hex[:8]}_{file.filename}")
            content = await file.read()
            with open(temp_path, "wb") as f:
                f.write(content)
                
            parse_res = parse_kart_mechanical(temp_path)
            
            if not parse_res["success"]:
                results.append({"filename": file.filename, "success": False, "error": parse_res["error"]})
                continue
                
            sig = parse_res["signature"]
            aggs = parse_res["aggregates"]
            
            # Upsert
            upsert_res = KartService.upsert_session(current_user, sig, "bulk_import", aggs, None)
            
            results.append({
                "filename": file.filename,
                "success": True,
                "is_new": upsert_res["is_new"],
                "session_id": upsert_res["session"].get("id")
            })
            
        except Exception as e:
            results.append({"filename": file.filename, "success": False, "error": str(e)})
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
                    
    return {"results": results}

@router.post("/api/kart/component-reset")
async def reset_component(req: ResetComponentRequest, current_user: str = Depends(get_current_user)):
    if not is_mon_kart_enabled():
        raise HTTPException(status_code=404, detail="Mon Kart is currently disabled.")
        
    if not KartService.is_racer_or_team(current_user):
        raise HTTPException(status_code=403, detail="Mon Kart is only available for Racer and Team plans.")
        
    if req.component_type not in ["engine", "tires", "brakes"]:
        raise HTTPException(status_code=400, detail="Invalid component_type")
        
    try:
        updated = KartService.reset_component(current_user, req.component_type, req.notes)
        return {"profile": updated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/kart/history/add")
async def add_history_entry(req: AddHistoryRequest, current_user: str = Depends(get_current_user)):
    if not is_mon_kart_enabled():
        raise HTTPException(status_code=404, detail="Mon Kart is currently disabled.")
        
    if not KartService.is_racer_or_team(current_user):
        raise HTTPException(status_code=403, detail="Mon Kart is only available for Racer and Team plans.")
        
    try:
        updated = KartService.add_maintenance_log(current_user, req.component_type, req.notes, req.date)
        return {"entry": updated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/kart/session/{session_id}")
async def delete_kart_session(session_id: str, current_user: str = Depends(get_current_user)):
    if not is_mon_kart_enabled():
        raise HTTPException(status_code=404, detail="Mon Kart is currently disabled.")
        
    if not KartService.is_racer_or_team(current_user):
        raise HTTPException(status_code=403, detail="Mon Kart is only available for Racer and Team plans.")
        
    try:
        res = KartService.delete_session_and_recalculate(current_user, session_id)
        return res
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
