import { Route, Routes } from "react-router-dom";

import { AppShell } from "./components/layout/AppShell";
import { ChatPage } from "./pages/ChatPage";
import { CatalogPage } from "./pages/CatalogPage";
import { AssetDetailPage } from "./pages/AssetDetailPage";
import { LineageGraphPage } from "./pages/LineageGraphPage";
import { GlossaryPage } from "./pages/GlossaryPage";

function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<ChatPage />} />
        <Route path="/assets" element={<CatalogPage />} />
        <Route path="/assets/:assetId" element={<AssetDetailPage />} />
        <Route path="/lineage" element={<LineageGraphPage />} />
        <Route path="/glossary" element={<GlossaryPage />} />
      </Routes>
    </AppShell>
  );
}

export default App;
