import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/layout/Layout';
import DashboardPage from './pages/DashboardPage';
import TradingPage from './pages/TradingPage';
import BacktestPage from './pages/BacktestPage';
import ConfigPage from './pages/ConfigPage';
import LogsPage from './pages/LogsPage';
import MarketDataPage from './pages/MarketDataPage';
import MLInsightsPage from './pages/MLInsightsPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="trading" element={<TradingPage />} />
          <Route path="backtest" element={<BacktestPage />} />
          <Route path="config" element={<ConfigPage />} />
          <Route path="logs" element={<LogsPage />} />
          <Route path="market" element={<MarketDataPage />} />
          <Route path="ml" element={<MLInsightsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
