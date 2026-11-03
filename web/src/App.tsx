import React from "react";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import {
  Sparkles,
  ArrowRight,
  ShieldCheck,
  Zap,
  Activity,
  Bot,
  FileCheck,
  CreditCard,
  Truck,
  CheckCircle2,
} from "lucide-react";
import { Layout } from "./components/Layout";
import { RoutePlaceholder } from "./routes/Placeholder";
import { StartPage } from "./routes/StartPage";
import { ChatPage } from "./routes/ChatPage";
import { QuotePage } from "./routes/QuotePage";
import { ConsentPage } from "./routes/ConsentPage";
import { KycPage } from "./routes/KycPage";
import { api } from "./api/client";

const HomePage: React.FC = () => {
  const { t } = useTranslation();

  const { data: health, isLoading } = useQuery({
    queryKey: ["home-health"],
    queryFn: () => api.checkHealth(),
  });

  return (
    <div className="space-y-8 max-w-4xl mx-auto py-2">
      {/* Hero Section */}
      <div className="bg-gradient-to-br from-white to-slate-100 rounded-3xl p-6 md:p-10 border border-slate-200/80 shadow-sm relative overflow-hidden">
        <div className="max-w-2xl">
          <div className="inline-flex items-center space-x-2 bg-airtel-lightred text-airtel-red text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider mb-4">
            <Sparkles className="w-3.5 h-3.5" />
            <span>YTL Hackathon 2026 &bull; Enterprise Track A</span>
          </div>
          <h1 className="text-3xl sm:text-4xl md:text-5xl font-black text-slate-950 tracking-tight leading-tight mb-4">
            {t("app.title")}
          </h1>
          <p className="text-base sm:text-lg text-slate-600 mb-8 leading-relaxed">
            {t("app.tagline")}
          </p>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <Link
              to="/start"
              className="inline-flex items-center justify-center space-x-2 bg-airtel-red hover:bg-airtel-darkred text-white font-bold text-base px-6 py-3.5 rounded-xl shadow-md transition-all active:scale-95"
            >
              <span>{t("nav.start")}</span>
              <ArrowRight className="w-5 h-5" />
            </Link>
            <Link
              to="/chat"
              className="inline-flex items-center justify-center space-x-2 bg-white hover:bg-slate-50 text-slate-800 font-bold text-base px-6 py-3.5 rounded-xl border border-slate-300 shadow-sm transition-all"
            >
              <Bot className="w-5 h-5 text-airtel-red" />
              <span>{t("nav.chat")}</span>
            </Link>
          </div>
        </div>
      </div>

      {/* Live Backend Connection Card */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div className="flex items-center space-x-3">
            <Activity className="w-5 h-5 text-airtel-red" />
            <h2 className="text-lg font-bold text-slate-900">{t("health.title")}</h2>
          </div>
          <span
            className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold uppercase ${
              health?.status === "healthy"
                ? "bg-emerald-100 text-emerald-800"
                : "bg-amber-100 text-amber-800"
            }`}
          >
            {health?.status || (isLoading ? "Connecting..." : "Degraded")}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4">
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
            <span className="text-xs font-medium text-slate-500 block mb-1">Fixed ClockPort</span>
            <span className="text-base font-bold font-mono text-slate-900 block">
              {health?.clock?.fixed_date || "2026-07-15"}
            </span>
            <span className="text-xs text-slate-400 font-mono">10:00:00 UTC</span>
          </div>

          <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
            <span className="text-xs font-medium text-slate-500 block mb-1">Database & Cache</span>
            <div className="space-y-0.5 text-xs font-semibold text-slate-700">
              <div className="flex items-center justify-between">
                <span>Postgres 16</span>
                <span className="text-emerald-600 font-mono">{health?.services?.postgres || "ok"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Redis 7</span>
                <span className="text-emerald-600 font-mono">{health?.services?.redis || "ok"}</span>
              </div>
            </div>
          </div>

          <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
            <span className="text-xs font-medium text-slate-500 block mb-1">Encrypted Vault</span>
            <div className="space-y-0.5 text-xs font-semibold text-slate-700">
              <div className="flex items-center justify-between">
                <span>MinIO Storage</span>
                <span className="text-emerald-600 font-mono">{health?.services?.minio || "ok"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Fernet AES-256</span>
                <span className="text-emerald-600 font-mono">Active</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Customer Journey Roadmap */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
        <h3 className="text-base font-bold text-slate-900 mb-4 flex items-center space-x-2">
          <Zap className="w-4 h-4 text-airtel-red" />
          <span>Complete SMB Onboarding Lifecycle</span>
        </h3>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
          {[
            { step: "1", label: "OTP & Lead", route: "/start", icon: CheckCircle2 },
            { step: "2", label: "AI Advisor", route: "/chat", icon: Bot },
            { step: "3", label: "Quote Engine", route: "/quote/demo", icon: FileCheck },
            { step: "4", label: "Smart KYC", route: "/kyc/demo", icon: ShieldCheck },
            { step: "5", label: "Sign & Pay", route: "/sign/demo", icon: CreditCard },
            { step: "6", label: "Live Tracker", route: "/track/demo", icon: Truck },
          ].map((item) => (
            <Link
              key={item.step}
              to={item.route}
              className="p-3 bg-slate-50 hover:bg-airtel-lightred border border-slate-200 hover:border-airtel-red/30 rounded-xl flex flex-col items-center text-center transition-all group"
            >
              <item.icon className="w-5 h-5 text-slate-600 group-hover:text-airtel-red mb-1.5 transition-colors" />
              <span className="text-xs font-bold text-slate-800">{item.label}</span>
              <span className="text-[10px] text-slate-400">Step {item.step}</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/start" element={<StartPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/quote/:quoteId" element={<QuotePage />} />
          <Route path="/consent" element={<ConsentPage />} />
          <Route path="/kyc/:caseId" element={<KycPage />} />
          <Route path="/sign/:quoteId" element={<RoutePlaceholder title="Aadhaar e-Sign & UPI Mandate" stepNumber={5} />} />
          <Route path="/track/:orderId" element={<RoutePlaceholder title="Live SSE Order Tracker" stepNumber={5} />} />
          <Route path="/ops/leads" element={<RoutePlaceholder title="Back-Office Lead Queue" stepNumber={6} />} />
          <Route path="/ops/review" element={<RoutePlaceholder title="Supervisor KYC Review" stepNumber={6} />} />
          <Route path="/ops/funnel" element={<RoutePlaceholder title="Real-Time Conversion Funnel" stepNumber={6} />} />
          <Route path="/wa-sim" element={<RoutePlaceholder title="WhatsApp Business Simulator" stepNumber={6} />} />
          <Route path="*" element={<HomePage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
};

export default App;
