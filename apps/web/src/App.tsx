import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components";
import { Dashboard } from "./pages/Dashboard";
import { History } from "./pages/History";
import { Interview } from "./pages/Interview";
import { ProjectDetail } from "./pages/ProjectDetail";
import { Projects } from "./pages/Projects";
import { Review } from "./pages/Review";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/projects/:id" element={<ProjectDetail />} />
          <Route path="/interview/:id" element={<Interview />} />
          <Route path="/review" element={<Review />} />
          <Route path="/history" element={<History />} />
          <Route path="*" element={<Dashboard />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
