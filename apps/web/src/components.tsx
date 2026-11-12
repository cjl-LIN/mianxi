import { useEffect, useMemo, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { api, useApi } from "./api";
import { RELATION_LABEL, formatScore, formatWhen, scoreTone } from "./format";
import type { GraphEdge, GraphNode, Health, HistoryItem, ScoreBlock } from "./types";

const NAV = [
  { to: "/", label: "总览", end: true },
  { to: "/projects", label: "项目", end: false },
  { to: "/review", label: "今日复习", end: false },
  { to: "/history", label: "作答历史", end: false },
];

export function Layout() {
  const [health, setHealth] = useState<Health | null>(null);
  const [offline, setOffline] = useState(false);
  useEffect(() => {
    api<Health>("/api/health")
      .then((next) => {
        setHealth(next);
        setOffline(false);
      })
      .catch(() => setOffline(true));
  }, []);

  return (
    <div className="shell">
      <aside className="sidebar">
        <NavLink to="/" className="brand">
          <span className="seal">面</span>
          <span>
            <strong>面习</strong>
            <small>本地面试练习</small>
          </span>
        </NavLink>
        <nav className="nav">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => (isActive ? "active" : "")}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <footer>
          {offline ? "后端未连接" : health?.llm ? "面试官：已接模型" : "面试官：内置脚本"}
          <br />
          {health ? `${health.knowledge} 个知识点` : "正在连接 API"}
        </footer>
      </aside>
      <div className="main">
        {offline ? (
          <div className="banner bad">
            后端没有连上。在仓库根目录另开一个终端运行
            <code> apps/api/.venv/bin/uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8741</code>
          </div>
        ) : null}
        <Outlet />
      </div>
    </div>
  );
}

export function Level({ level }: { level?: string | null }) {
  if (!level) return <span className="badge none">未练习</span>;
  const label = level === "weak" ? "薄弱" : level === "medium" ? "熟悉中" : level === "mastered" ? "已掌握" : level === "fluent" ? "熟练" : level;
  return <span className={`badge ${level}`}>{label}</span>;
}

export function Meters({ score }: { score: ScoreBlock }) {
  const rows: Array<[string, number]> = [
    ["相关性", score.relevance],
    ["正确性", score.correctness],
    ["完整度", score.completeness],
    ["推理", score.reasoning],
  ];
  return (
    <div>
      {rows.map(([label, value]) => (
        <div className="meter" key={label}>
          <div className="meter-top">
            <span>{label}</span>
            <strong className={scoreTone(value)}>{value.toFixed(1)}</strong>
          </div>
          <div className="meter-track">
            <div style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function HistoryTable({ projectId, limit }: { projectId?: string; limit: number }) {
  const [sort, setSort] = useState("time");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const path = useMemo(() => {
    const params = new URLSearchParams({ sort, order, limit: String(limit) });
    if (projectId) params.set("project_id", projectId);
    return `/api/history?${params.toString()}`;
  }, [sort, order, limit, projectId]);
  const { data, error, loading } = useApi<{ items: HistoryItem[] }>(path);

  function toggle(next: string) {
    if (sort === next) setOrder((current) => (current === "asc" ? "desc" : "asc"));
    else {
      setSort(next);
      setOrder(next === "time" ? "desc" : "desc");
    }
  }

  const columns: Array<[string, string]> = [
    ["time", "时间"],
    ["overall", "总分"],
    ["relevance", "相关"],
    ["correctness", "正确"],
    ["completeness", "完整"],
    ["reasoning", "推理"],
  ];

  return (
    <div>
      {error ? <div className="banner bad">{error}</div> : null}
      {loading && !data ? <p className="muted">正在读取作答…</p> : null}
      {data && data.items.length === 0 ? <p className="muted">完成一场模拟面试后，这里会留下每条回答和关联知识点。</p> : null}
      {data && data.items.length > 0 ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {columns.map(([key, label]) => (
                  <th key={key}>
                    <button type="button" onClick={() => toggle(key)}>
                      {label}
                      {sort === key ? (order === "asc" ? " ↑" : " ↓") : ""}
                    </button>
                  </th>
                ))}
                <th>回答</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <tr key={item.id}>
                  <td>{formatWhen(item.created_at)}</td>
                  <td className={scoreTone(item.overall)}>{formatScore(item.overall)}</td>
                  <td>{formatScore(item.relevance)}</td>
                  <td>{formatScore(item.correctness)}</td>
                  <td>{formatScore(item.completeness)}</td>
                  <td>{formatScore(item.reasoning)}</td>
                  <td>
                    <strong>{item.title}</strong>
                    <div className="muted clamp">{item.answer}</div>
                    <div className="chips">
                      <span className="chip">{item.project_name}</span>
                      {item.related.slice(0, 3).map((related) => (
                        <span className="chip" key={related.id}>
                          {RELATION_LABEL[related.relation] ?? related.relation} · {related.title}
                        </span>
                      ))}
                    </div>
                    {item.missing ? <div className="muted">{item.missing}</div> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

export function KnowledgeGraph({ projectId }: { projectId: string }) {
  const { data, error, loading } = useApi<{ nodes: GraphNode[]; edges: GraphEdge[] }>(
    `/api/graph?project_id=${encodeURIComponent(projectId)}`,
  );
  if (loading && !data) return <p className="muted">正在画知识关系…</p>;
  if (error) return <div className="banner bad">{error}</div>;
  if (!data || data.nodes.length === 0) return <p className="muted">这个项目还没有可画的知识点。</p>;

  const width = 680;
  const height = 440;
  const cx = width / 2;
  const cy = height / 2;
  const radius = data.nodes.length === 1 ? 0 : Math.min(width, height) * 0.34;
  const pos = new Map(
    data.nodes.map((node, index) => {
      const angle = (Math.PI * 2 * index) / data.nodes.length - Math.PI / 2;
      return [node.id, { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) }] as const;
    }),
  );
  const color: Record<string, string> = {
    prerequisite: "#8a5a10",
    part_of: "#1b6b4a",
    related: "#8a8178",
  };

  return (
    <div>
      <div className="graph-wrap">
        <svg className="graph" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="知识点关系图">
          {data.edges.map((edge, index) => {
            const from = pos.get(edge.from_id);
            const to = pos.get(edge.to_id);
            if (!from || !to) return null;
            return (
              <line
                key={`${edge.from_id}-${edge.to_id}-${edge.relation}-${index}`}
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke={color[edge.relation] ?? "#8a8178"}
                strokeWidth="1.4"
                strokeDasharray={edge.relation === "prerequisite" ? "4 3" : undefined}
              />
            );
          })}
          {data.nodes.map((node) => {
            const point = pos.get(node.id);
            if (!point) return null;
            const fill = node.level === "weak" ? "#9d2c2c" : node.level === "medium" ? "#8a5a10" : node.level ? "#1b6b4a" : "#6e665e";
            return (
              <g key={node.id}>
                <circle cx={point.x} cy={point.y} r="6" fill={fill} />
                <text x={point.x + 8} y={point.y + 4} fontSize="12" fill="#1d1a17">
                  {node.title.length > 10 ? `${node.title.slice(0, 10)}…` : node.title}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <div className="legend">
        <span><i className="swatch" style={{ background: "#8a5a10" }} />前置</span>
        <span><i className="swatch" style={{ background: "#1b6b4a" }} />属于</span>
        <span><i className="swatch" style={{ background: "#8a8178" }} />相关</span>
      </div>
    </div>
  );
}
