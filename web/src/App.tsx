import { lazy, Suspense } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";
import BottomNav from "./components/BottomNav";
import PlanPage from "./pages/PlanPage";

const HomePage = lazy(() => import("./pages/HomePage"));
const SearchPage = lazy(() => import("./pages/SearchPage"));
const CityPage = lazy(() => import("./pages/CityPage"));
const AttractionPage = lazy(() => import("./pages/AttractionPage"));
const CityComparePage = lazy(() => import("./pages/CityComparePage"));
const PlanHomePage = lazy(() => import("./pages/PlanHomePage"));
const PlanQuickPage = lazy(() => import("./pages/PlanQuickPage"));
const PlanChatPage = lazy(() => import("./pages/PlanChatPage"));
const MePage = lazy(() => import("./pages/MePage"));
const AiSettingsPage = lazy(() => import("./pages/AiSettingsPage"));
const SharePage = lazy(() => import("./pages/SharePage"));
const ReviewAdminPage = lazy(() => import("./pages/ReviewAdminPage"));
const ComparePage = lazy(() => import("./pages/ComparePage"));

export default function App() {
  return (
    <div className="appShell">
      <header className="appHeader">
        <h1 className="appTitle">云旅 · 智能旅行规划</h1>
        <nav className="appNav">
          <Link to="/">首页</Link>
          <Link to="/review">纠错审核</Link>
          <Link to="/compare">方案对比</Link>
        </nav>
      </header>
      <main className="appMain">
        <Suspense fallback={<p className="muted">加载中…</p>}>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/city/:name" element={<CityPage />} />
            <Route path="/attraction/:name" element={<AttractionPage />} />
            <Route path="/cities/compare" element={<CityComparePage />} />
            <Route path="/plan" element={<PlanHomePage />}>
              <Route index element={<Navigate to="quick" replace />} />
              <Route path="quick" element={<PlanQuickPage />} />
              <Route path="chat" element={<PlanChatPage />} />
            </Route>
            <Route path="/plan/:sessionId" element={<PlanPage />} />
            <Route path="/me" element={<MePage />} />
            <Route path="/me/ai" element={<AiSettingsPage />} />
            <Route path="/share/:shortId" element={<SharePage />} />
            <Route path="/review" element={<ReviewAdminPage />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </main>
      <BottomNav />
    </div>
  );
}