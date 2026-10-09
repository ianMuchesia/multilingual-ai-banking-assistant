import { Navigate, Route, Routes } from "react-router-dom";
import { RequireAuth } from "./auth/RequireAuth";
import { BankingProvider } from "./banking/BankingProvider";
import { AppShell } from "./components/shell/AppShell";
import { routes } from "./config";
import { AssistantPage } from "./pages/AssistantPage";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";

export function App() {
  return (
    <Routes>
      <Route path={routes.login} element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <BankingProvider>
              <AppShell />
            </BankingProvider>
          </RequireAuth>
        }
      >
        <Route path={routes.home} element={<HomePage />} />
        <Route path={routes.assistant} element={<AssistantPage />} />
      </Route>
      <Route path="*" element={<Navigate to={routes.home} replace />} />
    </Routes>
  );
}
