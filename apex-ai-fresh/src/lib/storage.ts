/**
 * Apex AI - Local Storage System
 * Système de stockage local pour les résultats d'analyse
 * Utilise localStorage du navigateur pour persister les analyses
 */

import type { AnalysisResult } from "./api";

// ============================================================================
// TYPES
// ============================================================================

export interface AnalysisSummary {
  id: string;
  date: string;
  timestamp: number;
  score: number;
  corner_count: number;
  lap_time: number;
  grade: string;
  filename?: string;
}

interface StoredAnalysis {
  id: string;
  timestamp: number;
  result: AnalysisResult;
}

// ============================================================================
// CONSTANTS
// ============================================================================

const STORAGE_INDEX_PREFIX = "apex_analyses_index_";
const STORAGE_ITEM_PREFIX = "apex_analysis_";
const STORAGE_GUEST = "guest";
const MAX_STORED_ANALYSES = 20; // Limite d'analyses dans localStorage

// ============================================================================
// UTILITIES
// ============================================================================

/**
 * Suffix de clé localStorage : user id ou "guest" si non connecté
 */
function getStorageSuffix(userId: string | null | undefined): string {
  return (userId && typeof userId === "string" && userId.trim()) ? userId.trim() : STORAGE_GUEST;
}

function getIndexKey(suffix: string): string {
  return `${STORAGE_INDEX_PREFIX}${suffix}`;
}

function getItemKey(suffix: string, id: string): string {
  return `${STORAGE_ITEM_PREFIX}${suffix}_${id}`;
}

/**
 * Génère un ID unique pour une analyse
 */
function generateAnalysisId(): string {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 9);
  return `${timestamp}_${random}`;
}

/**
 * Récupère l'index des analyses depuis localStorage (pour un utilisateur donné)
 */
function getAnalysesIndex(suffix: string): string[] {
  try {
    const indexJson = localStorage.getItem(getIndexKey(suffix));
    if (!indexJson) return [];
    return JSON.parse(indexJson) as string[];
  } catch (error) {
    console.error("Error reading analyses index:", error);
    return [];
  }
}

/**
 * Sauvegarde l'index des analyses dans localStorage
 */
function saveAnalysesIndex(index: string[], suffix: string): void {
  try {
    localStorage.setItem(getIndexKey(suffix), JSON.stringify(index));
  } catch (error) {
    console.error("Error saving analyses index:", error);
  }
}

/**
 * Nettoie les anciennes analyses si on dépasse la limite
 */
function cleanupOldAnalyses(suffix: string): void {
  try {
    const index = getAnalysesIndex(suffix);

    if (index.length <= MAX_STORED_ANALYSES) {
      return;
    }

    const prefix = `${STORAGE_ITEM_PREFIX}${suffix}_`;
    const analysesWithTimestamps = index.map((id) => {
      const stored = localStorage.getItem(prefix + id);
      if (!stored) return { id, timestamp: 0 };

      try {
        const data = JSON.parse(stored) as StoredAnalysis;
        return { id, timestamp: data.timestamp };
      } catch {
        return { id, timestamp: 0 };
      }
    });

    analysesWithTimestamps.sort((a, b) => a.timestamp - b.timestamp);

    const toRemove = analysesWithTimestamps.slice(0, index.length - MAX_STORED_ANALYSES);

    for (const item of toRemove) {
      localStorage.removeItem(prefix + item.id);
    }

    const newIndex = analysesWithTimestamps
      .slice(index.length - MAX_STORED_ANALYSES)
      .map((item) => item.id);

    saveAnalysesIndex(newIndex, suffix);
  } catch (error) {
    console.error("Error cleaning up old analyses:", error);
  }
}

/**
 * Vérifie si localStorage est disponible
 */
function isLocalStorageAvailable(): boolean {
  try {
    const test = "__localStorage_test__";
    localStorage.setItem(test, test);
    localStorage.removeItem(test);
    return true;
  } catch {
    return false;
  }
}

// ============================================================================
// STORAGE FUNCTIONS
// ============================================================================

/**
 * Sauvegarde un résultat d'analyse (isolé par compte : analyses_${userId} ou guest)
 *
 * @param result - Résultat de l'analyse à sauvegarder
 * @param userId - ID de l'utilisateur connecté (null/undefined = guest)
 * @returns ID unique de l'analyse sauvegardée
 */
export async function saveAnalysis(result: AnalysisResult, userId?: string | null): Promise<string> {
  if (!isLocalStorageAvailable()) {
    throw new Error("localStorage n'est pas disponible dans ce navigateur");
  }

  const suffix = getStorageSuffix(userId);

  try {
    const analysisId = result.analysis_id || generateAnalysisId();
    const timestamp = Date.now();

    const stored: StoredAnalysis = {
      id: analysisId,
      timestamp,
      result: {
        ...result,
        analysis_id: analysisId,
      },
    };

    const storageKey = getItemKey(suffix, analysisId);
    localStorage.setItem(storageKey, JSON.stringify(stored));

    const index = getAnalysesIndex(suffix);
    if (!index.includes(analysisId)) {
      index.push(analysisId);
      saveAnalysesIndex(index, suffix);
    }

    cleanupOldAnalyses(suffix);

    return analysisId;
  } catch (error) {
    console.error("Error saving analysis:", error);
    throw new Error(
      `Erreur lors de la sauvegarde: ${error instanceof Error ? error.message : "Erreur inconnue"}`
    );
  }
}

/**
 * Récupère toutes les analyses sauvegardées pour l'utilisateur courant (résumés)
 *
 * @param userId - ID de l'utilisateur connecté (null/undefined = guest)
 * @returns Tableau des résumés d'analyses, trié par date (plus récent en premier)
 */
export async function getAllAnalyses(userId?: string | null): Promise<AnalysisSummary[]> {
  if (!isLocalStorageAvailable()) {
    return [];
  }

  const suffix = getStorageSuffix(userId);

  try {
    const index = getAnalysesIndex(suffix);
    const summaries: AnalysisSummary[] = [];
    const prefix = `${STORAGE_ITEM_PREFIX}${suffix}_`;

    for (const id of index) {
      try {
        const storedJson = localStorage.getItem(prefix + id);
        if (!storedJson) continue;

        const stored = JSON.parse(storedJson) as StoredAnalysis;
        const result = stored.result;

        summaries.push({
          id: stored.id,
          date: new Date(stored.timestamp).toISOString(),
          timestamp: stored.timestamp,
          score: Math.round(result.performance_score.overall_score),
          corner_count: result.corners_detected,
          lap_time: result.lap_time,
          grade: result.performance_score.grade,
          filename: result.analysis_id ? `${result.analysis_id}.json` : undefined,
        });
      } catch (error) {
        console.warn(`Error reading analysis ${id}:`, error);
      }
    }

    summaries.sort((a, b) => b.timestamp - a.timestamp);

    return summaries;
  } catch (error) {
    console.error("Error getting all analyses:", error);
    return [];
  }
}

/**
 * Récupère une analyse complète par son ID (pour l'utilisateur courant)
 *
 * @param id - ID de l'analyse
 * @param userId - ID de l'utilisateur connecté (null/undefined = guest)
 * @returns Résultat complet de l'analyse ou null si non trouvé
 */
export async function getAnalysisById(id: string, userId?: string | null): Promise<AnalysisResult | null> {
  if (!isLocalStorageAvailable()) {
    return null;
  }

  if (!id || id.trim() === "") {
    return null;
  }

  const suffix = getStorageSuffix(userId);

  try {
    const storageKey = getItemKey(suffix, id);
    const storedJson = localStorage.getItem(storageKey);

    if (!storedJson) {
      return null;
    }

    const stored = JSON.parse(storedJson) as StoredAnalysis;
    return stored.result;
  } catch (error) {
    console.error(`Error getting analysis ${id}:`, error);
    return null;
  }
}

/**
 * Supprime une analyse (pour l'utilisateur courant)
 *
 * @param id - ID de l'analyse à supprimer
 * @param userId - ID de l'utilisateur connecté (null/undefined = guest)
 * @returns true si la suppression a réussi, false sinon
 */
export async function deleteAnalysis(id: string, userId?: string | null): Promise<boolean> {
  if (!isLocalStorageAvailable()) {
    return false;
  }

  if (!id || id.trim() === "") {
    return false;
  }

  const suffix = getStorageSuffix(userId);

  try {
    const storageKey = getItemKey(suffix, id);

    if (!localStorage.getItem(storageKey)) {
      return false;
    }

    localStorage.removeItem(storageKey);

    const index = getAnalysesIndex(suffix);
    const newIndex = index.filter((analysisId) => analysisId !== id);
    saveAnalysesIndex(newIndex, suffix);

    return true;
  } catch (error) {
    console.error(`Error deleting analysis ${id}:`, error);
    return false;
  }
}

/**
 * Exporte une analyse en tant que Blob JSON téléchargeable
 *
 * @param id - ID de l'analyse à exporter
 * @param userId - ID de l'utilisateur connecté (null/undefined = guest)
 * @returns Blob contenant le JSON de l'analyse
 */
export async function exportAnalysisAsJSON(id: string, userId?: string | null): Promise<Blob> {
  const analysis = await getAnalysisById(id, userId);

  if (!analysis) {
    throw new Error(`Analyse non trouvée: ${id}`);
  }

  try {
    const jsonString = JSON.stringify(analysis, null, 2);
    const blob = new Blob([jsonString], { type: "application/json" });
    return blob;
  } catch (error) {
    console.error(`Error exporting analysis ${id}:`, error);
    throw new Error(
      `Erreur lors de l'export: ${error instanceof Error ? error.message : "Erreur inconnue"}`
    );
  }
}

/**
 * Télécharge une analyse en tant que fichier JSON
 *
 * @param id - ID de l'analyse à télécharger
 * @param filename - Nom du fichier (optionnel, par défaut: apex-analysis-{id}.json)
 * @param userId - ID de l'utilisateur connecté (null/undefined = guest)
 */
export async function downloadAnalysis(id: string, filename?: string, userId?: string | null): Promise<void> {
  try {
    const blob = await exportAnalysisAsJSON(id, userId);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || `apex-analysis-${id}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (error) {
    console.error(`Error downloading analysis ${id}:`, error);
    throw error;
  }
}

/**
 * Récupère le nombre d'analyses sauvegardées pour l'utilisateur courant
 *
 * @param userId - ID de l'utilisateur connecté (null/undefined = guest)
 * @returns Nombre d'analyses dans le stockage
 */
export async function getAnalysesCount(userId?: string | null): Promise<number> {
  if (!isLocalStorageAvailable()) {
    return 0;
  }

  const suffix = getStorageSuffix(userId);

  try {
    const index = getAnalysesIndex(suffix);
    return index.length;
  } catch (error) {
    console.error("Error getting analyses count:", error);
    return 0;
  }
}

/**
 * Vide toutes les analyses sauvegardées pour l'utilisateur courant (pas le localStorage global)
 *
 * @param userId - ID de l'utilisateur connecté (null/undefined = guest)
 * @returns Nombre d'analyses supprimées
 */
export async function clearAllAnalyses(userId?: string | null): Promise<number> {
  if (!isLocalStorageAvailable()) {
    return 0;
  }

  const suffix = getStorageSuffix(userId);

  try {
    const index = getAnalysesIndex(suffix);
    let deletedCount = 0;
    const prefix = `${STORAGE_ITEM_PREFIX}${suffix}_`;

    for (const id of index) {
      try {
        localStorage.removeItem(prefix + id);
        deletedCount++;
      } catch (error) {
        console.warn(`Error deleting analysis ${id}:`, error);
      }
    }

    localStorage.removeItem(getIndexKey(suffix));

    return deletedCount;
  } catch (error) {
    console.error("Error clearing all analyses:", error);
    return 0;
  }
}

/**
 * Vérifie si une analyse existe pour l'utilisateur courant
 *
 * @param id - ID de l'analyse
 * @param userId - ID de l'utilisateur connecté (null/undefined = guest)
 * @returns true si l'analyse existe, false sinon
 */
export async function analysisExists(id: string, userId?: string | null): Promise<boolean> {
  if (!isLocalStorageAvailable() || !id || id.trim() === "") {
    return false;
  }

  const suffix = getStorageSuffix(userId);

  try {
    const storageKey = getItemKey(suffix, id);
    return localStorage.getItem(storageKey) !== null;
  } catch (error) {
    console.error(`Error checking if analysis ${id} exists:`, error);
    return false;
  }
}

// ============================================================================
// EXPORTS
// ============================================================================

export default {
  saveAnalysis,
  getAllAnalyses,
  getAnalysisById,
  deleteAnalysis,
  exportAnalysisAsJSON,
  downloadAnalysis,
  getAnalysesCount,
  clearAllAnalyses,
  analysisExists,
};
