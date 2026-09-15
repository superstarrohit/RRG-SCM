import React from "react";
import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Incoming from "./pages/Incoming.jsx";
import Planning from "./pages/Planning.jsx";
import Sourcing from "./pages/Sourcing.jsx";
import Costing from "./pages/Costing.jsx";
import FGPlanning from "./pages/FGPlanning.jsx";
import StockMonitoring from "./pages/StockMonitoring.jsx";
import InventoryMonitoring from "./pages/InventoryMonitoring.jsx";
import DataWorkspace from "./pages/DataWorkspace.jsx";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/incoming" element={<Incoming />} />
        <Route path="/planning" element={<Planning />} />
        <Route path="/sourcing" element={<Sourcing />} />
        <Route path="/costing" element={<Costing />} />
        <Route path="/fg-planning" element={<FGPlanning />} />
        <Route path="/stock-monitoring" element={<StockMonitoring />} />
        <Route path="/inventory-monitoring" element={<InventoryMonitoring />} />
        <Route path="/data" element={<DataWorkspace />} />
        <Route path="/ingest" element={<DataWorkspace />} />
        <Route path="*" element={<Dashboard />} />
      </Routes>
    </Layout>
  );
}
