import { useState } from "react";
import { useApi } from "../api";
import { HistoryTable } from "../components";
import type { ProjectSummary } from "../types";

export function History() {
  const [projectId, setProjectId] = useState("");
  const projects = useApi<{ projects: ProjectSummary[] }>("/api/projects");
  return (
    <section>
      <header className="page-head">
        <div>
          <h1>作答历史</h1>
          <p className="muted lede">每条回答都挂着知识点和它的相邻概念。点表头可以按时间或四项分数排序。</p>
        </div>
        <label className="field" style={{ margin: 0, minWidth: 180 }}>
          <span>项目</span>
          <select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
            <option value="">全部</option>
            {projects.data?.projects.map((project) => (
              <option key={project.id} value={project.id}>{project.name}</option>
            ))}
          </select>
        </label>
      </header>
      <section className="card">
        <HistoryTable projectId={projectId || undefined} limit={200} />
      </section>
    </section>
  );
}
