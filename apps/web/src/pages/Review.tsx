import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, useApi } from "../api";
import { Level } from "../components";
import { REVIEW_STATUS, formatDay, formatScore, formatWhen } from "../format";
import type { Reminder, ReviewItem, Session } from "../types";

const FILTERS = [
  ["due", "今日到期"],
  ["overdue", "已逾期"],
  ["upcoming", "即将到来"],
  ["unscheduled", "未排期"],
  ["all", "全部"],
] as const;

export function Review() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<(typeof FILTERS)[number][0]>("due");
  const [style, setStyle] = useState<"strict" | "loose">("loose");
  const [error, setError] = useState<string | null>(null);
  const table = useApi<{ items: ReviewItem[]; counts: Record<string, number> }>(`/api/reviews?filter=${filter}`);
  const reminders = useApi<{ items: Reminder[] }>("/api/reminders?scope=open");

  async function practice(item: ReviewItem) {
    const projectId = item.projects[0]?.id;
    if (!projectId) return;
    setError(null);
    try {
      const session = await api<Session>("/api/sessions", {
        method: "POST",
        body: JSON.stringify({
          project_id: projectId,
          style,
          mode: "review",
          knowledge_ids: [item.knowledge_id],
        }),
      });
      navigate(`/interview/${session.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "没能开始复习");
    }
  }

  async function dismiss(id: string) {
    await api(`/api/reminders/${id}/dismiss`, { method: "POST" });
    reminders.reload();
  }

  return (
    <section>
      <header className="page-head">
        <div>
          <h1>今日复习</h1>
          <p className="muted lede">
            薄弱 1–2 天，熟悉中 3–5 天，已掌握 7–14 天，熟练 21–30 天。到期后才重新出现，不在别的项目里重复开考。
          </p>
        </div>
        <div className="filters">
          <button type="button" className="ghost" aria-pressed={style === "loose"} onClick={() => setStyle("loose")}>宽松</button>
          <button type="button" className="ghost" aria-pressed={style === "strict"} onClick={() => setStyle("strict")}>严格</button>
        </div>
      </header>
      {error ? <div className="banner bad">{error}</div> : null}
      <section className="card">
        <h2>提醒</h2>
        {reminders.data && reminders.data.items.length === 0 ? <p className="muted">没有未读提醒。</p> : null}
        <div className="chat-list">
          {reminders.data?.items.map((item) => (
            <article className="bubble interviewer" key={item.id}>
              <span className="who">{item.title} · {formatWhen(item.due_at)}</span>
              {item.message}
              <div><button type="button" className="texty" onClick={() => void dismiss(item.id)}>知道了</button></div>
            </article>
          ))}
        </div>
      </section>
      <section className="card stack">
        <div className="filters">
          {FILTERS.map(([key, label]) => (
            <button key={key} type="button" className="ghost" aria-pressed={filter === key} onClick={() => setFilter(key)}>
              {label}{table.data ? ` ${table.data.counts[key] ?? 0}` : ""}
            </button>
          ))}
        </div>
        {table.error ? <div className="banner bad">{table.error}</div> : null}
        {table.loading && !table.data ? <p className="muted">正在读取复习表…</p> : null}
        {table.data && table.data.items.length === 0 ? (
          <p className="muted">这一栏是空的。完成一次模拟面试后，薄弱点会在一两天内回到这里。</p>
        ) : null}
        {table.data && table.data.items.length > 0 ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>知识点</th>
                  <th>等级</th>
                  <th>分数</th>
                  <th>项目</th>
                  <th>上次</th>
                  <th>下次</th>
                  <th>状态</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {table.data.items.map((item) => (
                  <tr key={item.knowledge_id}>
                    <td>{item.title}</td>
                    <td><Level level={item.level} /></td>
                    <td>{formatScore(item.score)}</td>
                    <td>{item.projects.map((project) => project.name).join("、")}</td>
                    <td>{formatDay(item.last_practiced_at)}</td>
                    <td>{formatDay(item.next_review_at)}</td>
                    <td>{REVIEW_STATUS[item.status] ?? item.status}</td>
                    <td>
                      <button type="button" className="texty" onClick={() => void practice(item)}>开始复习</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </section>
  );
}
