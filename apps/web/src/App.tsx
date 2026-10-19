import { useEffect, useRef, useState } from "react";
import {
  Capabilities,
  Detection,
  InterpretResult,
  Job,
  SceneDescription,
  SceneObjectFact,
  assetUrl,
  createDetectJob,
  createInterpretJob,
  createProject,
  getCapabilities,
  pollJob,
  uploadImage,
} from "./api";

const BOX_COLORS = ["#ff5050", "#ffb020", "#3ecf8e", "#4aa3ff", "#c07bff", "#ff7ad9"];
const DIM_ZH: Record<string, string> = {
  continuous_workspace: "连续工作区",
  accessibility: "取用便利",
  grouping: "同类集中",
  alignment: "对齐有序",
  movement_saving: "减少移动",
};
// 几何属性中文（Phase 4 阶段 B）；semantic 为 blocked 时不展示相关字段。
const ORIENT_ZH: Record<string, string> = { landscape: "横放", square: "方形", portrait: "竖放" };
const SIZE_ZH: Record<string, string> = { small: "小号", medium: "中号", large: "大号" };

export default function App() {
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [busy, setBusy] = useState(false);
  const [imageUrl, setImageUrl] = useState<string>("");
  const [job, setJob] = useState<Job | null>(null);
  const [scene, setScene] = useState<SceneDescription | null>(null);
  const [sceneObjects, setSceneObjects] = useState<SceneObjectFact[]>([]);
  const [error, setError] = useState<string>("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getCapabilities().then(setCaps).catch((e) => setError(String(e.message || e)));
  }, []);

  const onPickFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    setJob(null);
    setScene(null);
    setSceneObjects([]);
    try {
      const proj = await createProject(file.name);
      const up = await uploadImage(proj.id, file);
      setImageUrl(assetUrl(up.image_asset_id));
      const created = await createDetectJob(proj.id, up.image_asset_id);
      const done = await pollJob(created.id);
      setJob(done);
      if (done.status === "failed" && done.error) {
        setError(`${done.error.code}: ${done.error.message}`);
      } else if (done.status === "succeeded" && caps?.features.includes("interpret")) {
        // 检测成功后触发确定性 facts + 模板 NL（VL 增强 B 阶段 blocked）。
        const interp = await createInterpretJob(proj.id, { detect_job_id: done.id });
        const interpDone = await pollJob(interp.id);
        if (interpDone.status === "succeeded" && interpDone.result) {
          const res = interpDone.result as InterpretResult;
          setScene(res.description ?? null);
          setSceneObjects(res.scene_facts?.objects ?? []);
        }
      }
    } catch (err) {
      setError(String((err as Error).message || err));
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const detections: Detection[] = job?.detections ?? [];

  return (
    <div className="page">
      <header>
        <h1>桌面智能整理 · 桌面识别</h1>
        <div className="caps">
          {caps ? (
            <span>
              运行模式 <b>{caps.run_mode}</b> · 检测器{" "}
              <b>
                {caps.detector.model_name}
                {caps.detector.available ? "" : "（不可用）"}
              </b>
              {caps.open_vocab ? (
                <>
                  {" "}· 开放词表 <b>{caps.open_vocab.enabled ? (caps.open_vocab.available ? "已启用" : "启用但不可用") : "已关闭"}</b>
                </>
              ) : null}
            </span>
          ) : (
            <span>加载能力中…</span>
          )}
        </div>
      </header>

      <div className="toolbar">
        <input ref={fileRef} type="file" accept="image/png,image/jpeg" onChange={onPickFile} disabled={busy} />
        {busy && <span className="hint">上传并检测中…</span>}
      </div>

      {error && <div className="error">{error}</div>}

      <div className="stage">
        {imageUrl ? (
          <div className="canvas">
            <img src={imageUrl} alt="上传的桌面" />
            {detections.map((d, i) => {
              const [x1, y1, x2, y2] = d.bbox_image;
              const color = BOX_COLORS[i % BOX_COLORS.length];
              return (
                <div
                  key={d.id}
                  className="box"
                  style={{
                    left: `${x1 * 100}%`,
                    top: `${y1 * 100}%`,
                    width: `${Math.max(x2 - x1, 0) * 100}%`,
                    height: `${Math.max(y2 - y1, 0) * 100}%`,
                    borderColor: color,
                  }}
                >
                  <span className="tag" style={{ background: color }}>
                    {d.class_name}
                    {d.confidence != null ? ` ${d.confidence.toFixed(2)}` : ""}
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="placeholder">选择一张桌面照片开始识别（JPEG/PNG，≤10MB）</div>
        )}

        <aside className="panel">
          <h2>检测结果</h2>
          {job?.result && (
            <p className="meta">
              {job.result.model_name} · {job.result.run_mode} · {job.result.count} 个 ·{" "}
              {job.result.elapsed_seconds?.toFixed(2)}s
            </p>
          )}
          {detections.length === 0 && !busy && <p className="hint">暂无结果</p>}
          <ul>
            {detections.map((d, i) => (
              <li key={d.id}>
                <i className="dot" style={{ background: BOX_COLORS[i % BOX_COLORS.length] }} />
                {d.class_name}
                {d.raw_class_name && d.raw_class_name !== d.class_name
                  ? <span className="raw">({d.raw_class_name})</span> : null}
                {d.source ? <span className="src">{d.source}</span> : null}
                <span className="conf">{d.confidence != null ? d.confidence.toFixed(2) : "—"}</span>
              </li>
            ))}
          </ul>

          {scene && (
            <section className="scene">
              <h2>场景描述</h2>
              <p className="summary">{scene.summary}</p>
              <ul className="dims">
                {scene.dimensions.map((dim) => (
                  <li key={dim.key}>
                    <b>
                      {DIM_ZH[dim.key] ?? dim.key}（权重 {dim.weight.toFixed(2)}）
                    </b>
                    ：{dim.text}
                  </li>
                ))}
              </ul>
              {scene.warnings.length > 0 && (
                <div className="warn">
                  {scene.warnings.map((w, i) => (
                    <p key={i}>{w}</p>
                  ))}
                </div>
              )}
              <details>
                <summary>完整描述文本</summary>
                <pre className="scene-text">{scene.text}</pre>
              </details>
            </section>
          )}

          {sceneObjects.length > 0 && (
            <section className="scene attrs">
              <h2>物体属性</h2>
              <ul>
                {sceneObjects.map((o) => {
                  const c = o.attributes.color;
                  const known = c.name !== "unknown" && c.rgb != null;
                  const sem = o.attributes.semantic;
                  return (
                    <li key={o.object_id}>
                      {known ? (
                        <i
                          className="swatch"
                          style={{ background: `rgb(${c.rgb![0]},${c.rgb![1]},${c.rgb![2]})` }}
                        />
                      ) : null}
                      <b>{o.class_name}</b>
                      <span className="attr">{known ? `${c.name}色` : "颜色未知"}</span>
                      <span className="attr">{ORIENT_ZH[o.attributes.orientation] ?? o.attributes.orientation}</span>
                      <span className="attr">{SIZE_ZH[o.attributes.size_class] ?? o.attributes.size_class}</span>
                      {sem.status === "available" && sem.material ? (
                        <span className="attr">{sem.material}</span>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
              <p className="hint">颜色为受光照影响的主色近似；语义属性（材质/开合/空满）暂未启用（blocked）。</p>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}
