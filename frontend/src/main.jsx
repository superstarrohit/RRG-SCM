import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import { FiltersProvider } from "./components/filters.jsx";
import { ThemeProvider } from "./components/theme.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeProvider>
      <BrowserRouter>
        <FiltersProvider>
          <App />
        </FiltersProvider>
      </BrowserRouter>
    </ThemeProvider>
  </React.StrictMode>
);
