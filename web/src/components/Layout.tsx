import React, { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import {
  Globe,
  Radio,
  Wifi,
  FileText,
  ShieldCheck,
  Truck,
  Layers,
  LogOut,
  UserCheck,
  AlertCircle,
  Menu,
  X,
} from "lucide-react";
import { SUPPORTED_LANGUAGES } from "../i18n";
import { useAuth } from "../auth/AuthContext";
import { api } from "../api/client";

export const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const { token, role, phoneMasked, assistedMode, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Poll backend health every 30 seconds
  const { data: health, isError } = useQuery({
    queryKey: ["backend-health"],
    queryFn: () => api.checkHealth(),
    refetchInterval: 30000,
    retry: 1,
  });

  const handleLanguageChange = (code: string) => {
    i18n.changeLanguage(code);
  };

  const navLinks = [
    { to: "/start", label: t("nav.start"), icon: Radio, show: !token },
    { to: "/chat", label: t("nav.chat"), icon: Wifi, show: true },
    { to: "/ops/funnel", label: t("nav.ops"), icon: Layers, show: role === "ops_admin" || role === "partner" },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
      {/* Top Banner: Assisted Mode */}
      {assistedMode && (
        <div className="bg-amber-600 text-white text-xs sm:text-sm font-semibold px-4 py-1.5 flex items-center justify-between shadow-sm">
          <div className="flex items-center space-x-2">
            <UserCheck className="w-4 h-4" />
            <span>{t("app.assisted_mode")}</span>
          </div>
          <span className="bg-amber-800 px-2 py-0.5 rounded text-[11px] uppercase tracking-wide">
            Partner: {phoneMasked || "Active"}
          </span>
        </div>
      )}

      {/* Main Header */}
      <header className="sticky top-0 z-30 bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          {/* Logo & Brand */}
          <Link to="/" className="flex items-center space-x-2.5">
            <div className="w-9 h-9 bg-airtel-red rounded-lg flex items-center justify-center text-white font-extrabold text-xl shadow-sm">
              a
            </div>
            <div>
              <span className="font-bold text-lg leading-tight tracking-tight text-slate-950 block">
                {t("app.title")}
              </span>
              <span className="text-[11px] text-slate-500 font-medium block">
                YTL Hackathon 2026
              </span>
            </div>
          </Link>

          {/* Desktop Right Actions */}
          <div className="hidden md:flex items-center space-x-4">
            {/* Health Badge */}
            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs bg-slate-100 border border-slate-200">
              <span
                className={`w-2 h-2 rounded-full ${
                  health?.status === "healthy" ? "bg-emerald-500 animate-pulse" : isError ? "bg-red-500" : "bg-amber-500"
                }`}
              />
              <span className="text-slate-600 font-mono">
                {health?.status === "healthy"
                  ? `Clock: ${health.clock.fixed_date}`
                  : isError
                  ? "Backend Offline"
                  : "Checking..."}
              </span>
            </div>

            {/* Language Picker */}
            <div className="relative flex items-center space-x-1 bg-slate-100 rounded-lg p-1 border border-slate-200">
              <Globe className="w-4 h-4 text-slate-500 ml-1.5" />
              <select
                value={i18n.language.slice(0, 2)}
                onChange={(e) => handleLanguageChange(e.target.value)}
                className="bg-transparent text-sm font-semibold text-slate-700 py-1 pr-2 focus:outline-none cursor-pointer"
                aria-label="Language selection"
              >
                {SUPPORTED_LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.nativeName} ({l.name})
                  </option>
                ))}
              </select>
            </div>

            {/* User Session Info / Sign Out */}
            {token ? (
              <div className="flex items-center space-x-2">
                <span className="text-xs bg-slate-200 text-slate-800 font-semibold px-2 py-1 rounded">
                  {phoneMasked || role}
                </span>
                <button
                  onClick={logout}
                  className="p-2 text-slate-500 hover:text-airtel-red transition-colors"
                  title={t("nav.logout")}
                  aria-label={t("nav.logout")}
                >
                  <LogOut className="w-5 h-5" />
                </button>
              </div>
            ) : (
              <Link
                to="/start"
                className="bg-airtel-red hover:bg-airtel-darkred text-white font-semibold text-sm px-4 py-2 rounded-lg transition-colors shadow-sm"
              >
                {t("nav.start")}
              </Link>
            )}
          </div>

          {/* Mobile Menu Button */}
          <div className="md:hidden flex items-center space-x-2">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 text-slate-700 tap-target flex items-center justify-center"
              aria-label="Toggle navigation menu"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>

        {/* Mobile Dropdown Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-slate-200 bg-white px-4 py-3 space-y-3 shadow-lg">
            {/* Mobile Language Switcher */}
            <div className="flex items-center justify-between py-2 border-b border-slate-100">
              <span className="text-sm font-semibold text-slate-600 flex items-center space-x-2">
                <Globe className="w-4 h-4 text-slate-400" />
                <span>Language</span>
              </span>
              <select
                value={i18n.language.slice(0, 2)}
                onChange={(e) => {
                  handleLanguageChange(e.target.value);
                  setMobileMenuOpen(false);
                }}
                className="bg-slate-100 text-sm font-semibold text-slate-800 py-1.5 px-3 rounded-lg border border-slate-200"
              >
                {SUPPORTED_LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.nativeName} ({l.name})
                  </option>
                ))}
              </select>
            </div>

            {/* Mobile Health Status */}
            <div className="flex items-center justify-between text-xs py-1 text-slate-500">
              <span>Backend Status:</span>
              <span className="font-mono text-emerald-700 font-semibold">
                {health?.status === "healthy" ? `Clock: ${health.clock.fixed_date}` : "Offline"}
              </span>
            </div>

            {/* Links */}
            <div className="flex flex-col space-y-2 pt-2">
              <Link
                to="/start"
                onClick={() => setMobileMenuOpen(false)}
                className="w-full text-center bg-airtel-red text-white font-semibold py-2.5 rounded-lg text-base"
              >
                {t("nav.start")}
              </Link>
              {token && (
                <button
                  onClick={() => {
                    logout();
                    setMobileMenuOpen(false);
                  }}
                  className="w-full text-center text-slate-600 font-semibold py-2 text-base"
                >
                  {t("nav.logout")}
                </button>
              )}
            </div>
          </div>
        )}
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-6 md:py-8">
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-6 text-center text-xs text-slate-500">
        <div className="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>&copy; 2026 Bharti Airtel Limited &bull; Project Udyam Digital</span>
          <div className="flex items-center space-x-3 text-slate-400">
            <span>DPDP Act 2023 Compliant</span>
            <span>&bull;</span>
            <span>AES-256 Identification Vault</span>
          </div>
        </div>
      </footer>
    </div>
  );
};
