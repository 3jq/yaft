import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./index.css";

const qc = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: true,
      refetchInterval: 60_000,         // bot-created tx still appear within ~1 min, but no constant trickle
      refetchIntervalInBackground: false,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter basename={window.location.pathname.startsWith("/app") ? "/app" : "/"}>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
