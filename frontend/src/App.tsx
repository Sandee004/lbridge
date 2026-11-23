import { useState, useEffect } from "react";
import { CheckCircle2, Server, Globe, ExternalLink } from "lucide-react";

export default function App() {
  const [backendStatus, setBackendStatus] = useState<"checking" | "connected" | "error">("checking");

  useEffect(() => {
    fetch("http://localhost:8000/health")
      .then((res) => {
        if (res.ok) setBackendStatus("connected");
        else setBackendStatus("error");
      })
      .catch(() => setBackendStatus("error"));
  }, []);

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex items-center justify-center p-6 selection:bg-neutral-800">
      <div className="w-full max-w-md border border-neutral-800 bg-neutral-900/60 backdrop-blur-xl p-8 rounded-2xl shadow-2xl">
        <div className="flex items-center gap-3 mb-6">
          <div className="h-10 w-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-white">Project Startup Complete</h1>
            <p className="text-xs text-neutral-400">Vite, Tailwind v4 & FastAPI are live</p>
          </div>
        </div>

        <div className="space-y-3 mb-6">
          <div className="flex items-center justify-between p-3.5 rounded-xl bg-neutral-950/60 border border-neutral-800/80">
            <div className="flex items-center gap-2.5 text-sm">
              <Globe className="w-4 h-4 text-neutral-400" />
              <span className="font-medium text-neutral-200">Frontend Client</span>
            </div>
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Port 5173
            </span>
          </div>

          <div className="flex items-center justify-between p-3.5 rounded-xl bg-neutral-950/60 border border-neutral-800/80">
            <div className="flex items-center gap-2.5 text-sm">
              <Server className="w-4 h-4 text-neutral-400" />
              <span className="font-medium text-neutral-200">FastAPI Engine</span>
            </div>
            <span
              className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${
                backendStatus === "connected"
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                  : backendStatus === "checking"
                  ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                  : "bg-rose-500/10 text-rose-400 border-rose-500/20"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  backendStatus === "connected"
                    ? "bg-emerald-400 animate-pulse"
                    : backendStatus === "checking"
                    ? "bg-amber-400"
                    : "bg-rose-400"
                }`}
              />
              {backendStatus === "connected" ? "Online" : backendStatus === "checking" ? "Connecting..." : "Offline"}
            </span>
          </div>
        </div>

        <div className="pt-2 flex flex-col gap-2">
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="flex items-center justify-center gap-2 w-full py-2.5 px-4 rounded-xl bg-neutral-100 hover:bg-white text-neutral-900 font-medium text-sm transition-colors"
          >
            Open Swagger API Docs
            <ExternalLink className="w-3.5 h-3.5 text-neutral-600" />
          </a>
        </div>
      </div>
    </div>
  );
}
