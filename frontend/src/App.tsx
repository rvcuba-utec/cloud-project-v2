import { BrowserRouter, Navigate, Route, Routes } from 'react-router';
import Plantilla from './components/Plantilla';
import Inicio from './pages/Inicio';
import Login from './pages/Login';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<Plantilla />}>
          <Route index element={<Inicio />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
