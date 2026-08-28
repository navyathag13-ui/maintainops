import { NavLink, Route, Routes } from "react-router-dom";
import { WrenchIcon } from "./components/icons";
import { ActivityPage } from "./pages/ActivityPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EmployeeDetailPage } from "./pages/EmployeeDetailPage";
import { EmployeesPage } from "./pages/EmployeesPage";
import { EquipmentDetailPage } from "./pages/EquipmentDetailPage";
import { EquipmentListPage } from "./pages/EquipmentListPage";
import { EquipmentLoansPage } from "./pages/EquipmentLoansPage";
import { PartsPage } from "./pages/PartsPage";
import { ProjectDetailPage } from "./pages/ProjectDetailPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ReportsPage } from "./pages/ReportsPage";

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
        <NavLink to="/projects">Projects</NavLink>
        <NavLink to="/equipment">Equipment</NavLink>
        <NavLink to="/parts">Parts Inventory</NavLink>
        <NavLink to="/employees">Employees</NavLink>
        <NavLink to="/activity">Activity</NavLink>
        <NavLink to="/reports">Reports</NavLink>
      </nav>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/projects/:id" element={<ProjectDetailPage />} />
          <Route path="/equipment" element={<EquipmentListPage />} />
          <Route path="/equipment/:id" element={<EquipmentDetailPage />} />
          {/* Not in the main nav (checkout/return now happens contextually
              from Equipment and Projects) but kept reachable as a filtered
              cross-project view of everything currently deployed. */}
          <Route path="/borrowed" element={<EquipmentLoansPage />} />
          <Route path="/parts" element={<PartsPage />} />
          <Route path="/employees" element={<EmployeesPage />} />
          <Route path="/employees/:id" element={<EmployeeDetailPage />} />
          <Route path="/activity" element={<ActivityPage />} />
          <Route path="/reports" element={<ReportsPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
