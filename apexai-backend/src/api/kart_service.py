import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
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
    def save_kart_setup(user_id: str, setup_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save a new kart setup to the kart_setups table."""
        if not supabase:
            raise Exception("Supabase client not initialized")
        
        # Prepare payload with snake_case keys for the database
        db_payload = {
            "user_id": user_id,
            "setup_name": setup_data.get("setupName", "Nouveau Setup"),
            "weather": setup_data.get("weather"),
            "air_temp": setup_data.get("airTemp"),
            "track_temp": setup_data.get("trackTemp"),
            "mode": setup_data.get("mode"),
            "circuit": setup_data.get("circuit"),
            "circuit_id": setup_data.get("circuit_id"),
            "tire_model": setup_data.get("tireModel"),
            "cold_pressure_front": setup_data.get("coldPressureFront"),
            "cold_pressure_rear": setup_data.get("coldPressureRear"),
            "hot_pressure_front": setup_data.get("hotPressureFront"),
            "hot_pressure_rear": setup_data.get("hotPressureRear"),
            "track_width_front": setup_data.get("trackWidthFront"),
            "track_width_rear": setup_data.get("trackWidthRear"),
            "ride_height_front": setup_data.get("rideHeightFront"),
            "ride_height_rear": setup_data.get("rideHeightRear"),
            "camber": setup_data.get("camber"),
            "caster": setup_data.get("caster"),
            "rear_axle": setup_data.get("rearAxle"),
            "sprocket_front": setup_data.get("sprocketFront"),
            "sprocket_rear": setup_data.get("sprocketRear"),
            "carb_config": setup_data.get("carbConfig"),
        }
        
        try:
            res = supabase.table("kart_setups").insert(db_payload).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            return {}
        except Exception as e:
            logger.error(f"Error save_kart_setup: {e}")
            raise Exception("Could not save Kart setup")

    @staticmethod
    def get_kart_setups(user_id: str) -> List[Dict[str, Any]]:
        """Get all saved setups for a user, joined with circuit info if possible."""
        if not supabase:
            raise Exception("Supabase client not initialized")
            
        try:
            res = supabase.table("kart_setups").select("*, circuits(*)").eq("user_id", user_id).order("created_at", desc=True).execute()
            return res.data or []
        except Exception as e:
            logger.error(f"Error get_kart_setups: {e}")
            return []

    @staticmethod
    def get_circuits() -> List[Dict[str, Any]]:
        """Get all circuits."""
        if not supabase:
            raise Exception("Supabase client not initialized")
            
        try:
            res = supabase.table("circuits").select("*").order("name").execute()
            return res.data or []
        except Exception as e:
            logger.error(f"Error get_circuits: {e}")
            return []

    @staticmethod
    def create_circuit(circuit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new circuit."""
        if not supabase:
            raise Exception("Supabase client not initialized")
            
        try:
            res = supabase.table("circuits").insert(circuit_data).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            return {}
        except Exception as e:
            logger.error(f"Error create_circuit: {e}")
            raise Exception("Could not create circuit")

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
                updates["chain_hours_current"] = float(profile.get("chain_hours_current") or 0.0) + dur_hours
            
            laps = int(metrics.get("laps_count", 0))
            if laps > 0:
                updates["tires_laps_current"] = int(profile.get("tires_laps_current") or 0) + laps
                updates["brakes_sessions_current"] = int(profile.get("brakes_sessions_current") or 0) + laps
            
            updates["tires_sessions_current"] = int(profile.get("tires_sessions_current", 0)) + 1
            
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
            logger.error(f"Supabase not initialized in reset_component for {user_id}")
            raise Exception("Supabase client not initialized")
        
        # Ensure lowercase for consistent DB storage and logic
        comp_type = component_type.lower()
        
        try:
            profile = KartService.get_or_create_kart_profile(user_id)
            prev_hours = None
            prev_sessions = None
            updates = {}
            
            if comp_type == "engine":
                raw_hours = profile.get("engine_hours_current")
                prev_hours = float(raw_hours) if raw_hours is not None else 0.0
                raw_sessions = profile.get("engine_sessions")
                prev_sessions = int(float(raw_sessions)) if raw_sessions is not None else 0
                updates["engine_hours_current"] = 0.0
                updates["engine_sessions"] = 0.0
            elif comp_type == "tires":
                raw_sessions = profile.get("tires_sessions_current")
                prev_sessions = int(raw_sessions) if raw_sessions is not None else 0
                updates["tires_sessions_current"] = 0
            elif comp_type == "brakes":
                raw_sessions = profile.get("brakes_sessions_current")
                prev_sessions = int(raw_sessions) if raw_sessions is not None else 0
                updates["brakes_sessions_current"] = 0
            else:
                logger.warning(f"Invalid component type received: {comp_type}")
                raise ValueError(f"Invalid component type: {comp_type}")
                
            # Log history
            history_entry = {
                "user_id": user_id,
                "component_type": comp_type,
                "previous_hours": prev_hours,
                "previous_sessions": prev_sessions,
                "notes": notes,
                "entry_type": "reset"
            }
            logger.info(f"Inserting history entry for reset: {history_entry}")
            hist_res = supabase.table("kart_component_history").insert(history_entry).execute()
            if not hist_res.data:
                logger.error(f"Failed to insert history entry for reset. Response: {hist_res}")
            
            # Apply profile update
            updated_profile = KartService.update_kart_profile(user_id, updates)
            return updated_profile
        except Exception as e:
            logger.exception(f"Error in reset_component for user {user_id}: {e}")
            raise Exception(f"Could not reset component: {str(e)}")

    @staticmethod
    def add_maintenance_log(user_id: str, component_type: str, notes: str, date: Optional[str] = None) -> Dict[str, Any]:
        """Add a manual maintenance log entry without resetting counters."""
        if not supabase:
            raise Exception("Supabase client not initialized")
        
        # Ensure lowercase
        comp_type = component_type.lower()
        
        try:
            history_entry = {
                "user_id": user_id,
                "component_type": comp_type,
                "notes": notes,
                "entry_type": "manual"
            }
            if date:
                history_entry["created_at"] = date
                
            res = supabase.table("kart_component_history").insert(history_entry).execute()
            return res.data[0] if res.data else {}
        except Exception as e:
            logger.exception(f"Error add_maintenance_log for {user_id}: {e}")
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

    @staticmethod
    def delete_history_entry(user_id: str, entry_id: str) -> Dict[str, Any]:
        """Delete a maintenance history entry owned by this user."""
        if not supabase:
            raise Exception("Supabase client not initialized")
        try:
            logger.info(f"Attempting to delete history entry {entry_id} for user {user_id}")
            # Verify ownership
            res = supabase.table("kart_component_history").select("id").eq("id", entry_id).eq("user_id", user_id).limit(1).execute()
            if not res.data or len(res.data) == 0:
                logger.warning(f"History entry {entry_id} not found for user {user_id}")
                raise ValueError(f"History entry {entry_id} not found")
            
            supabase.table("kart_component_history").delete().eq("id", entry_id).eq("user_id", user_id).execute()
            logger.info(f"Successfully deleted history entry {entry_id}")
            return {"success": True, "deleted_id": entry_id}
        except ValueError:
            raise
        except Exception as e:
            logger.exception(f"Error delete_history_entry for {user_id}: {e}")
            raise Exception(f"Could not delete history entry: {str(e)}")

    @staticmethod
    def delete_sessions_by_day(user_id: str, date_str: str) -> Dict[str, Any]:
        """Delete all sessions for a given day (yyyy-MM-dd) and recalculate profile."""
        if not supabase:
            raise Exception("Supabase client not initialized")
        try:
            # More robust date comparison using strictly gte/lt (next day)
            dt_current = datetime.strptime(date_str, "%Y-%m-%d")
            dt_next = dt_current + timedelta(days=1)
            
            start = dt_current.strftime("%Y-%m-%dT00:00:00+00:00")
            end_strict = dt_next.strftime("%Y-%m-%dT00:00:00+00:00")
            
            logger.info(f"Deleting sessions for user {user_id} on day {date_str} (Range: {start} to {end_strict})")
            
            # Fetch sessions where EITHER session_date OR created_at (if session_date is null) matches the day.
            # Postgrest 'or' filter for complex conditions.
            # Format: .or(cond1, cond2)
            # cond1: session_date is in range
            # cond2: session_date is null AND created_at is in range
            q1 = f"and(session_date.gte.{start},session_date.lt.{end_strict})"
            q2 = f"and(session_date.is.null,created_at.gte.{start},created_at.lt.{end_strict})"
            
            res = supabase.table("kart_session_logs").select("*").eq("user_id", user_id).or_(f"{q1},{q2}").execute()
            sessions = res.data or []
            
            if len(sessions) == 0:
                logger.warning(f"No sessions found for user {user_id} on day {date_str} (tried session_date and created_at fallback)")
                raise ValueError(f"No sessions found for day {date_str}")
            
            # Delete all sessions found
            count = 0
            total_dur = 0.0
            for sess in sessions:
                # We delete by specific ID to be safe
                del_res = supabase.table("kart_session_logs").delete().eq("id", sess["id"]).eq("user_id", user_id).execute()
                if del_res.data:
                    count += 1
                    total_dur += float(sess.get("duration_hours", 0))
                else:
                    logger.error(f"Failed to delete session {sess['id']}")
            
            # Recalculate profile
            profile = KartService.get_or_create_kart_profile(user_id)
            
            updates = {}
            if total_dur > 0 or count > 0:
                updates["engine_hours_current"] = max(0.0, float(profile.get("engine_hours_current", 0)) - total_dur)
                updates["engine_sessions"] = max(0.0, float(profile.get("engine_sessions", 0)) - count)
                updates["tires_sessions_current"] = max(0, int(profile.get("tires_sessions_current", 0)) - count)
                updates["brakes_sessions_current"] = max(0, int(profile.get("brakes_sessions_current", 0)) - count)
            
            updated_profile = KartService.update_kart_profile(user_id, updates)
            return {"success": True, "deleted_count": count, "profile": updated_profile}
        except ValueError:
            raise
        except Exception as e:
            logger.exception(f"Error delete_sessions_by_day for {user_id}: {e}")
            raise Exception(f"Could not delete sessions: {str(e)}")
