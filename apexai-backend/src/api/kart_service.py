import os
import logging
from typing import Dict, Any, Optional, List
from supabase import Client, create_client
from .config import settings

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL") or getattr(settings, "SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
)

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and SUPABASE_SERVICE_ROLE_KEY not in ("", "ton_service_role_key"):
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
else:
    logger.warning("Supabase client is None in kart_service")

class KartService:
    @staticmethod
    def get_subscription_tier(user_id: str) -> str:
        """Fetch the user's subscription tier. Defaults to rookie."""
        if not supabase:
            return "rookie"
        try:
            res = supabase.table("profiles").select("subscription_tier").eq("id", user_id).limit(1).execute()
            if res.data and len(res.data) > 0:
                tier = res.data[0].get("subscription_tier")
                return tier.lower() if tier else "rookie"
        except Exception as e:
            logger.error(f"Error checking tier for {user_id}: {e}")
        return "rookie"

    @staticmethod
    def is_racer_or_team(user_id: str) -> bool:
        tier = KartService.get_subscription_tier(user_id)
        return tier in ["racer", "team"]

    @staticmethod
    def get_or_create_kart_profile(user_id: str) -> Dict[str, Any]:
        """Fetch kart_profile. Create it if it doesn't exist."""
        if not supabase:
            raise Exception("Supabase client not initialized")
        
        try:
            res = supabase.table("kart_profiles").select("*").eq("user_id", user_id).limit(1).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            
            # Create default profile
            new_profile = {
                "user_id": user_id,
                "mon_kart_enabled": True
            }
            create_res = supabase.table("kart_profiles").insert(new_profile).execute()
            if create_res.data and len(create_res.data) > 0:
                return create_res.data[0]
            return new_profile
        except Exception as e:
            logger.error(f"Error get_or_create_kart_profile: {e}")
            raise Exception("Could not retrieve or create Kart profile")

    @staticmethod
    def update_kart_profile(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update the kart profile (manual overrides)."""
        if not supabase:
            raise Exception("Supabase client not initialized")
        try:
            res = supabase.table("kart_profiles").update(updates).eq("user_id", user_id).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            return {}
        except Exception as e:
            logger.error(f"Error update_kart_profile: {e}")
            raise Exception("Could not update Kart profile")

    @staticmethod
    def get_sessions(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        if not supabase:
            return []
        try:
            res = supabase.table("kart_session_logs").select("*").eq("user_id", user_id).order("session_date", desc=True).limit(limit).execute()
            return res.data or []
        except Exception as e:
            logger.error(f"Error get_sessions: {e}")
            return []

    @staticmethod
    def get_component_history(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        if not supabase:
            return []
        try:
            res = supabase.table("kart_component_history").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
            return res.data or []
        except Exception as e:
            logger.error(f"Error get_component_history: {e}")
            return []

    @staticmethod
    def upsert_session(user_id: str, signature: str, imported_via: str, metrics: Dict[str, Any], analysis_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Upsert a session in kart_session_logs.
        If it's new (successful insert), increment the kart_profile counters.
        Returns the session record, and a boolean indicating if it was newly added (to prevent double counting).
        """
        if not supabase:
            raise Exception("Supabase client not initialized")
        
        try:
            # Check if exists
            existing_res = supabase.table("kart_session_logs").select("id").eq("user_id", user_id).eq("file_signature", signature).execute()
            if existing_res.data and len(existing_res.data) > 0:
                return {"session": existing_res.data[0], "is_new": False}
            
            # Insert
            session_data = {
                "user_id": user_id,
                "file_signature": signature,
                "imported_via": imported_via,
                "analysis_id": analysis_id,
                **metrics
            }
            insert_res = supabase.table("kart_session_logs").insert(session_data).execute()
            new_session = insert_res.data[0] if insert_res.data else {}
            
            # Increment Profile
            profile = KartService.get_or_create_kart_profile(user_id)
            updates: Dict[str, Any] = {}
            
            dur_hours = float(metrics.get("duration_hours", 0))
            if dur_hours > 0:
                updates["engine_hours_current"] = float(profile.get("engine_hours_current", 0)) + dur_hours
                updates["engine_sessions"] = float(profile.get("engine_sessions", 0)) + 1
            
            updates["tires_sessions_current"] = int(profile.get("tires_sessions_current", 0)) + 1
            updates["brakes_sessions_current"] = int(profile.get("brakes_sessions_current", 0)) + 1
            
            batt_avg = metrics.get("battery_voltage_avg")
            batt_min = metrics.get("battery_voltage_min")
            if batt_avg is not None:
                updates["battery_voltage_last"] = float(batt_avg)
            if batt_min is not None:
                current_min_ever = profile.get("battery_voltage_min_ever")
                if current_min_ever is None or float(batt_min) < float(current_min_ever):
                    updates["battery_voltage_min_ever"] = float(batt_min)
            
            KartService.update_kart_profile(user_id, updates)
            
            return {"session": new_session, "is_new": True}
        except Exception as e:
            logger.error(f"Error upsert_session: {e}")
            raise Exception(f"Could not upsert session: {e}")

    @staticmethod
    def reset_component(user_id: str, component_type: str, notes: Optional[str] = None) -> Dict[str, Any]:
        """Reset a component counter and log to history."""
        if not supabase:
            raise Exception("Supabase client not initialized")
        
        try:
            profile = KartService.get_or_create_kart_profile(user_id)
            prev_hours = None
            prev_sessions = None
            updates = {}
            
            if component_type == "engine":
                prev_hours = float(profile.get("engine_hours_current", 0))
                prev_sessions = float(profile.get("engine_sessions", 0))
                updates["engine_hours_current"] = 0.0
                updates["engine_sessions"] = 0.0
            elif component_type == "tires":
                prev_sessions = int(profile.get("tires_sessions_current", 0))
                updates["tires_sessions_current"] = 0
            elif component_type == "brakes":
                prev_sessions = int(profile.get("brakes_sessions_current", 0))
                updates["brakes_sessions_current"] = 0
            else:
                raise ValueError("Invalid component type")
                
            # Log history
            history_entry = {
                "user_id": user_id,
                "component_type": component_type,
                "previous_hours": prev_hours,
                "previous_sessions": prev_sessions,
                "notes": notes,
                "entry_type": "reset"
            }
            supabase.table("kart_component_history").insert(history_entry).execute()
            
            # Apply profile update
            updated_profile = KartService.update_kart_profile(user_id, updates)
            return updated_profile
        except Exception as e:
            logger.error(f"Error reset_component: {e}")
            raise Exception("Could not reset component")

    @staticmethod
    def add_maintenance_log(user_id: str, component_type: str, notes: str, date: Optional[str] = None) -> Dict[str, Any]:
        """Add a manual maintenance log entry without resetting counters."""
        if not supabase:
            raise Exception("Supabase client not initialized")
        try:
            history_entry = {
                "user_id": user_id,
                "component_type": component_type,
                "notes": notes,
                "entry_type": "manual"
            }
            if date:
                history_entry["created_at"] = date
                
            res = supabase.table("kart_component_history").insert(history_entry).execute()
            return res.data[0] if res.data else {}
        except Exception as e:
            logger.error(f"Error add_maintenance_log: {e}")
            raise Exception("Could not add maintenance log")

    @staticmethod
    def delete_session_and_recalculate(user_id: str, session_id: str) -> Dict[str, Any]:
        """Delete a session (autonomy requirement) and recalculate profile counters."""
        if not supabase:
            raise Exception("Supabase client not initialized")
            
        try:
            # Get session
            res = supabase.table("kart_session_logs").select("*").eq("id", session_id).eq("user_id", user_id).limit(1).execute()
            if not res.data or len(res.data) == 0:
                raise ValueError("Session not found")
                
            session_to_delete = res.data[0]
            
            # Delete it
            supabase.table("kart_session_logs").delete().eq("id", session_id).eq("user_id", user_id).execute()
            
            # Recalculate profile by fetching profile and decrementing
            profile = KartService.get_or_create_kart_profile(user_id)
            dur_hours = float(session_to_delete.get("duration_hours", 0))
            
            updates = {}
            if dur_hours > 0:
                new_eng_hours = max(0, float(profile.get("engine_hours_current", 0)) - dur_hours)
                new_eng_sess = max(0, float(profile.get("engine_sessions", 0)) - 1)
                updates["engine_hours_current"] = new_eng_hours
                updates["engine_sessions"] = new_eng_sess
                
            updates["tires_sessions_current"] = max(0, int(profile.get("tires_sessions_current", 0)) - 1)
            updates["brakes_sessions_current"] = max(0, int(profile.get("brakes_sessions_current", 0)) - 1)
            
            updated_profile = KartService.update_kart_profile(user_id, updates)
            return {"success": True, "profile": updated_profile}
        except Exception as e:
            logger.error(f"Error delete_session_and_recalculate: {e}")
            raise Exception(f"Could not delete session: {e}")
