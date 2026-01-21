import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import Index from "./pages/index";
import UploadPage from "./pages/UploadPage";
import "./App.css";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Index />} />
        <Route path="/upload" element={<UploadPage />} />
      </Routes>
      <Toaster position="top-right" richColors />
    </BrowserRouter>
  );
}

export default App;
