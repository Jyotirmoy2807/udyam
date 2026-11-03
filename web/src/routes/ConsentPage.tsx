import React, { useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useMutation } from "@tanstack/react-query";
import {
  ShieldCheck,
  Lock,
  Clock,
  CheckCircle2,
  AlertCircle,
  FileText,
  ArrowRight,
  ShieldAlert,
} from "lucide-react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export const ConsentPage: React.FC = () => {
  const { t, i18n } = useTranslation();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { activeLeadId } = useAuth();

  const leadId = searchParams.get("leadId") || activeLeadId || "";
  const quoteId = searchParams.get("quoteId") || "";

  // Consent Purpose Checkboxes
  const [purposes, setPurposes] = useState({
    kyc_verification: true,
    credit_evaluation: true,
    service_activation: true,
  });

  const [agreedToNotice, setAgreedToNotice] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const togglePurpose = (key: keyof typeof purposes) => {
    // kyc_verification is mandatory
    if (key === "kyc_verification") return;
    setPurposes((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  // Mutation to record consent and create case
  const consentMutation = useMutation({
    mutationFn: async () => {
      if (!leadId) {
        throw new Error("Missing leadId. Please start from the beginning.");
      }
      if (!quoteId) {
        throw new Error("Missing quoteId. Please configure your quote first.");
      }

      // 1. Record DPDP consent
      await api.recordConsent(leadId, "KYC_VERIFICATION", i18n.language || "en");

      // 2. Initialize KYC case
      const kycCase = await api.createKycCase(leadId, quoteId);
      return kycCase;
    },
    onSuccess: (data) => {
      navigate(`/kyc/${data.case_id}?leadId=${leadId}&quoteId=${quoteId}`);
    },
    onError: (err: any) => {
      setErrorMsg(err.detail || err.message || "Failed to record DPDP consent. Please try again.");
    },
  });

  const handleProceed = (e: React.FormEvent) => {
    e.preventDefault();
    if (!agreedToNotice) {
      setErrorMsg("Please read and agree to the Digital Personal Data Protection notice to proceed.");
      return;
    }
    setErrorMsg(null);
    consentMutation.mutate();
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6 py-4">
      {/* Breadcrumb / Step Indicator */}
      <div className="flex items-center space-x-2 text-xs font-semibold text-slate-500">
        <Link to={`/quote/${quoteId}`} className="hover:text-slate-800">
          Quote
        </Link>
        <span>&bull;</span>
        <span className="text-airtel-red">Step 4: DPDP Consent & KYC</span>
      </div>

      {/* Main Card */}
      <div className="bg-white rounded-3xl border border-slate-200/90 shadow-sm p-6 sm:p-8">
        <div className="flex items-start space-x-4 mb-6">
          <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0 border border-emerald-100 shadow-2xs">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <div className="inline-flex items-center space-x-1.5 text-xs font-bold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full mb-1">
              <Lock className="w-3 h-3" />
              <span>DPDP Act 2023 Compliant Notice v1.0</span>
            </div>
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">
              Consent & Privacy Protection
            </h1>
            <p className="text-sm text-slate-600 mt-1">
              Project Udyam Digital verifies your business credentials with strict data sovereignty, explicit consent, and automated purge guarantees.
            </p>
          </div>
        </div>

        {errorMsg && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-2xl flex items-start space-x-3 text-red-800 text-sm mb-6">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
            <div className="font-medium">{errorMsg}</div>
          </div>
        )}

        <form onSubmit={handleProceed} className="space-y-6">
          {/* Statutory Safeguards Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="p-3.5 bg-slate-50 border border-slate-200/80 rounded-2xl">
              <div className="flex items-center space-x-2 text-slate-900 font-bold text-xs mb-1">
                <Lock className="w-4 h-4 text-airtel-red" />
                <span>AES-256 Fernet Encryption</span>
              </div>
              <p className="text-[12px] text-slate-500 leading-relaxed">
                All PII (GSTIN, Udyam, ID documents) is encrypted at rest and masked in memory.
              </p>
            </div>

            <div className="p-3.5 bg-slate-50 border border-slate-200/80 rounded-2xl">
              <div className="flex items-center space-x-2 text-slate-900 font-bold text-xs mb-1">
                <Clock className="w-4 h-4 text-airtel-red" />
                <span>30-Day Auto Retention Purge</span>
              </div>
              <p className="text-[12px] text-slate-500 leading-relaxed">
                Verification documents are permanently purged 30 days after service activation.
              </p>
            </div>
          </div>

          {/* Explicit Purpose Checkboxes */}
          <div className="space-y-3">
            <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Select Authorized Data Processing Purposes
            </div>

            {/* Purpose 1: KYC Verification (Mandatory) */}
            <label className="flex items-start space-x-3 p-4 bg-slate-50 rounded-2xl border border-slate-200 cursor-pointer">
              <input
                type="checkbox"
                checked={purposes.kyc_verification}
                onChange={() => togglePurpose("kyc_verification")}
                className="w-5 h-5 mt-0.5 text-airtel-red rounded border-slate-300 focus:ring-airtel-red"
              />
              <div className="text-xs">
                <div className="font-bold text-slate-900 flex items-center space-x-2">
                  <span>KYC & Business Verification</span>
                  <span className="text-[10px] bg-slate-200 text-slate-700 px-1.5 py-0.2 rounded font-semibold">
                    Mandatory
                  </span>
                </div>
                <div className="text-slate-500 mt-0.5">
                  Authorize Airtel Enterprise to verify business registration (GST/Udyam) and premises validity against government registries.
                </div>
              </div>
            </label>

            {/* Purpose 2: Service Activation */}
            <label className="flex items-start space-x-3 p-4 bg-slate-50 rounded-2xl border border-slate-200 cursor-pointer">
              <input
                type="checkbox"
                checked={purposes.service_activation}
                onChange={() => togglePurpose("service_activation")}
                className="w-5 h-5 mt-0.5 text-airtel-red rounded border-slate-300 focus:ring-airtel-red"
              />
              <div className="text-xs">
                <div className="font-bold text-slate-900">Digital Service Activation & Feasibility</div>
                <div className="text-slate-500 mt-0.5">
                  Authorize network engineering teams to assess fibre/AirFiber feasibility and dispatch technicians to your enterprise location.
                </div>
              </div>
            </label>

            {/* Purpose 3: Credit Evaluation */}
            <label className="flex items-start space-x-3 p-4 bg-slate-50 rounded-2xl border border-slate-200 cursor-pointer">
              <input
                type="checkbox"
                checked={purposes.credit_evaluation}
                onChange={() => togglePurpose("credit_evaluation")}
                className="w-5 h-5 mt-0.5 text-airtel-red rounded border-slate-300 focus:ring-airtel-red"
              />
              <div className="text-xs">
                <div className="font-bold text-slate-900">Commercial Underwriting & Mandate Setup</div>
                <div className="text-slate-500 mt-0.5">
                  Allow credit risk scoring and configuration of monthly autopay mandates for uninterrupted corporate connectivity.
                </div>
              </div>
            </label>
          </div>

          {/* Statutory Declaration Checkbox */}
          <div className="pt-2">
            <label className="flex items-start space-x-3 p-4 bg-airtel-lightred/30 border border-airtel-red/20 rounded-2xl cursor-pointer">
              <input
                type="checkbox"
                checked={agreedToNotice}
                onChange={(e) => setAgreedToNotice(e.target.checked)}
                className="w-5 h-5 mt-0.5 text-airtel-red rounded border-red-300 focus:ring-airtel-red"
              />
              <div className="text-xs leading-relaxed text-slate-800">
                <span className="font-bold text-slate-950">Statutory Consent Declaration: </span>
                I hereby declare that I am the authorized representative of this enterprise and freely grant consent to Airtel Enterprise to process my business documents in accordance with the Digital Personal Data Protection Act, 2023. I understand I may withdraw this consent at any time via my account dashboard.
              </div>
            </label>
          </div>

          {/* Action Button */}
          <button
            type="submit"
            disabled={!agreedToNotice || consentMutation.isPending}
            className="w-full h-14 bg-airtel-red hover:bg-airtel-darkred disabled:bg-slate-300 disabled:cursor-not-allowed text-white font-bold text-base rounded-2xl shadow-md transition-all flex items-center justify-center space-x-2 tap-target"
          >
            {consentMutation.isPending ? (
              <span>Recording DPDP Consent...</span>
            ) : (
              <>
                <span>I Consent & Proceed to KYC</span>
                <ArrowRight className="w-5 h-5" />
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
};
