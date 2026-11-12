import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api, useApi } from "../api";
import { Level, Meters } from "../components";
import { formatDay, formatScore, scoreTone } from "../format";
import type { Session } from "../types";

export function Interview() {
  const { id = "" } = useParams();
  const { data, error, loading, setData } = useApi<Session>(id ? `/api/sessions/${id}` : null);
  const [draft, setDraft] = useState("");
  const [voice, setVoice] = useState(false);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [data?.messages.length]);

  async function send() {
    if (!draft.trim() || busy) return;
    setBusy(true);
    setFormError(null);
    try {
      const next = await api<Session>(`/api/sessions/${id}/turn`, {
        method: "POST",
        body: JSON.stringify({ content: draft, modality: voice ? "voice" : "text" }),
      });
      setData(next);
      setDraft("");
    } catch (reason) {
      setFormError(reason instanceof Error ? reason.message : "发送失败");
    } finally {
      setBusy(false);
    }
  }

  async function finish() {
    setBusy(true);
    setFormError(null);
    try {
      const next = await api<Session>(`/api/sessions/${id}/finish`, { method: "POST" });
      setData(next);
    } catch (reason) {
      setFormError(reason instanceof Error ? reason.message : "评分失败");
    } finally {
      setBusy(false);
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void send();
    }
  }

  if (loading && !data) return <p className="muted">正在进入面试…</p>;
  if (error) return <div className="banner bad">{error}</div>;
  if (!data) return null;

  const ended = data.status === "finished";
  const ready = data.status === "ready";
  const step = ready || ended ? data.queue.length : Math.min(data.queue.length, data.cursor_idx + 1);
  const who = data.style === "strict" ? "严格面试官" : "宽松面试官";

  return (
    <section>
      <header className="page-head">
        <div>
          <p className="muted">{data.project ? <Link to={`/projects/${data.project.id}`}>{data.project.name}</Link> : "面试"}</p>
          <h1>{data.mode === "review" ? "针对性复习" : "模拟面试"}</h1>
          <p className="muted">{who} · {data.llm ? "模型追问" : "内置追问"} · 第 {step}/{data.queue.length} 题</p>
        </div>
      </header>
      {formError ? <div className="banner bad">{formError}</div> : null}
      <div className="interview">
        <div className="card">
          <div className="transcript">
            {data.messages.map((message) => (
              <article key={message.id} className={`bubble ${message.role === "candidate" ? "candidate" : "interviewer"}`}>
                <span className="who">
                  {message.role === "candidate" ? (message.modality === "voice" ? "你 · 转写" : "你") : who}
                </span>
                {message.content}
              </article>
            ))}
            <div ref={bottom} />
          </div>
          {ended && data.report ? <ReportView report={data.report} /> : null}
          {!ended ? (
            <div className="composer">
              {ready ? <div className="banner good">问题问完了。结束并评分后，掌握度会写进对应知识点。</div> : null}
              {!ready ? (
                <>
                  <textarea
                    data-testid="interview-input"
                    value={draft}
                    placeholder="写下你的回答。Enter 发送，Shift+Enter 换行。"
                    onChange={(event) => setDraft(event.target.value)}
                    onKeyDown={onKeyDown}
                  />
                  <label className="check">
                    <input type="checkbox" checked={voice} onChange={(event) => setVoice(event.target.checked)} />
                    这段是转写文本，按语音回答记录。麦克风还没接上。
                  </label>
                </>
              ) : null}
              <div className="row">
                {!ready ? (
                  <button type="button" className="primary" disabled={busy} data-testid="interview-send" onClick={() => void send()}>
                    发送
                  </button>
                ) : null}
                {!ready && data.current_point?.outline ? (
                  <button type="button" className="ghost" onClick={() => setDraft(data.current_point?.outline ?? "")}>
                    插入示范要点
                  </button>
                ) : null}
                <button type="button" className="ghost" disabled={busy} data-testid="interview-finish" onClick={() => void finish()}>
                  结束并评分
                </button>
              </div>
            </div>
          ) : (
            <div className="row" style={{ marginTop: 12 }}>
              <Link className="primary" to="/" style={{ textDecoration: "none" }}>回总览</Link>
              <Link className="ghost" to="/review" style={{ textDecoration: "none" }}>看复习表</Link>
            </div>
          )}
        </div>
        <aside className="card side">
          <h2>本轮题目</h2>
          <div className="list">
            {data.queue.map((point, index) => (
              <div key={point.id} className={point.id === data.current_point?.id && !ended ? "" : "muted"}>
                {index + 1}. {point.title}
              </div>
            ))}
          </div>
          {data.current_point && !ended ? (
            <>
              <h3 style={{ marginTop: 16 }}>当前话题</h3>
              <p>{data.current_point.title}</p>
            </>
          ) : null}
        </aside>
      </div>
    </section>
  );
}

function ReportView({ report }: { report: NonNullable<Session["report"]> }) {
  if (!report.averages) {
    return <div className="banner">还没有作答，未更新掌握度。</div>;
  }
  return (
    <div style={{ marginTop: 16 }}>
      <h2>本轮 {formatScore(report.averages.overall)}</h2>
      <Meters score={report.averages} />
      <div className="list" style={{ marginTop: 12 }}>
        {report.by_point.map((point) => (
          <article className="point" key={point.knowledge_id}>
            <div className="spread">
              <strong>{point.title}</strong>
              <span className={scoreTone(point.overall)}>{formatScore(point.overall)}</span>
            </div>
            {point.mastery ? (
              <p>
                <Level level={point.mastery.level} /> 掌握度 {formatScore(point.mastery.score)} · 下次 {formatDay(point.mastery.next_review_at)}
              </p>
            ) : null}
            {point.wrong ? <p>偏差：{point.wrong}</p> : null}
            {point.missing ? <p>缺口：{point.missing}</p> : null}
            {point.better ? (
              <details>
                <summary>更好的答法</summary>
                <p style={{ marginTop: 6 }}>{point.better}</p>
              </details>
            ) : null}
          </article>
        ))}
      </div>
    </div>
  );
}
