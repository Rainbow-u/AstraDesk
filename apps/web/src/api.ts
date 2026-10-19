// 前端 API 客户端：只经 /api/v1 访问后端，不持有任何模型密钥（AGENTS.md 约定7）。

export interface Detection {
  id: string;
  class_id: number;
  class_name: string;
  confidence: number | null;
  bbox_image: [number, number, number, number];
  source?: string | null; // 检测来源(yolov10:*/yolo-world/manual/mock)，FR03 可追溯
  raw_class_name?: string | null; // 开放词表映射前原始提示词名(如 lamp/speaker)，FR03 原始类可追溯
}

// interpret 任务结果：确定性几何事实 + 模板中文描述（VL 增强 B 阶段 blocked）。
export interface SceneDimension {
  key: string;
  weight: number;
  text: string;
}

// 物体确定性属性（Phase 4 阶段 B）：颜色需原图（否则 unknown）+ bbox 几何派生 + 语义预留（恒 blocked）。
export interface ColorAttr {
  name: string; // 12 基本色中文名或 "unknown"
  rgb: [number, number, number] | null;
  hsv: [number, number, number] | null;
}

export interface SemanticAttr {
  status: "blocked" | "available";
  material: string | null;
  open_state: string | null;
  fill_level: string | null;
  precise_orientation: string | null;
}

export interface ObjectAttributes {
  color: ColorAttr;
  aspect_ratio: number;
  orientation: "landscape" | "square" | "portrait";
  size_class: "small" | "medium" | "large";
  semantic: SemanticAttr;
}

export interface SceneObjectFact {
  object_id: string;
  class_id?: number;
  class_name: string;
  center: [number, number];
  area: number;
  zone_depth: string;
  zone_lateral: string;
  fixed: boolean;
  high_frequency: boolean;
  source?: string | null;
  attributes: ObjectAttributes;
}

export interface SceneFacts {
  object_count?: number;
  objects?: SceneObjectFact[];
  [k: string]: unknown;
}

export interface SceneDescription {
  render_version: string;
  mode: string;
  user_side: string;
  summary: string;
  dimensions: SceneDimension[];
  h07_note: string | null;
  warnings: string[];
  text: string;
}

export interface InterpretResult extends JobResult {
  count?: number;
  desk_bbox_image?: [number, number, number, number]; // 事实推导所用桌面矩形（约定3 可追溯）
  desk_assumed_full_image?: boolean; // 未标定桌面时为 true（全图当桌面）
  scene_facts?: SceneFacts;
  description?: SceneDescription;
  vl?: { enabled: boolean; reason?: string };
}

export interface JobResult {
  model_name?: string;
  model_version?: string;
  run_mode?: "real" | "mock";
  device?: string;
  elapsed_seconds?: number;
  image_width?: number;
  image_height?: number;
  count?: number;
}

export interface ErrorBody {
  code: string;
  message: string;
  details?: unknown;
  retryable: boolean;
  request_id: string;
}

export interface Job {
  id: string;
  project_id: string;
  type: string;
  status: "queued" | "running" | "succeeded" | "partial" | "failed" | "cancelled";
  stage: string | null;
  attempt: number;
  result: JobResult | null;
  detections: Detection[];
  error: ErrorBody | null;
}

export interface Capabilities {
  run_mode: "real" | "mock";
  detector: { available: boolean; model_name: string; model_version: string };
  features: string[];
  open_vocab?: {
    enabled: boolean;
    available: boolean;
    model_name?: string;
    fusion_iou?: number;
  } | null;
}

const BASE = "/api/v1";

async function handle<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let body: ErrorBody | null = null;
    try {
      body = (await resp.json()) as ErrorBody;
    } catch {
      /* ignore */
    }
    const msg = body ? `${body.code}: ${body.message}` : `HTTP ${resp.status}`;
    throw new Error(msg);
  }
  return (await resp.json()) as T;
}

export function getCapabilities(): Promise<Capabilities> {
  return fetch(`${BASE}/capabilities`).then((r) => handle<Capabilities>(r));
}

export function createProject(title: string): Promise<{ id: string }> {
  return fetch(`${BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  }).then((r) => handle<{ id: string }>(r));
}

export interface UploadOut {
  project_id: string;
  image_asset_id: string;
  thumbnail_asset_id?: string;
  canonical_width: number;
  canonical_height: number;
  sha256: string;
}

export function uploadImage(projectId: string, file: File): Promise<UploadOut> {
  const form = new FormData();
  form.append("file", file);
  return fetch(`${BASE}/projects/${projectId}/images`, { method: "POST", body: form }).then((r) =>
    handle<UploadOut>(r),
  );
}

export function createDetectJob(projectId: string, imageAssetId: string): Promise<Job> {
  return fetch(`${BASE}/projects/${projectId}/jobs/detect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image_asset_id: imageAssetId }),
  }).then((r) => handle<Job>(r));
}

export interface InterpretJobIn {
  detect_job_id?: string;
  desk_bbox_image?: [number, number, number, number];
  user_side?: "bottom" | "top" | "left" | "right";
  handedness?: "left" | "right";
  mode?: "study" | "office" | "minimal";
}

export function createInterpretJob(projectId: string, payload: InterpretJobIn): Promise<Job> {
  return fetch(`${BASE}/projects/${projectId}/jobs/interpret`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then((r) => handle<Job>(r));
}

export function getJob(jobId: string): Promise<Job> {
  return fetch(`${BASE}/jobs/${jobId}`).then((r) => handle<Job>(r));
}

export function assetUrl(assetId: string): string {
  return `${BASE}/assets/${assetId}`;
}

const TERMINAL = new Set(["succeeded", "failed", "cancelled", "partial"]);

export async function pollJob(jobId: string, intervalMs = 800, maxTries = 60): Promise<Job> {
  let job = await getJob(jobId);
  for (let i = 0; i < maxTries && !TERMINAL.has(job.status); i++) {
    await new Promise((res) => setTimeout(res, intervalMs));
    job = await getJob(jobId);
  }
  return job;
}
