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
if settings.ENVIRONMENT == "development":
    from .mock_db import MockSupabaseClient
    supabase = MockSupabaseClient()
    logger.info("Initialized local mock Supabase client for dev mode in kart_service")
elif SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and SUPABASE_SERVICE_ROLE_KEY not in ("", "ton_service_role_key"):
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
        # Toujours autoriser en mode développement local
        if settings.ENVIRONMENT == "development":
            return True
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
        
        # Extract circuit_id from either top-level or nested circuit dictionary
        circuit_id = setup_data.get("circuit_id")
        if not circuit_id and isinstance(setup_data.get("circuit"), dict):
            circuit_id = setup_data.get("circuit", {}).get("id") or setup_data.get("circuit", {}).get("value")

        # Prepare payload with snake_case keys for the database
        db_payload = {
            "user_id": user_id,
            "setup_name": setup_data.get("setupName", "Nouveau Setup"),
            "weather": setup_data.get("weather"),
            "air_temp": setup_data.get("airTemp"),
            "track_temp": setup_data.get("trackTemp"),
            "mode": setup_data.get("mode"),
            "circuit_id": circuit_id,
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
            "driver_weight": setup_data.get("driverWeight"),
            "kart_weight": setup_data.get("kartWeight"),
            "target_weight": setup_data.get("targetWeight"),
            "ballast": setup_data.get("ballast"),
            # Recommandations figées au moment de la génération (JSONB) :
            # restaurées telles quelles au rechargement, jamais recalculées.
            "recommendations": setup_data.get("recommendations"),
        }

        # Sanitize: the frontend sends '' for empty numeric fields, which breaks
        # numeric/integer DB columns. Convert '' -> None and cast numeric values.
        numeric_fields = {
            "air_temp", "track_temp",
            "cold_pressure_front", "cold_pressure_rear",
            "hot_pressure_front", "hot_pressure_rear",
            "track_width_front", "track_width_rear",
            "driver_weight", "kart_weight", "target_weight", "ballast",
        }
        integer_fields = {"sprocket_front", "sprocket_rear"}
        for key in list(db_payload.keys()):
            val = db_payload[key]
            if val == "":
                db_payload[key] = None
            elif key in numeric_fields and val is not None:
                try:
                    db_payload[key] = float(val)
                except (ValueError, TypeError):
                    db_payload[key] = None
            elif key in integer_fields and val is not None:
                try:
                    db_payload[key] = int(float(val))
                except (ValueError, TypeError):
                    db_payload[key] = None

        # Check if updating an existing setup
        setup_id = setup_data.get("id")
        if setup_id:
            try:
                res = supabase.table("kart_setups").update(db_payload).eq("id", setup_id).eq("user_id", user_id).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
                return {}
            except Exception as e:
                logger.error(f"Error updating kart_setup {setup_id}: {e}")
                raise Exception(f"Could not update Kart setup: {str(e)}")
        
        try:
            res = supabase.table("kart_setups").insert(db_payload).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            return {}
        except Exception as e:
            logger.error(f"Error save_kart_setup: {e}")
            raise Exception(f"Could not save Kart setup: {str(e)}")

    @staticmethod
    def get_kart_setups(user_id: str) -> List[Dict[str, Any]]:
        """Get all saved setups for a user, joined with circuit info if possible."""
        if not supabase:
            raise Exception("Supabase client not initialized")
            
        try:
            res = supabase.table("kart_setups").select("*, circuits(*)").eq("user_id", user_id).order("created_at", desc=True).execute()
            setups = res.data or []
            for setup in setups:
                if "circuits" in setup and setup["circuits"]:
                    KartService._normalize_circuit_read(setup["circuits"])
            return setups
        except Exception as e:
            logger.error(f"Error get_kart_setups: {e}")
            return []

    @staticmethod
    def rename_kart_setup(user_id: str, setup_id: str, new_name: str) -> Dict[str, Any]:
        """Rename a saved kart setup."""
        if not supabase:
            raise Exception("Supabase client not initialized")
        try:
            res = supabase.table("kart_setups").update({"setup_name": new_name}).eq("id", setup_id).eq("user_id", user_id).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            raise Exception("Setup not found or access denied")
        except Exception as e:
            logger.error(f"Error renaming kart_setup {setup_id}: {e}")
            raise Exception(f"Could not rename Kart setup: {str(e)}")

    @staticmethod
    def get_circuits() -> List[Dict[str, Any]]:
        """Get all circuits."""
        if not supabase:
            raise Exception("Supabase client not initialized")
            
        try:
            res = supabase.table("circuits").select("*").order("name").execute()
            circuits_data = res.data or []
            for c in circuits_data:
                KartService._normalize_circuit_read(c)
            return circuits_data
        except Exception as e:
            logger.error(f"Error get_circuits: {e}")
            return []

    @staticmethod
    def get_catalog_components(category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get the global component catalog (kart_components table)."""
        if not supabase:
            raise Exception("Supabase client not initialized")

        valid_categories = {"engine", "tire", "brake", "chassis", "carburetor", "axle"}
        try:
            query = supabase.table("kart_components").select("*").eq("active", True)
            if category:
                if category not in valid_categories:
                    return []
                query = query.eq("category", category)
            res = query.order("category").order("brand").order("name").execute()
            return res.data or []
        except Exception as e:
            logger.error(f"Error get_catalog_components: {e}")
            return []

    # Champs "caractéristiques" d'un circuit (stockés en numérique dans la DB prod)
    CIRCUIT_FEATURE_KEYS = {
        "speed_ratio", "rotation", "hairpins_count",
        "fast_corners_count", "elevation", "bumpiness",
    }

    @staticmethod
    def _circuit_payload_to_db(circuit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Filtre les clés autorisées et convertit les valeurs texte -> codes numériques DB."""
        allowed_keys = {
            "name", "slug", "speed_ratio", "rotation", "hairpins_count",
            "fast_corners_count", "elevation", "bumpiness"
        }
        p = {k: v for k, v in circuit_data.items() if k in allowed_keys}

        for k in ["hairpins_count", "fast_corners_count"]:
            if k in p and p[k] is not None:
                try:
                    p[k] = int(p[k])
                except (ValueError, TypeError):
                    pass

        if isinstance(p.get("bumpiness"), str):
            p["bumpiness"] = 1 if p["bumpiness"].lower() == "bossele" else 0
        if isinstance(p.get("elevation"), str):
            p["elevation"] = 1 if p["elevation"].lower() == "vallonne" else 0
        if isinstance(p.get("rotation"), str):
            p["rotation"] = 1 if p["rotation"].lower() == "anti-horaire" else 0
        if isinstance(p.get("speed_ratio"), str):
            p["speed_ratio"] = {"sinueux": 0, "mixte": 1, "rapide": 2}.get(p["speed_ratio"].lower(), 1)
        return p

    @staticmethod
    def _normalize_circuit_read(c: Dict[str, Any]) -> Dict[str, Any]:
        """Convertit les codes numériques DB -> valeurs texte attendues par le frontend.
        Les NULL restent NULL (le frontend applique ses propres défauts)."""
        if c.get("bumpiness") is not None and not isinstance(c["bumpiness"], str):
            c["bumpiness"] = "bossele" if c["bumpiness"] == 1 else "lisse"
        if c.get("elevation") is not None and not isinstance(c["elevation"], str):
            c["elevation"] = "vallonne" if c["elevation"] == 1 else "plat"
        if c.get("rotation") is not None and not isinstance(c["rotation"], str):
            c["rotation"] = "anti-horaire" if c["rotation"] == 1 else "horaire"
        if c.get("speed_ratio") is not None and not isinstance(c["speed_ratio"], str):
            c["speed_ratio"] = {0: "sinueux", 1: "mixte", 2: "rapide"}.get(c["speed_ratio"], "mixte")
        return c

    @staticmethod
    def create_circuit(circuit_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Create a circuit, or match+enrich an existing one.

        Matching flou par slug (ex: 'adria-kart' issu du header télémétrie
        rapproché de la fiche seedée 'adria-karting-raceway'). Quand un circuit
        existant est trouvé, ses caractéristiques NULL sont remplies avec les
        nouvelles données (jamais écrasées si déjà renseignées).
        """
        if not supabase:
            raise Exception("Supabase client not initialized")

        try:
            from slugify import slugify
            generated_slug = slugify(circuit_data.get("name", "circuit"))

            all_res = supabase.table("circuits").select("*").execute()
            circuits = all_res.data or []

            existing = next((c for c in circuits if c.get("slug") == generated_slug), None)
            if not existing and len(generated_slug) >= 8:
                for c in circuits:
                    s = c.get("slug") or ""
                    if len(s) >= 8 and (s.startswith(generated_slug) or generated_slug.startswith(s)):
                        existing = c
                        logger.info(f"create_circuit: fuzzy match '{generated_slug}' -> '{s}'")
                        break

            db_payload = KartService._circuit_payload_to_db({**circuit_data, "slug": generated_slug})

            if existing:
                # Enrichissement : on remplit uniquement les champs encore vides
                fill = {
                    k: v for k, v in db_payload.items()
                    if k in KartService.CIRCUIT_FEATURE_KEYS and v is not None and existing.get(k) is None
                }
                if fill:
                    upd = supabase.table("circuits").update(fill).eq("id", existing["id"]).execute()
                    if upd.data and len(upd.data) > 0:
                        existing = upd.data[0]
                    logger.info(f"create_circuit: enriched '{existing.get('slug')}' with {sorted(fill.keys())}")
                return KartService._normalize_circuit_read(existing)

            db_payload["created_by"] = user_id
            db_payload["verified"] = False

            res = supabase.table("circuits").insert(db_payload).execute()
            if res.data and len(res.data) > 0:
                return KartService._normalize_circuit_read(res.data[0])
            raise Exception("Insertion failed")
        except Exception as e:
            logger.error(f"Error create_circuit: {e}")
            raise Exception(f"Could not create circuit: {e}")

    @staticmethod
    def update_circuit(circuit_id: str, circuit_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Update an existing circuit."""
        if not supabase:
            raise Exception("Supabase client not initialized")
            
        try:
            # Les circuits officiels (verified) sont protégés : données de référence.
            # Les circuits perso ne sont modifiables que par leur créateur.
            current = supabase.table("circuits").select("id, verified, created_by").eq("id", circuit_id).limit(1).execute()
            if current.data and current.data[0].get("verified"):
                raise Exception("Ce circuit officiel ApexAI n'est pas modifiable.")
            owner = current.data[0].get("created_by") if current.data else None
            if owner and owner != user_id:
                raise Exception("Ce circuit appartient à un autre pilote.")

            from slugify import slugify
            circuit_data["slug"] = slugify(circuit_data.get("name", "circuit"))
            db_payload = KartService._circuit_payload_to_db(circuit_data)

            res = supabase.table("circuits").update(db_payload).eq("id", circuit_id).execute()
            if res.data and len(res.data) > 0:
                return KartService._normalize_circuit_read(res.data[0])
            raise Exception("Update failed")
        except Exception as e:
            logger.error(f"Error update_circuit: {e}")
            raise Exception(f"Could not update circuit: {e}")

    @staticmethod
    def estimate_kart_weight(user_id: str) -> Dict[str, Any]:
        """Estime la masse totale kart + pilote depuis le Garage.

        Somme : poids châssis (catalogue) + poids moteur (catalogue)
              + poids pilote (profil, équipement compris).
        Retourne le détail complet pour affichage transparent — c'est une
        ESTIMATION (±3 kg : essence, lest, accessoires non comptés).
        """
        from src.api.advisor_service import _norm

        profile = KartService.get_or_create_kart_profile(user_id)
        setup_json = profile.get("setup_json") or {}
        components = KartService.get_catalog_components()

        def match_component(label: str, category: str) -> Optional[Dict[str, Any]]:
            target = set(_norm(label or "").split())
            if not target:
                return None
            best, best_score = None, 0.0
            for c in components:
                if c.get("category") != category:
                    continue
                cand = set(_norm(f"{c.get('brand','')} {c.get('name','')}").split())
                if not cand:
                    continue
                score = len(target & cand) / len(cand)
                if score > best_score:
                    best, best_score = c, score
            return best if best_score >= 0.5 else None

        chassis_label = f"{setup_json.get('chassis_brand', '')} {setup_json.get('chassis_model', '')}".strip() \
            or profile.get("chassis_brand") or ""
        engine_label = profile.get("engine_model") or ""

        chassis = match_component(chassis_label, "chassis")
        engine = match_component(engine_label, "engine")
        chassis_w = (chassis or {}).get("specs", {}).get("weight_kg")
        engine_w = (engine or {}).get("specs", {}).get("weight_kg")
        driver_w = profile.get("driver_weight_kg")

        missing = []
        if not chassis_label or chassis_w is None:
            missing.append("chassis")
        if not engine_label or engine_w is None:
            missing.append("engine")
        if driver_w is None:
            missing.append("driver")

        kart_w = None
        if chassis_w is not None and engine_w is not None:
            kart_w = round(float(chassis_w) + float(engine_w), 1)

        total = None
        if kart_w is not None and driver_w is not None:
            total = round(kart_w + float(driver_w), 1)

        return {
            "driver_weight_kg": float(driver_w) if driver_w is not None else None,
            "chassis": {
                "label": f"{chassis['brand']} {chassis['name']}" if chassis else (chassis_label or None),
                "weight_kg": float(chassis_w) if chassis_w is not None else None,
            },
            "engine": {
                "label": f"{engine['brand']} {engine['name']}" if engine else (engine_label or None),
                "weight_kg": float(engine_w) if engine_w is not None else None,
            },
            "kart_weight_kg": kart_w,          # châssis + moteur = kart à vide estimé
            "estimated_total_kg": total,       # + pilote
            "tolerance_kg": 3,
            "missing": missing,
        }

    # ─────────────────────────────────────────────
    # Stock de trains de pneus (kart_tire_sets)
    # ─────────────────────────────────────────────

    TIRE_SET_FIELDS = {"label", "component_id", "custom_model", "state", "is_rain", "laps_current", "laps_life", "active", "notes", "is_mounted"}

    @staticmethod
    def _sanitize_tire_set(payload: Dict[str, Any]) -> Dict[str, Any]:
        p = {k: v for k, v in payload.items() if k in KartService.TIRE_SET_FIELDS}
        for k in ("laps_current", "laps_life"):
            if k in p and p[k] is not None:
                try:
                    p[k] = max(0, int(p[k]))
                except (ValueError, TypeError):
                    p.pop(k)
        if p.get("state") not in (None, "neuf", "rode", "use"):
            p["state"] = "neuf"
        return p

    @staticmethod
    def get_tire_sets(user_id: str) -> List[Dict[str, Any]]:
        """Get the user's tire sets, enriched with the catalog label if linked."""
        if not supabase:
            raise Exception("Supabase client not initialized")
        try:
            res = supabase.table("kart_tire_sets").select("*, kart_components(brand, name, subcategory)") \
                .eq("user_id", user_id).order("is_mounted", desc=True).order("created_at").execute()
            sets = res.data or []
            for t in sets:
                comp = t.pop("kart_components", None)
                if comp:
                    t["component_label"] = f"{comp.get('brand', '')} {comp.get('name', '')}".strip()
                    t["compound"] = comp.get("subcategory")
            return sets
        except Exception as e:
            logger.error(f"Error get_tire_sets: {e}")
            return []

    @staticmethod
    def create_tire_set(user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not supabase:
            raise Exception("Supabase client not initialized")
        try:
            p = KartService._sanitize_tire_set(payload)
            p["user_id"] = user_id
            if not p.get("label"):
                existing = KartService.get_tire_sets(user_id)
                p["label"] = f"Train {len(existing) + 1}"
            res = supabase.table("kart_tire_sets").insert(p).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            raise Exception("Insertion failed")
        except Exception as e:
            logger.error(f"Error create_tire_set: {e}")
            raise Exception(f"Could not create tire set: {e}")

    @staticmethod
    def update_tire_set(user_id: str, set_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not supabase:
            raise Exception("Supabase client not initialized")
        try:
            p = KartService._sanitize_tire_set(payload)
            res = supabase.table("kart_tire_sets").update(p).eq("id", set_id).eq("user_id", user_id).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            raise Exception("Tire set not found")
        except Exception as e:
            logger.error(f"Error update_tire_set: {e}")
            raise Exception(f"Could not update tire set: {e}")

    @staticmethod
    def mount_tire_set(user_id: str, set_id: str) -> Dict[str, Any]:
        """Mark a tire set as the one currently mounted on the kart (exclusive)."""
        if not supabase:
            raise Exception("Supabase client not initialized")
        try:
            # Démonter tous les autres trains, puis monter celui-ci
            supabase.table("kart_tire_sets").update({"is_mounted": False}) \
                .eq("user_id", user_id).eq("is_mounted", True).execute()
            res = supabase.table("kart_tire_sets").update({"is_mounted": True}) \
                .eq("id", set_id).eq("user_id", user_id).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            raise Exception("Tire set not found")
        except Exception as e:
            logger.error(f"Error mount_tire_set: {e}")
            raise Exception(f"Could not mount tire set: {e}")

    @staticmethod
    def delete_tire_set(user_id: str, set_id: str) -> Dict[str, Any]:
        if not supabase:
            raise Exception("Supabase client not initialized")
        try:
            supabase.table("kart_tire_sets").delete().eq("id", set_id).eq("user_id", user_id).execute()
            return {"deleted": True, "id": set_id}
        except Exception as e:
            logger.error(f"Error delete_tire_set: {e}")
            raise Exception(f"Could not delete tire set: {e}")

    @staticmethod
    def delete_circuit(circuit_id: str, user_id: str) -> Dict[str, Any]:
        """Delete a non-official circuit. Official (verified) circuits are protected."""
        if not supabase:
            raise Exception("Supabase client not initialized")

        try:
            cur = supabase.table("circuits").select("id, verified, name, created_by").eq("id", circuit_id).limit(1).execute()
            if not cur.data or len(cur.data) == 0:
                raise Exception("Circuit introuvable.")
            circuit = cur.data[0]
            if circuit.get("verified"):
                raise Exception("Ce circuit officiel ApexAI ne peut pas être supprimé.")
            owner = circuit.get("created_by")
            if owner and owner != user_id:
                raise Exception("Ce circuit appartient à un autre pilote.")

            # Détacher les réglages qui référencent ce circuit (contrainte FK)
            supabase.table("kart_setups").update({"circuit_id": None}).eq("circuit_id", circuit_id).execute()
            supabase.table("circuits").delete().eq("id", circuit_id).execute()
            logger.info(f"delete_circuit: '{circuit.get('name')}' ({circuit_id}) deleted by {user_id}")
            return {"deleted": True, "id": circuit_id}
        except Exception as e:
            logger.error(f"Error delete_circuit: {e}")
            raise Exception(f"Could not delete circuit: {e}")

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
            existing_res = supabase.table("kart_session_logs").select("id, track_features, circuit_name").eq("user_id", user_id).eq("file_signature", signature).execute()
            if existing_res.data and len(existing_res.data) > 0:
                existing_session = existing_res.data[0]
                # Backfill : les sessions importées avant la signature de piste
                # récupèrent track_features/circuit_name à la ré-analyse.
                backfill: Dict[str, Any] = {}
                if metrics.get("track_features") and not existing_session.get("track_features"):
                    backfill["track_features"] = metrics["track_features"]
                if metrics.get("circuit_name") and not existing_session.get("circuit_name"):
                    backfill["circuit_name"] = metrics["circuit_name"]
                if backfill:
                    upd = supabase.table("kart_session_logs").update(backfill).eq("id", existing_session["id"]).execute()
                    if upd.data and len(upd.data) > 0:
                        existing_session = upd.data[0]
                    logger.info(f"upsert_session: backfilled {sorted(backfill.keys())}")
                return {"session": existing_session, "is_new": False}
            
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

            # Décrémente aussi l'usure du TRAIN MONTÉ (stock de pneus).
            # Best-effort : ne doit jamais faire échouer l'import de session.
            if laps > 0:
                try:
                    mounted = supabase.table("kart_tire_sets").select("id, laps_current") \
                        .eq("user_id", user_id).eq("is_mounted", True).eq("active", True).limit(1).execute()
                    if mounted.data and len(mounted.data) > 0:
                        m = mounted.data[0]
                        supabase.table("kart_tire_sets").update(
                            {"laps_current": int(m.get("laps_current") or 0) + laps}
                        ).eq("id", m["id"]).execute()
                except Exception as tire_err:
                    logger.warning(f"upsert_session: tire set wear update skipped: {tire_err}")

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

    @staticmethod
    def delete_kart_setup(user_id: str, setup_id: str) -> Dict[str, Any]:
        """Delete a kart setup."""
        if not supabase:
            raise Exception("Supabase client not initialized")
        try:
            res = supabase.table("kart_setups").delete().eq("id", setup_id).eq("user_id", user_id).execute()
            return {"success": True}
        except Exception as e:
            logger.error(f"Error delete_kart_setup: {e}")
            raise Exception(f"Could not delete Kart setup: {str(e)}")

