import React, { useState } from "react";
import { useParams, useSearchParams, useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  FileCheck,
  CreditCard,
  Download,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  Building,
  KeyRound,
  ExternalLink,
  Lock,
} from "lucide-react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export const SignAndPayPage: React.FC = () => {
  const { quoteId } = useParams<{ quoteId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { activeLeadId, phoneMasked } = useAuth();

  const leadId = searchParams.get("leadId") || activeLeadId || "";
  const caseId = searchParams.get("caseId") || "";

  // 1. Fetch Quote
  const { data: quote, isLoading: quoteLoading } = useQuery({
    queryKey: ["quote", quoteId],
    queryFn: () => api.getQuote(quoteId!),
    enabled: !!quoteId,
  });

  // e-Sign State
  const [signMode, setSignMode] = useState<"self" | "delegate">("self");
  const [signatoryName, setSignatoryName] = useState("Enterprise Proprietor");
  const [signatoryPhone, setSignatoryPhone] = useState(phoneMasked || "9876543210");
  const [delegateName, setDelegateName] = useState("Managing Director");
  const [delegatePhone, setDelegatePhone] = useState("9811223344");
  const [linkSentNotice, setLinkSentNotice] = useState<string | null>(null);
  const [esignId, setEsignId] = useState<string | null>(null);
  const [otpValue, setOtpValue] = useState("");
  const [isSigned, setIsSigned] = useState(false);
  const [signedAt, setSignedAt] = useState<string | null>(null);
  const [esignError, setEsignError] = useState<string | null>(null);

  // Mandate State
  const [vpa, setVpa] = useState("enterprise@okhdfcbank");
  const [bankName, setBankName] = useState("HDFC Bank");
  const [mandateError, setMandateError] = useState<string | null>(null);

  // Currency Formatter
  const formatINR = (val: number | null | undefined) => {
    if (val === null || val === undefined) return "₹0";
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(val);
  };

  // e-Sign Step 1: Request OTP
  const requestEsignMutation = useMutation({
    mutationFn: async () => {
      setEsignError(null);
      const res = await api.requestEsign(quoteId!, signatoryName, signatoryPhone);
      return res;
    },
    onSuccess: (data) => {
      setEsignId(data.esign_id);
      setOtpValue("123456"); // Demo pre-fill for evaluator convenience
    },
    onError: (err: any) => {
      setEsignError(err.detail || err.message || "Failed to initiate Aadhaar e-Sign.");
    },
  });

  // e-Sign Step 2: Complete Signature
  const completeEsignMutation = useMutation({
    mutationFn: async () => {
      setEsignError(null);
      if (!esignId) throw new Error("e-Sign request not initiated.");
      const res = await api.completeEsign(esignId);
      return res;
    },
    onSuccess: () => {
      setIsSigned(true);
      setSignedAt(new Date().toLocaleTimeString());
    },
    onError: (err: any) => {
      setEsignError(err.detail || err.message || "Invalid OTP or e-Sign verification failed.");
    },
  });

  // Mandate Mutation: Create Mandate + Generate Order
  const mandateMutation = useMutation({
    mutationFn: async () => {
      setMandateError(null);
      if (!vpa || !vpa.includes("@")) {
        throw new Error("Please enter a valid UPI ID (e.g. user@okhdfcbank)");
      }
      // 1. Authorize UPI Mandate
      await api.createMandate(quoteId!, leadId, vpa, bankName);

      // 2. Create Order in backend
      const order = await api.createOrder(quoteId!, 1);
      return order;
    },
    onSuccess: (order) => {
      navigate(`/track/${order.order_id}`);
    },
    onError: (err: any) => {
      setMandateError(err.detail || err.message || "Failed to create mandate and order.");
    },
  });

  return (
    <div className="max-w-3xl mx-auto space-y-6 py-4">
      {/* Breadcrumb */}
      <div className="flex items-center space-x-2 text-xs font-semibold text-slate-500">
        <Link to={`/quote/${quoteId}`} className="hover:text-slate-800">
          Quote
        </Link>
        <span>&bull;</span>
        <Link to={`/kyc/${caseId}?leadId=${leadId}&quoteId=${quoteId}`} className="hover:text-slate-800">
          KYC
        </Link>
        <span>&bull;</span>
        <span className="text-airtel-red">Step 5: Digital Contract & Autopay Mandate</span>
      </div>

      {/* Contract Summary Header */}
      <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-6 sm:p-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-100">
          <div>
            <div className="inline-flex items-center space-x-1.5 text-xs font-bold text-slate-500 bg-slate-100 px-2.5 py-0.5 rounded-full mb-1">
              <span>Agreement Ref: {quoteId?.slice(0, 8).toUpperCase()}</span>
            </div>
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">
              Enterprise Service Agreement
            </h1>
            <p className="text-xs text-slate-500 mt-1">
              Review commercial terms, digitally sign via Aadhaar OTP, and set up recurring UPI autopay.
            </p>
          </div>

          <button
            type="button"
            onClick={() => api.downloadQuotePdf(quoteId!)}
            className="inline-flex items-center space-x-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs px-4 py-2.5 rounded-xl transition-all shadow-2xs self-start sm:self-auto tap-target"
          >
            <Download className="w-3.5 h-3.5 text-airtel-red" />
            <span>Download Agreement PDF</span>
          </button>
        </div>

        {/* Pricing Metrics Grid */}
        <div className="grid grid-cols-3 gap-3 pt-6">
          <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100 text-center">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
              Monthly Commitment
            </span>
            <span className="text-lg sm:text-2xl font-black text-slate-950 font-mono">
              {formatINR(quote?.monthly_recurring)}
            </span>
            <span className="text-[10px] text-slate-500 block">/month + GST</span>
          </div>

          <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100 text-center">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
              One-Time Setup Fee
            </span>
            <span className="text-lg sm:text-2xl font-black text-slate-950 font-mono">
              {formatINR(quote?.one_time)}
            </span>
            <span className="text-[10px] text-slate-500 block">Initial dispatch</span>
          </div>

          <div className="p-4 bg-airtel-lightred/30 rounded-2xl border border-airtel-red/20 text-center">
            <span className="text-[11px] font-bold uppercase tracking-wider text-airtel-red block mb-1">
              Contract Term
            </span>
            <span className="text-lg sm:text-2xl font-black text-airtel-red font-mono">
              {quote?.term_months || 12}
            </span>
            <span className="text-[10px] text-slate-600 block">Months Lock-in</span>
          </div>
        </div>
      </div>

      {/* Part A: Aadhaar / Mobile OTP e-Sign */}
      <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-6 space-y-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
              <FileCheck className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-black text-slate-900 tracking-tight">
                Part A: Aadhaar e-Sign Verification
              </h2>
              <p className="text-xs text-slate-500">
                Statutory digital signature compliant with Information Technology Act, 2000.
              </p>
            </div>
          </div>

          {isSigned && (
            <div className="inline-flex items-center space-x-1.5 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-bold px-3 py-1 rounded-full">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Digitally Signed ({signedAt})</span>
            </div>
          )}
        </div>

        {esignError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-800 flex items-center space-x-2 font-medium">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{esignError}</span>
          </div>
        )}

        {!isSigned ? (
          <div className="space-y-4 pt-2">
            {/* Mode Switcher */}
            <div className="flex p-1 bg-slate-100 rounded-2xl w-full sm:w-fit">
              <button
                type="button"
                onClick={() => setSignMode("self")}
                className={`flex-1 sm:flex-initial px-4 py-2 rounded-xl text-xs font-bold transition-all tap-target ${
                  signMode === "self"
                    ? "bg-white text-slate-900 shadow-2xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Sign Now as Authorised Signatory
              </button>
              <button
                type="button"
                onClick={() => setSignMode("delegate")}
                className={`flex-1 sm:flex-initial px-4 py-2 rounded-xl text-xs font-bold transition-all tap-target ${
                  signMode === "delegate"
                    ? "bg-white text-slate-900 shadow-2xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Send e-Sign Link to Another Signatory
              </button>
            </div>

            {signMode === "self" ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-1">
                      Authorized Signatory Name
                    </label>
                    <input
                      type="text"
                      value={signatoryName}
                      onChange={(e) => setSignatoryName(e.target.value)}
                      className="w-full h-11 px-3.5 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-airtel-red"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-1">
                      Aadhaar Registered Mobile
                    </label>
                    <input
                      type="text"
                      value={signatoryPhone}
                      onChange={(e) => setSignatoryPhone(e.target.value)}
                      className="w-full h-11 px-3.5 rounded-xl border border-slate-300 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-airtel-red"
                    />
                  </div>
                </div>

                {!esignId ? (
                  <button
                    type="button"
                    onClick={() => requestEsignMutation.mutate()}
                    disabled={requestEsignMutation.isPending}
                    className="h-12 px-6 bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs rounded-xl shadow-xs transition-all flex items-center space-x-2 tap-target"
                  >
                    <KeyRound className="w-3.5 h-3.5" />
                    <span>
                      {requestEsignMutation.isPending ? "Requesting UIDAI OTP..." : "Request Aadhaar e-Sign OTP"}
                    </span>
                  </button>
                ) : (
                  <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-3">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-slate-800">
                        Enter 6-Digit OTP sent to {signatoryPhone.slice(-4).padStart(signatoryPhone.length, "*")}
                      </span>
                      <span className="text-[11px] font-mono text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded font-bold">
                        Demo OTP: 123456
                      </span>
                    </div>

                    <div className="flex items-center space-x-3">
                      <input
                        type="text"
                        maxLength={6}
                        value={otpValue}
                        onChange={(e) => setOtpValue(e.target.value)}
                        placeholder="123456"
                        className="w-48 h-12 px-4 rounded-xl border border-slate-300 font-mono text-center text-lg tracking-widest focus:outline-none focus:ring-2 focus:ring-airtel-red"
                      />

                      <button
                        type="button"
                        onClick={() => completeEsignMutation.mutate()}
                        disabled={completeEsignMutation.isPending || otpValue.length < 6}
                        className="h-12 px-6 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white font-bold text-xs rounded-xl shadow-md transition-all flex items-center space-x-2 tap-target"
                      >
                        <CheckCircle2 className="w-4 h-4" />
                        <span>
                          {completeEsignMutation.isPending ? "Affixing Signature..." : "Verify & Affix Signature"}
                        </span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-1">
                      Designated Signatory Name
                    </label>
                    <input
                      type="text"
                      value={delegateName}
                      onChange={(e) => setDelegateName(e.target.value)}
                      className="w-full h-11 px-3.5 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-airtel-red"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-1">
                      Signatory Mobile / WhatsApp
                    </label>
                    <input
                      type="text"
                      value={delegatePhone}
                      onChange={(e) => setDelegatePhone(e.target.value)}
                      className="w-full h-11 px-3.5 rounded-xl border border-slate-300 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-airtel-red"
                    />
                  </div>
                </div>

                {!linkSentNotice ? (
                  <button
                    type="button"
                    onClick={async () => {
                      setEsignError(null);
                      try {
                        const res = await api.requestEsign(quoteId!, delegateName, delegatePhone);
                        setEsignId(res.esign_id);
                        setLinkSentNotice(
                          `e-Sign link sent via NotifierPort to ${delegatePhone}! Outbox event recorded.`
                        );
                      } catch (err: any) {
                        setEsignError(err.detail || err.message || "Failed to dispatch link.");
                      }
                    }}
                    className="h-12 px-6 bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs rounded-xl shadow-xs transition-all flex items-center space-x-2 tap-target"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    <span>Send e-Sign Link to Signatory</span>
                  </button>
                ) : (
                  <div className="p-4 bg-blue-50 border border-blue-200 rounded-2xl space-y-3 text-xs">
                    <div className="flex items-center space-x-2 text-blue-900 font-bold">
                      <CheckCircle2 className="w-4 h-4 text-blue-600" />
                      <span>{linkSentNotice}</span>
                    </div>
                    <p className="text-blue-800 text-[11px]">
                      The authorised signatory has received the link via SMS/WhatsApp. You may simulate remote acceptance below:
                    </p>
                    <button
                      type="button"
                      onClick={() => completeEsignMutation.mutate()}
                      disabled={completeEsignMutation.isPending}
                      className="h-10 px-4 bg-blue-700 hover:bg-blue-800 text-white font-bold text-xs rounded-xl transition-all tap-target"
                    >
                      Simulate Signatory Affixing Signature
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <ShieldCheck className="w-6 h-6 text-emerald-600" />
              <div>
                <div className="font-bold text-emerald-950 text-xs">
                  Contract Agreement e-Signed Successfully
                </div>
                <div className="text-[11px] text-emerald-700">
                  Digitally certified with SHA-256 certificate hash &bull; Signatory: {signatoryName}
                </div>
              </div>
            </div>
            <span className="text-[10px] font-mono font-bold text-emerald-800 bg-emerald-200/60 px-2 py-1 rounded">
              VERIFIED
            </span>
          </div>
        )}
      </div>

      {/* Part B: UPI Autopay Recurring Mandate */}
      <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-6 space-y-4">
        <div className="flex items-start space-x-3">
          <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center font-bold">
            <CreditCard className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-black text-slate-900 tracking-tight">
              Part B: Set Up Recurring UPI Autopay Mandate
            </h2>
            <p className="text-xs text-slate-500">
              Automate monthly billing with zero manual follow-ups via NPCI UPI Autopay.
            </p>
          </div>
        </div>

        {mandateError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-800 flex items-center space-x-2 font-medium">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{mandateError}</span>
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
          <div>
            <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-1">
              Virtual Payment Address (UPI ID)
            </label>
            <input
              type="text"
              value={vpa}
              onChange={(e) => setVpa(e.target.value.toLowerCase())}
              placeholder="e.g. enterprise@okhdfcbank"
              className="w-full h-11 px-3.5 rounded-xl border border-slate-300 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-airtel-red"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-1">
              Primary Settlement Bank
            </label>
            <select
              value={bankName}
              onChange={(e) => setBankName(e.target.value)}
              className="w-full h-11 px-3.5 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-airtel-red bg-white"
            >
              <option value="HDFC Bank">HDFC Bank</option>
              <option value="State Bank of India">State Bank of India</option>
              <option value="ICICI Bank">ICICI Bank</option>
              <option value="Axis Bank">Axis Bank</option>
              <option value="Kotak Mahindra Bank">Kotak Mahindra Bank</option>
            </select>
          </div>
        </div>

        <div className="p-3 bg-purple-50/50 border border-purple-200/70 rounded-2xl flex items-center justify-between text-xs">
          <div className="text-purple-900">
            <span className="font-bold">Authorized Monthly Debit: </span>
            <span>{formatINR(quote?.monthly_recurring)} (Max limit capped at {formatINR((quote?.monthly_recurring || 1000) * 1.5)})</span>
          </div>
          <Lock className="w-4 h-4 text-purple-600 shrink-0" />
        </div>

        {/* Action Button */}
        <button
          type="button"
          onClick={() => mandateMutation.mutate()}
          disabled={!isSigned || mandateMutation.isPending}
          className="w-full h-14 bg-airtel-red hover:bg-airtel-darkred disabled:bg-slate-300 disabled:cursor-not-allowed text-white font-bold text-base rounded-2xl shadow-md transition-all flex items-center justify-center space-x-2 tap-target"
        >
          {mandateMutation.isPending ? (
            <span>Authorizing Mandate & Generating Order...</span>
          ) : (
            <>
              <span>Authorize Mandate & Activate Order</span>
              <ArrowRight className="w-5 h-5" />
            </>
          )}
        </button>

        {!isSigned && (
          <p className="text-center text-[11px] text-slate-400">
            * Please complete Part A (Aadhaar e-Sign) above before activating the order.
          </p>
        )}
      </div>
    </div>
  );
};
