import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, useApi } from "../api";
import { HistoryTable, Level } from "../components";
import { formatDay, formatScore, scoreTone } from "../format";
import type { DashboardData, MasteryRow, ProjectSummary } from "../types";

type Band = "all" | "strong" | "weak" | "today";
type SortKey = "title" | "score" | "next";

export function Dashboard() {
  const [projectId, setProjectId] = useState("");
  const [band, setBand] = useState<Band>("all");
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const projects = useApi<{ projects: ProjectSummary[] }>("/api/projects");
  const path = projectId ? `/api/dashboard?project_id=${encodeURIComponent(projectId)}` : "/api/dashboard";
  const { data, error, loading, reload } = useApi<DashboardData>(path);

  const rows = useMemo(() => {
    const source = data?.rows ?? [];
    const filtered = source.filter((row) => {
      if (band === "strong") return (row.score ?? -1) >= 75;
      if (band === "weak") return row.score == null || row.score < 60;
      if (band === "today") return row.practiced_today;
      return true;
    });
    const direction = order === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => direction * compare(a, b, sortKey));
  }, [data, band, sortKey, order]);

  function toggle(next: SortKey) {
    if (sortKey === next) setOrder((current) => (current === "asc" ? "desc" : "asc"));
    else {
      setSortKey(next);
      setOrder(next === "title" ? "asc" : "desc");
    }
  }

  async function dismiss(id: string) {
    await api(`/api/reminders/${id}/dismiss`, { method: "POST" });
    reload();
  }

  return (
    <section>
      <header className="page-head">
        <div>
          <h1>今天的练习</h1>
          <p className="muted lede">
            {data ? `今天 ${data.today} · ${data.timezone}` : "按上海时区计算今天。"}
            掌握度记在知识点上，在任一项目里掌握后，其他项目的模拟面试不再重复出题。
          </p>
        </div>
        <label className="field" style={{ margin: 0, minWidth: 180 }}>
          <span>项目范围</span>
          <select value={projectId} onChange={(event) => setProjectId(event.target.value)} data-testid="dashboard-project">
            <option value="">全部项目</option>
            {projects.data?.projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
      </header>
      {error ? <div className="banner bad">{error}</div> : null}
      {loading && !data ? <p className="muted">正在读取今天的记录…</p> : null}
      {data ? (
        <>
          <div className="stats">
            <article className="card stat">
              <span className="muted">今日掌握度</span>
              <strong data-testid="dashboard-mastery" className={scoreTone(data.mastery_today.average)}>
                {formatScore(data.mastery_today.average)}
              </strong>
              <p className="muted">{data.mastery_today.average == null ? "今天还没练习。练完一场会记到今天。" : "今天练过的知识点，当前掌握度均值。"}</p>
            </article>
            <article className="card stat">
              <span className="muted">今日练习量</span>
              <strong>{data.practice.answers}</strong>
              <p className="muted">
                {data.practice.sessions} 场 · {data.practice.points} 个知识点
              </p>
            </article>
            <article className="card stat">
              <span className="muted">全局掌握</span>
              <strong className={scoreTone(data.mastery_global.average)}>{formatScore(data.mastery_global.average)}</strong>
              <p className="dist">
                薄弱 {data.mastery_global.distribution.weak} · 熟悉中 {data.mastery_global.distribution.medium} · 已掌握{" "}
                {data.mastery_global.distribution.mastered} · 熟练 {data.mastery_global.distribution.fluent} · 未练习{" "}
                {data.mastery_global.unpracticed}
              </p>
            </article>
          </div>

          <div className="split">
            <section className="card">
              <div className="spread">
                <h2>掌握情况</h2>
                <Link to="/projects">去练习</Link>
              </div>
              <div className="filters">
                {(
                  [
                    ["all", "全部"],
                    ["strong", "优势 ≥75"],
                    ["weak", "薄弱 <60 / 未练"],
                    ["today", "今日练过"],
                  ] as const
                ).map(([key, label]) => (
                  <button key={key} type="button" className="ghost" aria-pressed={band === key} onClick={() => setBand(key)}>
                    {label}
                  </button>
                ))}
              </div>
              {rows.length === 0 ? <p className="muted">这个筛选下没有知识点。</p> : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th><button type="button" onClick={() => toggle("title")}>知识点{sortKey === "title" ? mark(order) : ""}</button></th>
                        <th>等级</th>
                        <th><button type="button" onClick={() => toggle("score")}>分数{sortKey === "score" ? mark(order) : ""}</button></th>
                        <th><button type="button" onClick={() => toggle("next")}>下次复习{sortKey === "next" ? mark(order) : ""}</button></th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => (
                        <tr key={row.id}>
                          <td>
                            {row.title}
                            <div className="chips">
                              {row.projects.map((project) => (
                                <span className="chip" key={project.id}>{project.name}</span>
                              ))}
                              {row.practiced_today ? <span className="chip">今日</span> : null}
                            </div>
                          </td>
                          <td><Level level={row.level} /></td>
                          <td className={scoreTone(row.score)}>{formatScore(row.score)}</td>
                          <td>{formatDay(row.next_review_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
            <section className="card">
              <h2>复习提醒</h2>
              {data.reminders.length === 0 ? <p className="muted">今天没有到点的提醒。</p> : (
                <div className="chat-list">
                  {data.reminders.map((reminder) => (
                    <article className="bubble interviewer" key={reminder.id}>
                      <span className="who">{reminder.title}</span>
                      {reminder.message}
                      <div>
                        <button type="button" className="texty" onClick={() => void dismiss(reminder.id)}>知道了</button>
                      </div>
                    </article>
                  ))}
                </div>
              )}
              <h2 style={{ marginTop: 18 }}>今日缺口</h2>
              {data.gaps.length === 0 ? <p className="muted">今天还没有记下缺口。</p> : (
                <div className="list">
                  {data.gaps.map((gap) => (
                    <div key={gap.id}>
                      <strong>{gap.title}</strong>
                      <span className={scoreTone(gap.overall)}> {formatScore(gap.overall)}</span>
                      <p className="muted">{gap.missing || gap.wrong}</p>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>

          <section className="card stack">
            <div className="spread">
              <h2>作答历史</h2>
              <Link to="/history">全部历史</Link>
            </div>
            <HistoryTable projectId={projectId || undefined} limit={12} />
          </section>
        </>
      ) : null}
    </section>
  );
}

function mark(order: "asc" | "desc") {
  return order === "asc" ? " ↑" : " ↓";
}

function compare(a: MasteryRow, b: MasteryRow, key: SortKey) {
  if (key === "title") return a.title.localeCompare(b.title, "zh");
  if (key === "next") return (a.next_review_at ?? "9999").localeCompare(b.next_review_at ?? "9999");
  return (a.score ?? -1) - (b.score ?? -1);
}
