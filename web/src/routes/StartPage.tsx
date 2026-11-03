import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Globe,
  Phone,
  ShieldCheck,
  ArrowRight,
  UserCheck,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  Lock,
  Layers,
} from "lucide-react";
import { SUPPORTED_LANGUAGES } from "../i18n";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { UserRole } from "../api/types";

export const StartPage: React.FC = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { login, setActiveLeadId, setAssistedMode: setGlobalAssistedMode } = useAuth();

  // State
  const [selectedLanguage, setSelectedLanguage] = useState<string>(i18n.language.slice(0, 2) || "en");
  const [phone, setPhone] = useState<string>("");
  const [role, setRole] = useState<UserRole>("customer");
  const [isAssisted, setIsAssisted] = useState<boolean>(false);
  const [partnerId, setPartnerId] = useState<string>("");

  // OTP flow state
  const [otpSent, setOtpSent] = useState<boolean>(false);
  const [otpCode, setOtpCode] = useState<string>("123456");
  const [maskedPhone, setMaskedPhone] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleLanguageSelect = (code: string) => {
    setSelectedLanguage(code);
    i18n.changeLanguage(code);
  };

  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const cleanPhone = phone.trim().replace(/\D/g, "");
    if (cleanPhone.length < 10) {
      setErrorMessage("Please enter a valid 10-digit Indian mobile number.");
      return;
    }

    setLoading(true);
    try {
      const res = await api.sendOtp(cleanPhone);
      setOtpSent(true);
      setMaskedPhone(res.phone_masked);
      setOtpCode("123456"); // Pre-fill fixed demo OTP
    } catch (err: any) {
      setErrorMessage(err.detail || "Failed to dispatch OTP. Please check backend connection.");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyAndCreateLead = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const cleanPhone = phone.trim().replace(/\D/g, "");
    if (!otpCode || otpCode.length !== 6) {
      setErrorMessage("Please enter the 6-digit verification OTP.");
      return;
    }

    setLoading(true);
    try {
      // 1. Verify OTP with real JWT issuance
      const authRes = await api.verifyOtp(cleanPhone, otpCode, role === "reviewer" ? "ops_admin" : role);
      login(authRes.access_token, authRes.role, authRes.phone_masked);
      setGlobalAssistedMode(isAssisted);

      // 2. Create Lead in PostgreSQL
      const leadRes = await api.createLead({
        phone: cleanPhone,
        language: selectedLanguage,
        source: isAssisted ? "channel_partner" : "web_start",
      });

      setActiveLeadId(leadRes.lead_id);

      // 3. Navigate to chat advisor
      navigate(`/chat?leadId=${leadRes.lead_id}`);
    } catch (err: any) {
      setErrorMessage(err.detail || "Authentication or lead registration failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto py-4">
      {/* Step Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center space-x-2 bg-airtel-lightred text-airtel-red text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider mb-2">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Step 1 of 5 &bull; Instant Access</span>
        </div>
        <h1 className="text-3xl font-black text-slate-950 tracking-tight mb-2">
          {t("nav.start")}
        </h1>
        <p className="text-slate-600 text-sm">
          Select your preferred language and verify mobile to begin personalized consultation.
        </p>
      </div>

      <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-sm space-y-6">
        {/* Error Alert Banner */}
        {errorMessage && (
          <div className="bg-red-50 border border-red-200 text-red-800 p-4 rounded-xl flex items-start space-x-3 text-sm animate-shake">
            <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
            <div className="flex-1 font-medium">{errorMessage}</div>
          </div>
        )}

        {/* 1. Language Selection Grid */}
        <div>
          <label className="text-xs font-bold text-slate-700 uppercase tracking-wider block mb-3 flex items-center space-x-1.5">
            <Globe className="w-4 h-4 text-slate-400" />
            <span>Select Preferred Language (भाषा निवडा)</span>
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {SUPPORTED_LANGUAGES.map((lang) => {
              const isSelected = selectedLanguage === lang.code;
              return (
                <button
                  key={lang.code}
                  type="button"
                  onClick={() => handleLanguageSelect(lang.code)}
                  className={`p-3 rounded-xl border text-left transition-all tap-target flex flex-col justify-center ${
                    isSelected
                      ? "border-airtel-red bg-airtel-lightred text-airtel-red font-bold shadow-sm"
                      : "border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-800"
                  }`}
                >
                  <span className="text-base leading-none mb-1">{lang.nativeName}</span>
                  <span className="text-xs text-slate-500 font-normal">{lang.name}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* 2. Role & Demo Mode Controls */}
        <div className="pt-2 border-t border-slate-100">
          <label className="text-xs font-bold text-slate-700 uppercase tracking-wider block mb-2">
            Demo Persona & Role (जॉब रोल)
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {[
              { id: "customer", label: "Business Owner" },
              { id: "partner", label: "Channel Partner" },
              { id: "sales", label: "Field Sales" },
              { id: "reviewer", label: "Ops Supervisor" },
            ].map((rItem) => (
              <button
                key={rItem.id}
                type="button"
                onClick={() => {
                  setRole(rItem.id as UserRole);
                  if (rItem.id === "partner" || rItem.id === "sales") {
                    setIsAssisted(true);
                  }
                }}
                className={`py-2 px-3 rounded-lg text-xs font-semibold border transition-all text-center tap-target flex items-center justify-center ${
                  role === rItem.id
                    ? "bg-slate-900 text-white border-slate-900 shadow-sm"
                    : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                }`}
              >
                {rItem.label}
              </button>
            ))}
          </div>

          {/* Assisted Mode Toggle */}
          <div className="mt-3 flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-200">
            <div className="flex items-center space-x-2.5">
              <UserCheck className="w-5 h-5 text-amber-600" />
              <div>
                <span className="text-xs font-bold text-slate-900 block">Assisted Onboarding Mode</span>
                <span className="text-[11px] text-slate-500 block">Channel partner onboarding an SMB owner</span>
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={isAssisted}
                onChange={(e) => setIsAssisted(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-amber-600"></div>
            </label>
          </div>
        </div>

        {/* 3. Mobile Number & OTP Verification */}
        <div className="pt-2 border-t border-slate-100">
          {!otpSent ? (
            <form onSubmit={handleSendOtp} className="space-y-4">
              <div>
                <label className="text-xs font-bold text-slate-700 uppercase tracking-wider block mb-1.5 flex items-center space-x-1.5">
                  <Phone className="w-4 h-4 text-slate-400" />
                  <span>Business Contact Mobile (मोबाइल नंबर)</span>
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500 font-semibold text-sm">
                    +91
                  </div>
                  <input
                    type="tel"
                    maxLength={10}
                    value={phone}
                    onChange={(e) => setPhone(e.target.value.replace(/\D/g, ""))}
                    placeholder="9876543210"
                    className="w-full pl-12 pr-4 py-3 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-airtel-red focus:border-transparent text-base font-semibold text-slate-900 tracking-wider tap-target"
                    required
                  />
                </div>
                <span className="text-[11px] text-slate-500 mt-1 block">
                  Encrypted at rest with AES-256 Fernet; masked in logs and screens.
                </span>
              </div>

              <button
                type="submit"
                disabled={loading || phone.length < 10}
                className="w-full bg-airtel-red hover:bg-airtel-darkred disabled:bg-slate-300 text-white font-bold py-3.5 px-6 rounded-xl transition-all shadow-md flex items-center justify-center space-x-2 tap-target active:scale-95"
              >
                <span>{loading ? "Sending OTP..." : "Get Verification OTP"}</span>
                <ArrowRight className="w-5 h-5" />
              </button>
            </form>
          ) : (
            <form onSubmit={handleVerifyAndCreateLead} className="space-y-4">
              <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-200 flex items-center justify-between text-xs text-emerald-800">
                <div className="flex items-center space-x-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span>OTP dispatched to <strong>{maskedPhone || phone}</strong></span>
                </div>
                <button
                  type="button"
                  onClick={() => setOtpSent(false)}
                  className="underline text-emerald-700 hover:text-emerald-900 font-bold"
                >
                  Change
                </button>
              </div>

              <div>
                <label className="text-xs font-bold text-slate-700 uppercase tracking-wider block mb-1.5 flex items-center space-x-1.5">
                  <Lock className="w-4 h-4 text-slate-400" />
                  <span>Enter 6-Digit Verification Code (ओटीपी)</span>
                </label>
                <input
                  type="text"
                  maxLength={6}
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ""))}
                  placeholder="123456"
                  className="w-full px-4 py-3 text-center text-2xl font-black font-mono tracking-widest rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-airtel-red text-slate-900 tap-target"
                  required
                />
                <span className="text-[11px] text-slate-500 mt-1 text-center block">
                  Demo fixed code: <strong className="text-slate-800 font-mono">123456</strong>
                </span>
              </div>

              <button
                type="submit"
                disabled={loading || otpCode.length !== 6}
                className="w-full bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white font-bold py-3.5 px-6 rounded-xl transition-all shadow-md flex items-center justify-center space-x-2 tap-target active:scale-95"
              >
                <span>{loading ? "Authenticating..." : "Verify & Start Consultation"}</span>
                <ArrowRight className="w-5 h-5" />
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
