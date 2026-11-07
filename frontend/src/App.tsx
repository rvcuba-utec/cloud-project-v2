import { BrowserRouter, Navigate, Route, Routes } from 'react-router';
import Plantilla from './components/Plantilla';
import RutaPorRol from './components/RutaPorRol';
import Agenda from './pages/Agenda';
import Atencion from './pages/Atencion';
import Clientes from './pages/Clientes';
import DetalleCliente from './pages/DetalleCliente';
import DetalleOrden from './pages/DetalleOrden';
import DetalleParte from './pages/DetalleParte';
import DetalleTecnico from './pages/DetalleTecnico';
import Inicio from './pages/Inicio';
import Login from './pages/Login';
import MisVisitas from './pages/MisVisitas';
import NuevaOrden from './pages/NuevaOrden';
import Ordenes from './pages/Ordenes';
import Tecnicos from './pages/Tecnicos';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<Plantilla />}>
          <Route index element={<Inicio />} />
          <Route element={<RutaPorRol roles={['ADMIN', 'COORDINADOR']} />}>
            <Route path="clientes" element={<Clientes />} />
            <Route path="clientes/:id" element={<DetalleCliente />} />
            <Route path="tecnicos" element={<Tecnicos />} />
            <Route path="tecnicos/:id" element={<DetalleTecnico />} />
            <Route path="ordenes" element={<Ordenes />} />
            <Route path="ordenes/nueva" element={<NuevaOrden />} />
            <Route path="ordenes/:id" element={<DetalleOrden />} />
            <Route path="agenda" element={<Agenda />} />
          </Route>
          <Route element={<RutaPorRol roles={['TECNICO']} />}>
            <Route path="mis-visitas" element={<MisVisitas />} />
            <Route path="mis-visitas/:id" element={<Atencion />} />
          </Route>
          <Route path="partes/:id" element={<DetalleParte />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
