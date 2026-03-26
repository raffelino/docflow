import { Routes, Route } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { DashboardPage } from "@/pages/Dashboard";
import { DocumentsPage } from "@/pages/Documents";
import { RunDetailPage } from "@/pages/RunDetail";
import { SettingsPage } from "@/pages/Settings";
import { DocsPage } from "@/pages/Docs";

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/runs/:id" element={<RunDetailPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/docs" element={<DocsPage />} />
        <Route path="/docs/:slug" element={<DocsPage />} />
      </Route>
    </Routes>
  );
}

export default App;
