import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { Suspense, lazy } from 'react';
import Layout from './components/layout/Layout';
import { SkeletonCard } from './components/common/Skeleton';

// Lazy load all pages for code splitting
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const TradingPage = lazy(() => import('./pages/TradingPage'));
const BacktestPage = lazy(() => import('./pages/BacktestPage'));
const ConfigPage = lazy(() => import('./pages/ConfigPage'));
const LogsPage = lazy(() => import('./pages/LogsPage'));
const MarketDataPage = lazy(() => import('./pages/MarketDataPage'));
const MLInsightsPage = lazy(() => import('./pages/MLInsightsPage'));

function PageFallback() {
  return (
    <div className="space-y-4 animate-fade-in">
      <div className="h-8 w-48 skeleton" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SkeletonCard className="h-64" />
        <SkeletonCard className="h-64" />
      </div>
    </div>
  );
}

function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center py-32 animate-fade-in-up">
      <div className="text-7xl font-black text-gradient-blue mb-4">404</div>
      <p className="text-lg text-[var(--text-secondary)] mb-6">Page not found</p>
      <a href="/" className="btn-primary px-6 py-2.5">Back to Dashboard</a>
    </div>
  );
}

function AnimatedRoutes() {
  const location = useLocation();

  return (
    <div key={location.pathname} className="animate-fade-in-up" style={{ animationDuration: '0.25s' }}>
      <Suspense fallback={<PageFallback />}>
        <Routes location={location}>
          <Route path="/" element={<Layout />}>
            <Route index element={<DashboardPage />} />
            <Route path="trading" element={<TradingPage />} />
            <Route path="backtest" element={<BacktestPage />} />
            <Route path="config" element={<ConfigPage />} />
            <Route path="logs" element={<LogsPage />} />
            <Route path="market" element={<MarketDataPage />} />
            <Route path="ml" element={<MLInsightsPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </Suspense>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AnimatedRoutes />
    </BrowserRouter>
  );
}

export default App;
