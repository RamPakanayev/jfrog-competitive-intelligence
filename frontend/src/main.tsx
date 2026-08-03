import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import App from "./App";
import "./index.css";
import Compare from "./pages/Compare";
import CompetitorDetail from "./pages/CompetitorDetail";
import Competitors from "./pages/Competitors";
import Feed from "./pages/Feed";
import Today from "./pages/Today";

const router = createBrowserRouter([
  { path: "/", element: <App />, children: [
    { index: true, element: <Today /> },
    { path: "feed", element: <Feed /> },
    { path: "competitors", element: <Competitors /> },
    { path: "competitors/:slug", element: <CompetitorDetail /> },
    { path: "compare", element: <Compare /> },
  ]},
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
);
