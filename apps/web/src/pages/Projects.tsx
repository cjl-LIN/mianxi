import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, useApi } from "../api";
import type { ProjectDetail, ProjectSummary } from "../types";

export function Projects() {
  const navigate = useNavigate();
  const { data, error, loading, reload } = useApi<{ projects: ProjectSummary[] }>("/api/projects");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [jd, setJd] = useState("");
  const [seed, setSeed] = useState(true);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFormError(null);
    try {
      const created = await api<ProjectDetail>("/api/projects", {
        method: "POST",
        body: JSON.stringify({ name, description, jd_text: jd, seed }),
      });
      reload();
      navigate(`/projects/${created.id}`);
    } catch (reason) {
      setFormError(reason instanceof Error ? reason.message : "创建失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <header className="page-head">
        <div>
          <h1>项目</h1>
          <p className="muted lede">每个项目是一条独立的准备线。知识点可以挂到多个项目，掌握度仍然只有一份。</p>
        </div>
      </header>
      {error ? <div className="banner bad">{error}</div> : null}
      <div className="split">
        <div>
          {loading && !data ? <p className="muted">正在读取项目…</p> : null}
          <div className="projects">
            {data?.projects.map((project) => (
              <Link className="card project-card" key={project.id} to={`/projects/${project.id}`}>
                <h2>{project.name}</h2>
                <p className="muted">{project.description}</p>
                <div className="chips">
                  <span className="chip">{project.knowledge_count} 个知识点</span>
                  <span className="chip">{project.mastered_count} 已掌握</span>
                  <span className="chip">{project.due_count} 到期</span>
                </div>
              </Link>
            ))}
          </div>
        </div>
        <form className="card" onSubmit={(event) => void onSubmit(event)}>
          <h2>从 JD 新建</h2>
          <label className="field">
            <span>项目名称</span>
            <input data-testid="create-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：AI 产品经理" required />
          </label>
          <label className="field">
            <span>方向</span>
            <input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="这个项目要准备成什么样" />
          </label>
          <label className="field">
            <span>岗位描述</span>
            <textarea value={jd} onChange={(event) => setJd(event.target.value)} placeholder="把 JD 贴在这里。没有 JD 也可以，只写方向。" />
          </label>
          <label className="check">
            <input type="checkbox" checked={seed} onChange={(event) => setSeed(event.target.checked)} />
            用本地知识点库补齐起步内容
          </label>
          {formError ? <div className="banner bad">{formError}</div> : null}
          <button className="primary" type="submit" disabled={busy} data-testid="create-submit">
            {busy ? "正在创建…" : "创建项目"}
          </button>
        </form>
      </div>
    </section>
  );
}
