const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface AnalysisResponse {
  success: boolean;
  analysis_id: string;
  timestamp: string;
  corners_detected: number;
  lap_time: number;
  performance_score: {
    overall_score: number;
    grade: string;
    breakdown: {
      apex_precision: number;
      trajectory_consistency: number;
      apex_speed: number;
      sector_times: number;
    };
    percentile: number;
  };
  corner_analysis: Array<{
    corner_id: number;
    corner_number: number;
    corner_type: string;
    apex_speed_real: number;
    apex_speed_optimal: number;
    speed_efficiency: number;
    apex_distance_error: number;
    apex_direction_error: string;
    lateral_g_max: number;
    time_lost: number;
    grade: string;
    score: number;
  }>;
  coaching_advice: Array<{
    priority: number;
    category: string;
    impact_seconds: number;
    corner?: number;
    message: string;
    explanation: string;
    difficulty: string;
  }>;
  plots: {
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
  };
  statistics: {
    processing_time_seconds: number;
    data_points: number;
    best_corners: number[];
    worst_corners: number[];
    avg_apex_distance: number;
    avg_apex_speed_efficiency: number;
  };
}

export async function analyzeTelemetry(file: File): Promise<AnalysisResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/v1/analyze`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      message: "Erreur lors de l'analyse",
    }));
    throw new Error(error.message || `HTTP ${response.status}`);
  }

  return response.json();
}
