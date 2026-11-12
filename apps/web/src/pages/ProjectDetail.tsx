import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, useApi } from "../api";
import { KnowledgeGraph, Level } from "../components";
import { formatScore, scoreTone } from "../format";
import type { ProjectDetail as Project, Session } from "../types";

export function ProjectDetail() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const { data, error, loading, reload } = useApi<Project>(id ? `/api/projects/${id}` : null);
  const [style, setStyle] = useState<"strict" | "loose">("loose");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Array<{ id: string; title: string; summary: string }>>([]);

  async function start(mode: "mock" | "review", knowledgeIds?: string[]) {
    setBusy(true);
    setMessage(null);
    try {
      const session = await api<Session>("/api/sessions", {
        method: "POST",
        body: JSON.stringify({ project_id: id, style, mode, knowledge_ids: knowledgeIds ?? [] }),
      });
      navigate(`/interview/${session.id}`);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "没能开始");
      setBusy(false);
    }
  }

  async function collect() {
    setBusy(true);
    setMessage(null);
    try {
      const result = await api<{ message: string }>(`/api/projects/${id}/collect`, { method: "POST" });
      setMessage(result.message);
      reload();
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "补齐失败");
    } finally {
      setBusy(false);
    }
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const input = event.currentTarget.elements.namedItem("file");
    if (!(input instanceof HTMLInputElement) || !input.files?.[0]) return;
    const body = new FormData();
    body.set("project_id", id);
    body.set("file", input.files[0]);
    setBusy(true);
    setMessage(null);
    try {
      const result = await api<{ count: number }>("/api/ingest", { method: "POST", body });
      setMessage(`已写入 ${result.count} 条知识点。`);
      event.currentTarget.reset();
      reload();
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "导入失败");
    } finally {
      setBusy(false);
    }
  }

  async function search(value: string) {
    setQuery(value);
    if (!value.trim()) {
      setHits([]);
      return;
    }
    const result = await api<{ items: Array<{ id: string; title: string; summary: string }> }>(
      `/api/knowledge?q=${encodeURIComponent(value)}&project_id=${encodeURIComponent(id)}&unlinked=1`,
    );
    setHits(result.items.slice(0, 6));
  }

  async function link(knowledgeId: string) {
    await api(`/api/projects/${id}/link`, { method: "POST", body: JSON.stringify({ knowledge_id: knowledgeId }) });
    setHits((current) => current.filter((item) => item.id !== knowledgeId));
    reload();
  }

  async function remove() {
    if (!data || !confirm(`删除项目「${data.name}」？知识点本身会留下来。`)) return;
    await api(`/api/projects/${id}`, { method: "DELETE" });
    navigate("/projects");
  }

  if (loading && !data) return <p className="muted">正在读取项目…</p>;
  if (error) return <div className="banner bad">{error}</div>;
  if (!data) return null;

  return (
    <section>
      <header className="page-head">
        <div>
          <p className="muted"><Link to="/projects">项目</Link></p>
          <h1>{data.name}</h1>
          <p className="lede">{data.description}</p>
        </div>
        <button type="button" className="ghost danger" onClick={() => void remove()}>删除项目</button>
      </header>
      {message ? <div className="banner">{message}</div> : null}

      <div className="split">
        <section className="card">
          <h2>模拟面试</h2>
          <div className="filters">
            <button type="button" className="ghost" aria-pressed={style === "loose"} onClick={() => setStyle("loose")}>宽松</button>
            <button type="button" className="ghost" aria-pressed={style === "strict"} onClick={() => setStyle("strict")}>严格</button>
          </div>
          <p className="muted">本轮预计考察 {data.plan.points.length} 个尚未掌握的知识点。已掌握的点会跳过。</p>
          <div className="list" style={{ margin: "10px 0" }}>
            {data.plan.points.map((point) => (
              <div key={point.id}>{point.title} · {point.reason}</div>
            ))}
            {data.plan.points.length === 0 ? <p>没有可新考的点。到期项去今日复习。</p> : null}
          </div>
          {data.plan.skipped_mastered.length > 0 ? (
            <p className="muted">已跳过：{data.plan.skipped_mastered.map((point) => point.title).join("、")}</p>
          ) : null}
          <div className="row" style={{ marginTop: 12 }}>
            <button type="button" className="primary" disabled={busy} data-testid="start-interview" onClick={() => void start("mock")}>
              开始模拟面试
            </button>
            <button type="button" className="ghost" disabled={busy} onClick={() => void collect()}>按 JD 补齐知识点</button>
          </div>
          {data.jd_text ? (
            <details style={{ marginTop: 14 }}>
              <summary>岗位描述</summary>
              <p style={{ whiteSpace: "pre-wrap", marginTop: 8 }}>{data.jd_text}</p>
            </details>
          ) : null}
        </section>
        <section className="card">
          <h2>导入资料</h2>
          <p className="muted">支持 txt、md，以及带文字层的 pdf。仓库里有一份样例：data/vault/samples/sample-import.md</p>
          <form onSubmit={(event) => void upload(event)} style={{ marginTop: 10 }}>
            <input name="file" type="file" accept=".md,.txt,.pdf,text/plain,text/markdown,application/pdf" />
            <button className="ghost" type="submit" disabled={busy} style={{ marginTop: 8 }}>上传并抽取知识点</button>
          </form>
          <h3 style={{ marginTop: 16 }}>关联已有知识点</h3>
          <input value={query} placeholder="搜索标题、别名或关键词" onChange={(event) => void search(event.target.value)} />
          <div className="list" style={{ marginTop: 8 }}>
            {hits.map((hit) => (
              <div className="spread" key={hit.id}>
                <span>{hit.title}</span>
                <button type="button" className="texty" onClick={() => void link(hit.id)}>关联</button>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="card stack">
        <h2>知识点</h2>
        <div className="list">
          {data.knowledge.map((point) => {
            const mastered = point.level === "mastered" || point.level === "fluent";
            return (
              <article className="point" key={point.id}>
                <div className="spread">
                  <strong>{point.title}</strong>
                  <span className="row">
                    <Level level={point.level} />
                    <span className={scoreTone(point.score)}>{formatScore(point.score)}</span>
                  </span>
                </div>
                <p>{point.summary}</p>
                <div className="chips">
                  {point.chips.map((chip) => (
                    <span className="chip" key={`${chip.label}-${chip.id}`}>{chip.label} {chip.title}</span>
                  ))}
                </div>
                <button
                  type="button"
                  className="texty"
                  onClick={() => void start(mastered ? "review" : "mock", [point.id])}
                >
                  {mastered ? "复习这个" : "只练这个"}
                </button>
              </article>
            );
          })}
        </div>
      </section>

      <section className="card stack">
        <h2>关系</h2>
        <KnowledgeGraph projectId={id} />
      </section>
    </section>
  );
}
