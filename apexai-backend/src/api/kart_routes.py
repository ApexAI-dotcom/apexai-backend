import os
import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Request
from pydantic import BaseModel

from src.core.kart_mechanical import parse_kart_mechanical
from src.api.kart_service import KartService
from src.api.auth import get_current_user
from src.api.config import settings
from src.api.models import KartSetupCreate, CircuitCreate, AdvisorRequest, TireSetPayload
from src.api.advisor_service import compute_tire_advice, recommend_tire_set

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

class RenameSetupRequest(BaseModel):
    name: str

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

@router.get("/api/kart/last-sessions")
async def get_last_kart_sessions(limit: int = 3, current_user: str = Depends(get_current_user)):
    """Get the last N sessions for Magic Link."""
    if not is_mon_kart_enabled():
        raise HTTPException(status_code=404, detail="Mon Kart is currently disabled.")
        
    try:
        sessions = KartService.get_sessions(current_user, limit=limit)
        return {"sessions": sessions}
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

@router.delete("/api/kart/history/{entry_id}")
async def delete_history_entry(entry_id: str, current_user: str = Depends(get_current_user)):
    if not is_mon_kart_enabled():
        raise HTTPException(status_code=404, detail="Mon Kart is currently disabled.")
        
    if not KartService.is_racer_or_team(current_user):
        raise HTTPException(status_code=403, detail="Mon Kart is only available for Racer and Team plans.")
        
    try:
        res = KartService.delete_history_entry(current_user, entry_id)
        return res
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/kart/day/{date}")
async def delete_sessions_by_day(date: str, current_user: str = Depends(get_current_user)):
    """Delete all sessions for a given day (yyyy-MM-dd) and recalculate profile."""
    if not is_mon_kart_enabled():
        raise HTTPException(status_code=404, detail="Mon Kart is currently disabled.")
        
    if not KartService.is_racer_or_team(current_user):
        raise HTTPException(status_code=403, detail="Mon Kart is only available for Racer and Team plans.")
        
    try:
        res = KartService.delete_sessions_by_day(current_user, date)
        return res
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/kart/setups")
async def save_kart_setup(setup: KartSetupCreate, current_user: str = Depends(get_current_user)):
    """Save a new kart setup."""
    if not is_mon_kart_enabled():
        raise HTTPException(status_code=404, detail="Mon Kart is currently disabled.")
        
    if not KartService.is_racer_or_team(current_user):
        raise HTTPException(status_code=403, detail="Mon Kart is only available for Racer and Team plans.")
        
    try:
        res = KartService.save_kart_setup(current_user, setup.model_dump())
        return {"success": True, "setup": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/kart/setups")
async def get_kart_setups(current_user: str = Depends(get_current_user)):
    """Get all saved kart setups for the user."""
    if not is_mon_kart_enabled():
        raise HTTPException(status_code=404, detail="Mon Kart is currently disabled.")
        
    if not KartService.is_racer_or_team(current_user):
        raise HTTPException(status_code=403, detail="Mon Kart is only available for Racer and Team plans.")
        
    try:
        setups = KartService.get_kart_setups(current_user)
        return {"setups": setups}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/kart/setups/{setup_id}")
async def delete_kart_setup(setup_id: str, current_user: str = Depends(get_current_user)):
    """Delete a saved kart setup."""
    if not is_mon_kart_enabled():
        raise HTTPException(status_code=404, detail="Mon Kart is currently disabled.")
        
    if not KartService.is_racer_or_team(current_user):
        raise HTTPException(status_code=403, detail="Mon Kart is only available for Racer and Team plans.")
        
    try:
        res = KartService.delete_kart_setup(current_user, setup_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/api/kart/setups/{setup_id}/rename")
async def rename_kart_setup(setup_id: str, req: RenameSetupRequest, current_user: str = Depends(get_current_user)):
    """Rename a saved kart setup."""
    if not is_mon_kart_enabled():
        raise HTTPException(status_code=404, detail="Mon Kart is currently disabled.")
        
    if not KartService.is_racer_or_team(current_user):
        raise HTTPException(status_code=403, detail="Mon Kart is only available for Racer and Team plans.")
        
    try:
        res = KartService.rename_kart_setup(current_user, setup_id, req.name)
        return {"success": True, "setup": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/circuits")
async def get_circuits(current_user: str = Depends(get_current_user)):
    """Get all available circuits."""
    try:
        circuits = KartService.get_circuits()
        return {"circuits": circuits}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/kart/advisor")
async def kart_advisor(req: AdvisorRequest, current_user: str = Depends(get_current_user)):
    """Recommandations ingénieur : pressions pneus (abaques catalogue)
    + train de pneus optimal depuis le stock Mon Kart (si mode fourni)."""
    try:
        components = KartService.get_catalog_components("tire")
        tire_sets = KartService.get_tire_sets(current_user)
        set_advice = recommend_tire_set(tire_sets, req.mode or "course", req.weather) if tire_sets else None

        # Base des pressions : le pneu réellement concerné par la session.
        # Priorité au train recommandé (ce qu'ApexAI conseille de rouler),
        # sinon le train monté, sinon le modèle envoyé par le frontend.
        pressure_tire = req.tire_model or ""
        if set_advice and set_advice.get("set") and set_advice["set"].get("model"):
            pressure_tire = set_advice["set"]["model"]
        elif set_advice and set_advice.get("mounted") and set_advice["mounted"].get("model"):
            pressure_tire = set_advice["mounted"]["model"]

        result = compute_tire_advice(
            tire_model=pressure_tire,
            weather=req.weather,
            track_temp=req.track_temp,
            air_temp=req.air_temp,
            grip=req.grip,
            circuit=req.circuit,
            components=components,
        )
        if set_advice:
            result["tire_set_advice"] = set_advice
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/kart/tire-sets")
async def get_tire_sets(current_user: str = Depends(get_current_user)):
    """List the user's tire sets."""
    try:
        return {"tire_sets": KartService.get_tire_sets(current_user)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/kart/tire-sets")
async def create_tire_set(payload: TireSetPayload, current_user: str = Depends(get_current_user)):
    """Declare a new tire set in the stock."""
    try:
        res = KartService.create_tire_set(current_user, payload.model_dump(by_alias=False, exclude_none=True))
        return {"success": True, "tire_set": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/kart/tire-sets/{set_id}")
async def update_tire_set(set_id: str, payload: TireSetPayload, current_user: str = Depends(get_current_user)):
    """Update a tire set (state, wear, label...)."""
    try:
        res = KartService.update_tire_set(current_user, set_id, payload.model_dump(by_alias=False, exclude_none=True))
        return {"success": True, "tire_set": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/kart/tire-sets/{set_id}")
async def delete_tire_set(set_id: str, current_user: str = Depends(get_current_user)):
    """Remove a tire set from the stock."""
    try:
        res = KartService.delete_tire_set(current_user, set_id)
        return {"success": True, **res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/kart/tire-sets/{set_id}/mount")
async def mount_tire_set(set_id: str, current_user: str = Depends(get_current_user)):
    """Mark a tire set as currently mounted on the kart."""
    try:
        res = KartService.mount_tire_set(current_user, set_id)
        return {"success": True, "tire_set": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/catalog/components")
async def get_catalog_components(category: str = None, current_user: str = Depends(get_current_user)):
    """Get the component catalog (engines, tires, brakes, chassis, carburetors, axles).

    Optional query param `category` filters on one category.
    """
    try:
        components = KartService.get_catalog_components(category)
        return {"components": components}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/circuits")
async def create_circuit(circuit: CircuitCreate, current_user: str = Depends(get_current_user)):
    """Create a new circuit."""
    try:
        # Pydantic v2 dump with by_alias=False ensures snake_case keys are used in output
        res = KartService.create_circuit(circuit.model_dump(by_alias=False), current_user)
        return {"success": True, "circuit": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/api/circuits/{circuit_id}")
async def update_circuit(circuit_id: str, circuit: CircuitCreate, current_user: str = Depends(get_current_user)):
    """Update an existing circuit."""
    try:
        res = KartService.update_circuit(circuit_id, circuit.model_dump(by_alias=False), current_user)
        return {"success": True, "circuit": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/circuits/{circuit_id}")
async def delete_circuit(circuit_id: str, current_user: str = Depends(get_current_user)):
    """Delete a non-official circuit."""
    try:
        res = KartService.delete_circuit(circuit_id, current_user)
        return {"success": True, **res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
