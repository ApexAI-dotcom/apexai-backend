/**
 * Apex AI - API Client
 * Client TypeScript pour communiquer avec le backend FastAPI
 */

// Configuration - unique source for API URL (VITE_API_URL en prod)
export const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const API_TIMEOUT_MS = 30000; // 30 secondes
const MAX_FILE_SIZE_MB = 50;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

// ============================================================================
// TYPES
// ============================================================================

export interface ScoreBreakdown {
  apex_precision: number;
  trajectory_consistency: number;
  apex_speed: number;
  sector_times: number;
}

export interface PerformanceScore {
  overall_score: number;
  grade: string; // "A+", "A", "B", "C", "D"
  breakdown: ScoreBreakdown;
  percentile?: number;
}

/** Max par catégorie (somme = 100). */
export const BREAKDOWN_MAX = {
  apex_precision: 30,
  trajectory_consistency: 25,
  apex_speed: 25,
  sector_times: 20,
} as const;

/**
 * Valeur de score à afficher : overall_score uniquement.
 * Si incohérence avec sum(breakdown) > 0.5, log warning et utilise la somme en fallback.
 */
export function getDisplayScore(ps: PerformanceScore): number {
  const b = ps.breakdown;
  const sum =
    (b?.apex_precision ?? 0) +
    (b?.trajectory_consistency ?? 0) +
    (b?.apex_speed ?? 0) +
    (b?.sector_times ?? 0);
  const overall = ps.overall_score ?? 0;
  if (Math.abs(sum - overall) > 0.5) {
    console.warn(
      "[ApexAI] Score inconsistency: overall_score",
      overall,
      "!= sum(breakdown)",
      sum,
      "; using sum as fallback."
    );
    return Math.round(sum * 10) / 10;
  }
  return overall;
}

export interface PerLapCornerData {
  lap: number;
  apex_speed_kmh?: number;
  max_lateral_g?: number;
  time_lost?: number;
}

export interface CornerAnalysis {
  corner_id: number;
  corner_number: number;
  corner_type: string; // "left" | "right" | "unknown"
  apex_speed_real: number;
  apex_speed_optimal: number;
  speed_efficiency: number;
  apex_distance_error: number;
  apex_direction_error: string;
  lateral_g_max: number;
  time_lost: number;
  grade: string;
  score: number;
  entry_speed?: number | null;
  exit_speed?: number | null;
  target_entry_speed?: number | null;
  target_exit_speed?: number | null;
  label?: string;
  avg_note?: string;
  per_lap_data?: PerLapCornerData[];
  apex_lat?: number | null;
  apex_lon?: number | null;
}

const CORNER_KEYS: (keyof CornerAnalysis)[] = [
  "corner_id", "corner_number", "corner_type", "apex_speed_real", "apex_speed_optimal",
  "speed_efficiency", "apex_distance_error", "apex_direction_error", "lateral_g_max",
  "time_lost", "grade", "score"
];

/**
 * Normalise un objet virage brut de l'API vers CornerAnalysis.
 * Gère les clés alternatives (type → corner_type, apex_distance_m → apex_distance_error)
 * et log un warning si une clé attendue est absente.
 */
export function mapCornerData(raw: Record<string, unknown>): CornerAnalysis {
  const corner_type = (raw.corner_type ?? raw.type ?? "unknown") as string;
  const apex_distance_error = Number(raw.apex_distance_error ?? raw.apex_distance_m ?? 0);
  const time_lost = Number(raw.time_lost ?? 0);
  if (raw.type !== undefined && raw.corner_type === undefined) {
    console.warn("[ApexAI] corner: expected 'corner_type', got 'type'");
  }
  if (raw.apex_distance_m !== undefined && raw.apex_distance_error === undefined) {
    console.warn("[ApexAI] corner: expected 'apex_distance_error', got 'apex_distance_m'");
  }
  for (const k of CORNER_KEYS) {
    if (k === "corner_type" || k === "apex_distance_error" || k === "time_lost") continue;
    if (raw[k] === undefined && (k === "corner_id" || k === "corner_number" || k === "grade" || k === "score")) {
      console.warn("[ApexAI] corner: missing expected key", k);
    }
  }
  return {
    corner_id: Number(raw.corner_id ?? 0),
    corner_number: Number(raw.corner_number ?? raw.corner_id ?? 0),
    corner_type,
    apex_speed_real: Number(raw.apex_speed_real ?? 0),
    apex_speed_optimal: Number(raw.apex_speed_optimal ?? 0),
    speed_efficiency: Number(raw.speed_efficiency ?? 0),
    apex_distance_error,
    apex_direction_error: String(raw.apex_direction_error ?? "center"),
    lateral_g_max: Number(raw.lateral_g_max ?? 0),
    time_lost,
    grade: String(raw.grade ?? "C"),
    score: Number(raw.score ?? 50),
    entry_speed: raw.entry_speed != null ? Number(raw.entry_speed) : undefined,
    exit_speed: raw.exit_speed != null ? Number(raw.exit_speed) : undefined,
    target_entry_speed: raw.target_entry_speed != null ? Number(raw.target_entry_speed) : undefined,
    target_exit_speed: raw.target_exit_speed != null ? Number(raw.target_exit_speed) : undefined,
    label: raw.label != null ? String(raw.label) : undefined,
    avg_note: raw.avg_note != null ? String(raw.avg_note) : undefined,
    per_lap_data: Array.isArray(raw.per_lap_data) ? (raw.per_lap_data as PerLapCornerData[]) : undefined,
    apex_lat: raw.apex_lat != null ? Number(raw.apex_lat) : undefined,
    apex_lon: raw.apex_lon != null ? Number(raw.apex_lon) : undefined,
  };
}

export interface CoachingAdvice {
  priority: number;
  category: string; // "braking" | "apex" | "speed" | "trajectory" | "global"
  impact_seconds: number;
  corner?: number;
  message: string;
  explanation: string;
  difficulty: string; // "facile" | "moyen" | "difficile"
}

/**
 * Normalise un conseil brut (impact_seconds vs time_impact_seconds).
 */
function mapAdviceData(raw: Record<string, unknown>): CoachingAdvice {
  const impact_seconds = Number(raw.impact_seconds ?? raw.time_impact_seconds ?? 0);
  if (raw.time_impact_seconds !== undefined && raw.impact_seconds === undefined) {
    console.warn("[ApexAI] coaching: expected 'impact_seconds', got 'time_impact_seconds'");
  }
  return {
    priority: Number(raw.priority ?? 5),
    category: String(raw.category ?? "global"),
    impact_seconds,
    corner: raw.corner != null ? Number(raw.corner) : undefined,
    message: String(raw.message ?? ""),
    explanation: String(raw.explanation ?? ""),
    difficulty: String(raw.difficulty ?? "moyen"),
  };
}

export interface PlotUrls {
  trajectory_2d?: string;
  speed_heatmap?: string;
  lateral_g_chart?: string;
  speed_trace?: string;
  throttle_brake?: string;
  sector_times?: string;
  apex_precision?: string;
  performance_radar?: string;
  performance_score_breakdown?: string;
  corner_heatmap?: string;
  [key: string]: string | undefined;
}

export interface Statistics {
  processing_time_seconds: number;
  data_points: number;
  best_corners: number[];
  worst_corners: number[];
  avg_apex_distance: number;
  avg_apex_speed_efficiency: number;
  laps_analyzed?: number;
}

export interface SessionConditions {
  track_condition: string; // "dry" | "damp" | "wet" | "rain"
  track_temperature?: number | null; // °C
}

export interface AnalysisResult {
  success: boolean;
  analysis_id: string;
  timestamp: string;
  corners_detected: number;
  lap_time: number;
  best_lap_time?: number | null;
  avg_lap_time?: number | null;
  lap_times?: number[] | null;
  performance_score: PerformanceScore;
  corner_analysis: CornerAnalysis[];
  coaching_advice: CoachingAdvice[];
  plots: PlotUrls;
  statistics: Statistics;
  session_conditions?: SessionConditions | null;
}

export interface LapInfo {
  lap_number: number;
  lap_time_seconds: number;
  points_count: number;
  is_outlier: boolean;
}

export interface ParseLapsResponse {
  success: boolean;
  laps: LapInfo[];
}

export interface AnalysisStatus {
  analysis_id: string;
  status: string; // "completed" | "processing" | "failed"
  message?: string;
}

export interface BackendHealth {
  status: string;
  version?: string;
  environment?: string;
}

export interface ApiError {
  success: false;
  error: string;
  message: string;
  details?: unknown;
}

// ============================================================================
// UTILITIES
// ============================================================================

/**
 * Crée un AbortController avec timeout
 */
function createTimeoutController(timeoutMs: number): AbortController {
  const controller = new AbortController();
  setTimeout(() => controller.abort(), timeoutMs);
  return controller;
}

/**
 * Valide un fichier CSV avant upload
 */
function validateCSVFile(file: File): { valid: boolean; error?: string } {
  // Vérifier extension
  if (!file.name.toLowerCase().endsWith(".csv")) {
    return {
      valid: false,
      error: "Le fichier doit être un CSV (.csv)",
    };
  }

  // Vérifier taille
  if (file.size > MAX_FILE_SIZE_BYTES) {
    const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
    return {
      valid: false,
      error: `Fichier trop volumineux (${sizeMB}MB). Maximum: ${MAX_FILE_SIZE_MB}MB`,
    };
  }

  if (file.size < 1000) {
    return {
      valid: false,
      error: "Fichier trop petit (<1KB). Vérifiez que c'est un CSV valide.",
    };
  }

  return { valid: true };
}

/**
 * Gère les erreurs de fetch et retourne un message utilisateur-friendly
 */
function handleFetchError(error: unknown, context: string): ApiError {
  if (error instanceof Error) {
    // Timeout
    if (error.name === "AbortError") {
      return {
        success: false,
        error: "timeout",
        message: "La requête a expiré (timeout 30s). Le fichier est peut-être trop volumineux.",
      };
    }

    // Network error
    if (error.message.includes("Failed to fetch") || error.message.includes("NetworkError")) {
      return {
        success: false,
        error: "network",
        message: `Impossible de se connecter au serveur. Vérifiez que le backend est accessible (${API_BASE_URL})`,
      };
    }

    // Autre erreur
    return {
      success: false,
      error: "unknown",
      message: `Erreur lors de ${context}: ${error.message}`,
    };
  }

  return {
    success: false,
    error: "unknown",
    message: `Erreur inconnue lors de ${context}`,
  };
}

/**
 * Parse une réponse JSON avec gestion d'erreurs
 */
async function parseJSONResponse<T>(response: Response): Promise<T> {
  const text = await response.text();

  if (!text) {
    throw new Error("Réponse vide du serveur");
  }

  try {
    return JSON.parse(text) as T;
  } catch (error) {
    throw new Error(`Réponse JSON invalide: ${text.substring(0, 100)}`);
  }
}

// ============================================================================
// API FUNCTIONS
// ============================================================================

/**
 * Upload et analyse un fichier CSV de télémétrie
 *
 * @param file - Fichier CSV à analyser
 * @param options - Optionnel : lapFilter = liste des numéros de tours à inclure
 * @returns Résultats de l'analyse complète
 * @throws ApiError en cas d'erreur
 */
export async function uploadAndAnalyzeCSV(
  file: File,
  options?: {
    lapFilter?: number[];
    track_condition?: string;
    track_temperature?: number | null;
    accessToken?: string | null;
  }
): Promise<AnalysisResult> {
  // Validation du fichier
  const validation = validateCSVFile(file);
  if (!validation.valid) {
    throw {
      success: false,
      error: "validation",
      message: validation.error || "Erreur de validation",
    } as ApiError;
  }

  // Créer FormData
  const formData = new FormData();
  formData.append("file", file);
  if (options?.lapFilter && options.lapFilter.length > 0) {
    formData.append("lap_filter", JSON.stringify(options.lapFilter));
  }
  const cond = options?.track_condition && ["dry", "damp", "wet", "rain"].includes(options.track_condition)
    ? options.track_condition
    : "dry";
  formData.append("track_condition", cond);
  if (options?.track_temperature != null && Number.isFinite(options.track_temperature)) {
    formData.append("track_temperature", String(options.track_temperature));
  }

  // Créer controller avec timeout
  const controller = createTimeoutController(API_TIMEOUT_MS);

  const headers: Record<string, string> = {};
  if (options?.accessToken) {
    headers["Authorization"] = `Bearer ${options.accessToken}`;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/analyze`, {
      method: "POST",
      body: formData,
      signal: controller.signal,
      headers: Object.keys(headers).length ? headers : undefined,
    });

    // Gérer erreurs HTTP
    if (!response.ok) {
      let errorData: ApiError;

      try {
        const errorJson = await parseJSONResponse<{ detail?: ApiError } & ApiError>(response);
        const d = errorJson.detail ?? errorJson;
        errorData = {
          success: false,
          error: d.error || "http_error",
          message: d.message || `Erreur HTTP ${response.status}`,
          details: d.details,
        };
      } catch {
        // Si pas de JSON, créer erreur générique
        errorData = {
          success: false,
          error: "http_error",
          message: `Erreur serveur (${response.status}): ${response.statusText}`,
        };
      }

      throw errorData;
    }

    // Parser réponse JSON
    const result = await parseJSONResponse<AnalysisResult>(response);

    // Normaliser les clés backend (corner_type, apex_distance_error, time_lost)
    if (Array.isArray(result.corner_analysis)) {
      result.corner_analysis = result.corner_analysis.map((c) => mapCornerData(c as Record<string, unknown>));
    }
    if (Array.isArray(result.coaching_advice)) {
      result.coaching_advice = result.coaching_advice.map((a) => mapAdviceData(a as Record<string, unknown>));
    }

    // Vérifier que la réponse contient success: true
    if (!result.success) {
      throw {
        success: false,
        error: "analysis_failed",
        message: "L'analyse a échoué. Vérifiez que le fichier CSV est valide.",
      } as ApiError;
    }

    return result;
  } catch (error) {
    // Si c'est déjà une ApiError, la relancer
    if (error && typeof error === "object" && "success" in error && error.success === false) {
      throw error;
    }

    // Sinon, gérer comme erreur fetch
    throw handleFetchError(error, "l'upload et l'analyse du CSV");
  }
}

/**
 * Parse un fichier CSV et retourne la liste des tours détectés (pour sélection avant analyse).
 *
 * @param file - Fichier CSV
 * @returns Liste des tours avec lap_number, lap_time_seconds, points_count, is_outlier
 */
export async function parseLaps(file: File): Promise<ParseLapsResponse> {
  const validation = validateCSVFile(file);
  if (!validation.valid) {
    throw {
      success: false,
      error: "validation",
      message: validation.error || "Erreur de validation",
    } as ApiError;
  }
  const formData = new FormData();
  formData.append("file", file);
  const controller = createTimeoutController(20000);
  const response = await fetch(`${API_BASE_URL}/api/v1/parse-laps`, {
    method: "POST",
    body: formData,
    signal: controller.signal,
  });
  if (!response.ok) {
    const err = await parseJSONResponse<ApiError>(response).catch(() => ({}));
    throw {
      success: false,
      error: err.error || "http_error",
      message: err.message || `Erreur ${response.status}`,
    } as ApiError;
  }
  const data = await parseJSONResponse<ParseLapsResponse>(response);
  if (!data.success || !Array.isArray(data.laps)) {
    throw { success: false, error: "invalid_response", message: "Réponse parse-laps invalide" } as ApiError;
  }
  return data;
}

/**
 * Récupère le statut d'une analyse
 *
 * @param analysisId - ID de l'analyse
 * @returns Statut de l'analyse
 * @throws ApiError en cas d'erreur
 */
export async function getAnalysisStatus(analysisId: string): Promise<AnalysisStatus> {
  if (!analysisId || analysisId.trim() === "") {
    throw {
      success: false,
      error: "validation",
      message: "ID d'analyse invalide",
    } as ApiError;
  }

  const controller = createTimeoutController(10000); // 10s pour status

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/status/${analysisId}`, {
      method: "GET",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      throw {
        success: false,
        error: "http_error",
        message: `Erreur lors de la récupération du statut (${response.status})`,
      } as ApiError;
    }

    return await parseJSONResponse<AnalysisStatus>(response);
  } catch (error) {
    if (error && typeof error === "object" && "success" in error && error.success === false) {
      throw error;
    }
    throw handleFetchError(error, "la récupération du statut");
  }
}

/**
 * Vérifie si le backend est accessible et opérationnel
 *
 * @returns Statut de santé du backend
 * @throws ApiError si le backend n'est pas accessible
 */
export async function getBackendHealth(): Promise<BackendHealth> {
  const controller = createTimeoutController(5000); // 5s pour health check

  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      method: "GET",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      throw {
        success: false,
        error: "http_error",
        message: `Backend non disponible (${response.status})`,
      } as ApiError;
    }

    return await parseJSONResponse<BackendHealth>(response);
  } catch (error) {
    if (error && typeof error === "object" && "success" in error && error.success === false) {
      throw error;
    }
    throw handleFetchError(error, "la vérification de santé du backend");
  }
}

/**
 * Vérifie la connectivité au backend avant d'effectuer une analyse
 * Utile pour afficher un message d'erreur précoce à l'utilisateur
 */
export async function checkBackendConnection(): Promise<boolean> {
  try {
    await getBackendHealth();
    return true;
  } catch {
    return false;
  }
}

/** Clés price_id acceptées par le backend Stripe */
export type StripePriceId =
  | "racer_monthly"
  | "racer_annual"
  | "team_monthly"
  | "team_annual";

export interface CreateCheckoutSessionResponse {
  checkout_url: string;
}

/**
 * Crée une session Stripe Checkout pour abonnement.
 * Rediriger l'utilisateur vers checkout_url après appel réussi.
 */
export async function createCheckoutSession(
  userId: string,
  priceId: StripePriceId
): Promise<CreateCheckoutSessionResponse> {
  const controller = createTimeoutController(15000);
  const response = await fetch(`${API_BASE_URL}/api/stripe/create-checkout-session`, {
    method: "POST",
    signal: controller.signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, price_id: priceId }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const message =
      (data?.message as string) || (data?.detail?.message as string) || `Erreur ${response.status}`;
    throw new Error(message);
  }
  return parseJSONResponse<CreateCheckoutSessionResponse>(response);
}

export interface CreatePortalSessionResponse {
  portal_url: string;
}

/**
 * Crée une session Stripe Customer Portal pour gérer l'abonnement.
 * Rediriger l'utilisateur vers portal_url après appel réussi.
 */
export async function createPortalSession(userId: string): Promise<CreatePortalSessionResponse> {
  const controller = createTimeoutController(15000);
  const response = await fetch(`${API_BASE_URL}/api/stripe/create-portal-session`, {
    method: "POST",
    signal: controller.signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const message =
      (data?.message as string) || (data?.detail?.message as string) || `Erreur ${response.status}`;
    throw new Error(message);
  }
  return parseJSONResponse<CreatePortalSessionResponse>(response);
}

// ============================================================================
// EXPORTS
// ============================================================================

export default {
  uploadAndAnalyzeCSV,
  getAnalysisStatus,
  getBackendHealth,
  checkBackendConnection,
  API_BASE_URL,
};
