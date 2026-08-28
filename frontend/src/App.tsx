import { NavLink, Route, Routes } from "react-router-dom";
import { WrenchIcon } from "./components/icons";
import { DashboardPage } from "./pages/DashboardPage";
import { EquipmentDetailPage } from "./pages/EquipmentDetailPage";
import { EquipmentListPage } from "./pages/EquipmentListPage";
import { EquipmentLoansPage } from "./pages/EquipmentLoansPage";
import { PartsPage } from "./pages/PartsPage";

function App() {
  return (
    <div className="app">
      <nav className="app-nav">
        <span className="app-brand">
          <WrenchIcon />
          <span className="app-title">
            Maintain<span>Ops</span>
          </span>
        </span>
        <NavLink to="/" end>
          Dashboard
        </NavLink>
        <NavLink to="/equipment">Equipment</NavLink>
        <NavLink to="/borrowed">Borrowed</NavLink>
        <NavLink to="/parts">Parts</NavLink>
      </nav>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/equipment" element={<EquipmentListPage />} />
          <Route path="/equipment/:id" element={<EquipmentDetailPage />} />
          <Route path="/borrowed" element={<EquipmentLoansPage />} />
          <Route path="/parts" element={<PartsPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
