import React, { useState, useEffect, useRef } from "react";
import { useParams, useSearchParams, useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ShieldCheck,
  Upload,
  Camera,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  FileText,
  Search,
  Sparkles,
  ArrowRight,
  RefreshCw,
  Building,
  Eye,
  Info,
  Clock,
  Layers,
  Check,
} from "lucide-react";
import { api } from "../api/client";
import { KycCase, KycVerifyResponse } from "../api/types";

const GSTIN_REGEX = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;
const UDYAM_REGEX = /^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$/;

interface SlotConfig {
  slot: string;
  label: string;
  description: string;
  required: boolean;
}

const DOCUMENT_SLOTS: SlotConfig[] = [
  {
    slot: "gst_certificate",
    label: "GST Registration Certificate",
    description: "Form GST REG-06 showing legal entity name, trade name, and active status.",
    required: true,
  },
  {
    slot: "udyam_certificate",
    label: "Udyam Registration Certificate",
    description: "Ministry of MSME certificate showing enterprise classification and Udyam number.",
    required: false,
  },
  {
    slot: "address_proof",
    label: "Premises Electricity / Utility Bill",
    description: "Recent utility bill (dated within last 90 days) matching business installation address.",
    required: true,
  },
  {
    slot: "signatory_id",
    label: "Authorized Signatory PAN / Aadhaar",
    description: "Government-issued identity proof of authorized proprietor or company director.",
    required: true,
  },
];

export const KycPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useTranslation();

  const leadId = searchParams.get("leadId") || "";
  const quoteId = searchParams.get("quoteId") || "";

  // Identifier state
  const [gstinInput, setGstinInput] = useState("");
  const [udyamInput, setUdyamInput] = useState("");
  const [registryGstinData, setRegistryGstinData] = useState<any | null>(null);
  const [registryUdyamData, setRegistryUdyamData] = useState<any | null>(null);
  const [registryError, setRegistryError] = useState<string | null>(null);

  // Verification result state
  const [verifyResult, setVerifyResult] = useState<KycVerifyResponse | null>(null);
  const [uploadProgress, setUploadProgress] = useState<Record<string, boolean>>({});

  // 1. Fetch KYC Case data
  const {
    data: kycCase,
    isLoading: caseLoading,
    refetch: refetchCase,
  } = useQuery({
    queryKey: ["kyc-case", caseId],
    queryFn: () => api.getKycCase(caseId!),
    enabled: !!caseId,
  });

  // 2. Fetch Test Specimens for quick evaluation demo
  const { data: specimens } = useQuery({
    queryKey: ["kyc-specimens"],
    queryFn: () => api.getSpecimens(),
  });

  // Set initial identifiers if case has them
  useEffect(() => {
    if (kycCase?.gstin_masked && !gstinInput) {
      setGstinInput(kycCase.gstin_masked);
    }
  }, [kycCase]);

  // Registry Lookup Mutation
  const registryLookupMutation = useMutation({
    mutationFn: async () => {
      setRegistryError(null);
      let gData = null;
      let uData = null;

      if (gstinInput && GSTIN_REGEX.test(gstinInput.trim().toUpperCase())) {
        try {
          gData = await api.lookupGstin(gstinInput.trim().toUpperCase());
          setRegistryGstinData(gData);
        } catch (e: any) {
          setRegistryError(`GSTIN not found in sandbox registry: ${gstinInput}`);
        }
      }

      if (udyamInput && UDYAM_REGEX.test(udyamInput.trim().toUpperCase())) {
        try {
          uData = await api.lookupUdyam(udyamInput.trim().toUpperCase());
          setRegistryUdyamData(uData);
        } catch (e: any) {
          setRegistryError((prev) => (prev ? `${prev} | ` : "") + `Udyam not found: ${udyamInput}`);
        }
      }

      return { gData, uData };
    },
  });

  // Upload Mutation
  const uploadDocMutation = useMutation({
    mutationFn: async ({ slot, file }: { slot: string; file: File }) => {
      setUploadProgress((prev) => ({ ...prev, [slot]: true }));
      return await api.uploadKycDocument(caseId!, slot, file);
    },
    onSuccess: (_, variables) => {
      setUploadProgress((prev) => ({ ...prev, [variables.slot]: false }));
      refetchCase();
    },
    onError: (_, variables) => {
      setUploadProgress((prev) => ({ ...prev, [variables.slot]: false }));
    },
  });

  // Verification Mutation
  const verifyMutation = useMutation({
    mutationFn: async () => {
      const res = await api.verifyKycCase(caseId!);
      return res;
    },
    onSuccess: (data) => {
      setVerifyResult(data);
      refetchCase();
    },
  });

  // Apply Specimen Quick-Loader Mutation
  const applySpecimenMutation = useMutation({
    mutationFn: async (code: string) => {
      await api.applySpecimen(caseId!, code);
      // Auto-run verification right after applying
      const v = await api.verifyKycCase(caseId!);
      return { code, v };
    },
    onSuccess: (data) => {
      setVerifyResult(data.v);
      refetchCase();
    },
  });

  const handleFileUpload = (slot: string, e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      uploadDocMutation.mutate({ slot, file });
    }
  };

  // Find document status for slot
  const getDocForSlot = (slot: string) => {
    return kycCase?.documents?.find((d) => d.slot === slot);
  };

  const isVerifiedPass = (kycCase?.verdict === "PASS") || (verifyResult?.verdict === "PASS");

  return (
    <div className="max-w-4xl mx-auto space-y-6 py-4">
      {/* Breadcrumb */}
      <div className="flex items-center space-x-2 text-xs font-semibold text-slate-500">
        <Link to={`/quote/${quoteId}`} className="hover:text-slate-800">
          Quote
        </Link>
        <span>&bull;</span>
        <Link to={`/consent?leadId=${leadId}&quoteId=${quoteId}`} className="hover:text-slate-800">
          Consent
        </Link>
        <span>&bull;</span>
        <span className="text-airtel-red">Step 4: Smart KYC & Document Verification</span>
      </div>

      {/* Floating Demo Specimen Quick-Loader */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-3xl p-5 text-white shadow-lg border border-indigo-900/40">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-amber-400" />
            <span className="font-black text-sm uppercase tracking-wider text-amber-300">
              Hackathon Judge Demo: 1-Click Specimen Auto-Loader
            </span>
          </div>
          <span className="text-xs text-slate-300">
            Instantly load any of the 12 benchmark specimen applicants (K01-K12)
          </span>
        </div>

        <div className="flex flex-wrap gap-2">
          {specimens?.map((spec) => (
            <button
              key={spec.code}
              type="button"
              disabled={applySpecimenMutation.isPending}
              onClick={() => applySpecimenMutation.mutate(spec.code)}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 border ${
                spec.expected === "PASS"
                  ? "bg-emerald-950/70 border-emerald-500/50 hover:bg-emerald-800/80 text-emerald-200"
                  : "bg-amber-950/70 border-amber-500/50 hover:bg-amber-800/80 text-amber-200"
              }`}
            >
              <span>{spec.code}</span>
              <span className="text-[10px] opacity-75">
                ({spec.expected === "PASS" ? "Clean Pass" : spec.label.split(":")[1]?.trim().slice(0, 16) + "..."})
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* 1. Enter-Then-Verify Identifiers Card */}
      <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
              <Building className="w-5 h-5 text-airtel-red" />
              <span>1. Enter-Then-Verify Enterprise Identifiers</span>
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Validate your 15-character GSTIN or 19-character Udyam number against government sandbox registries.
            </p>
          </div>
        </div>

        {registryError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-800 mb-4 font-medium flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{registryError}</span>
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
          {/* GSTIN Input */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
              Goods & Services Tax ID (GSTIN)
            </label>
            <input
              type="text"
              value={gstinInput}
              onChange={(e) => setGstinInput(e.target.value.toUpperCase())}
              placeholder="e.g. 27XUIXG0767D1ZP"
              className="w-full h-12 px-4 rounded-xl border border-slate-300 font-mono text-sm tracking-wider uppercase focus:outline-none focus:ring-2 focus:ring-airtel-red"
            />
          </div>

          {/* Udyam Input */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
              Udyam Registration Number (Optional)
            </label>
            <input
              type="text"
              value={udyamInput}
              onChange={(e) => setUdyamInput(e.target.value.toUpperCase())}
              placeholder="e.g. UDYAM-MH-01-0012345"
              className="w-full h-12 px-4 rounded-xl border border-slate-300 font-mono text-sm tracking-wider uppercase focus:outline-none focus:ring-2 focus:ring-airtel-red"
            />
          </div>
        </div>

        <button
          type="button"
          onClick={() => registryLookupMutation.mutate()}
          disabled={registryLookupMutation.isPending || (!gstinInput && !udyamInput)}
          className="inline-flex items-center space-x-2 bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs px-5 py-3 rounded-xl transition-all shadow-xs tap-target"
        >
          <Search className="w-3.5 h-3.5" />
          <span>
            {registryLookupMutation.isPending ? "Querying Sandbox Registry..." : "Verify in Sandbox Registry"}
          </span>
        </button>

        {/* Pre-fill Registry Result Card */}
        {registryGstinData && (
          <div className="mt-4 p-4 bg-emerald-50 border border-emerald-200 rounded-2xl">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2 text-emerald-800 font-bold text-xs">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>GSTIN Registry Record Verified: Active</span>
              </div>
              <span className="text-[11px] font-mono text-emerald-700 font-bold">
                {registryGstinData.gstin}
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-slate-700">
              <div>
                <span className="text-slate-400">Legal Name: </span>
                <span className="font-bold">{registryGstinData.legal_name}</span>
              </div>
              <div>
                <span className="text-slate-400">Trade Name: </span>
                <span className="font-bold">{registryGstinData.trade_name}</span>
              </div>
              <div className="sm:col-span-2">
                <span className="text-slate-400">Registered Premises: </span>
                <span className="font-bold">{registryGstinData.address}, {registryGstinData.city} - {registryGstinData.pincode}</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 2. Document Upload Slots Grid */}
      <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-6">
        <div className="mb-4">
          <h2 className="text-xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <FileText className="w-5 h-5 text-airtel-red" />
            <span>2. Upload Verification Documents</span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Capture or upload required business proofs. Automatic OpenCV deskewing, blur detection, and OCR extraction are executed instantly.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {DOCUMENT_SLOTS.map((slotCfg) => {
            const doc = getDocForSlot(slotCfg.slot);
            const isUploading = uploadProgress[slotCfg.slot];

            return (
              <div
                key={slotCfg.slot}
                className={`p-4 rounded-2xl border transition-all ${
                  doc
                    ? "bg-slate-50/70 border-slate-300"
                    : slotCfg.required
                    ? "bg-white border-dashed border-slate-300 hover:border-airtel-red/40"
                    : "bg-slate-50/40 border-dashed border-slate-200"
                }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <div className="flex items-center space-x-1.5">
                      <span className="font-bold text-slate-900 text-sm">{slotCfg.label}</span>
                      {slotCfg.required ? (
                        <span className="text-[10px] bg-red-100 text-red-700 font-bold px-1.5 py-0.2 rounded">
                          Required
                        </span>
                      ) : (
                        <span className="text-[10px] bg-slate-100 text-slate-600 font-medium px-1.5 py-0.2 rounded">
                          Optional
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">
                      {slotCfg.description}
                    </p>
                  </div>
                </div>

                {/* Uploaded State Preview */}
                {doc ? (
                  <div className="mt-3 p-3 bg-white border border-slate-200 rounded-xl space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center space-x-2 text-emerald-700 font-bold">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                        <span>Uploaded & Processed</span>
                      </div>
                      {doc.view_url && (
                        <a
                          href={doc.view_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-airtel-red hover:underline text-[11px] font-bold flex items-center space-x-1"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          <span>View Doc</span>
                        </a>
                      )}
                    </div>

                    {/* OpenCV Quality Metrics */}
                    <div className="flex items-center space-x-3 text-[10px] font-mono text-slate-500 pt-1 border-t border-slate-100">
                      <span>Blur: {Math.round(doc.quality?.laplacian_var || 0)}</span>
                      <span>&bull;</span>
                      <span>Skew: {Math.round(doc.quality?.skew_angle || 0)}&deg;</span>
                      <span>&bull;</span>
                      <span>Glare: {Math.round(doc.quality?.glare_score || 0)}%</span>
                    </div>
                  </div>
                ) : (
                  <div className="mt-3 flex items-center gap-2">
                    <label className="flex-1 h-11 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs rounded-xl flex items-center justify-center space-x-1.5 cursor-pointer tap-target transition-all">
                      <Upload className="w-3.5 h-3.5" />
                      <span>{isUploading ? "Uploading..." : "Choose File"}</span>
                      <input
                        type="file"
                        accept="image/*,application/pdf"
                        onChange={(e) => handleFileUpload(slotCfg.slot, e)}
                        className="hidden"
                        disabled={isUploading}
                      />
                    </label>

                    <label className="w-11 h-11 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl flex items-center justify-center cursor-pointer tap-target transition-all">
                      <Camera className="w-4 h-4" />
                      <input
                        type="file"
                        accept="image/*"
                        capture="environment"
                        onChange={(e) => handleFileUpload(slotCfg.slot, e)}
                        className="hidden"
                        disabled={isUploading}
                      />
                    </label>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 3. Run Smart Verification Card */}
      <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
              <ShieldCheck className="w-5 h-5 text-airtel-red" />
              <span>3. Deterministic KYC Evaluation</span>
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Executes the 7-stage quality and registry matching pipeline across all uploaded documents.
            </p>
          </div>

          <button
            type="button"
            onClick={() => verifyMutation.mutate()}
            disabled={verifyMutation.isPending}
            className="h-12 px-6 bg-airtel-red hover:bg-airtel-darkred text-white font-bold text-sm rounded-xl transition-all shadow-md flex items-center justify-center space-x-2 tap-target"
          >
            <RefreshCw className={`w-4 h-4 ${verifyMutation.isPending ? "animate-spin" : ""}`} />
            <span>{verifyMutation.isPending ? "Evaluating Pipeline..." : "Run Smart Verification"}</span>
          </button>
        </div>

        {/* Verdict Banner */}
        {(verifyResult || kycCase?.verdict) && (
          <div
            className={`p-5 rounded-2xl border ${
              (verifyResult?.verdict || kycCase?.verdict) === "PASS"
                ? "bg-emerald-50 border-emerald-200 text-emerald-950"
                : (verifyResult?.verdict || kycCase?.verdict) === "NEEDS_FIX"
                ? "bg-amber-50 border-amber-200 text-amber-950"
                : "bg-blue-50 border-blue-200 text-blue-950"
            }`}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-2 font-black text-base">
                {(verifyResult?.verdict || kycCase?.verdict) === "PASS" ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                ) : (
                  <AlertTriangle className="w-5 h-5 text-amber-600" />
                )}
                <span>Verdict: {verifyResult?.verdict || kycCase?.verdict}</span>
              </div>

              {verifyResult && (
                <div className="text-xs font-bold font-mono">
                  {verifyResult.checks_passed} / {verifyResult.total_checks} Checks Passed
                </div>
              )}
            </div>

            {/* Actionable Fix Guidance */}
            {verifyResult?.fix_messages && verifyResult.fix_messages.length > 0 && (
              <div className="space-y-1.5 mt-2 pt-2 border-t border-amber-200/60">
                <div className="text-xs font-bold uppercase tracking-wider text-amber-800">
                  Required Corrections:
                </div>
                {verifyResult.fix_messages.map((fix, idx) => (
                  <div key={idx} className="flex items-start space-x-2 text-xs text-amber-900 font-medium">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-600 mt-1.5 shrink-0" />
                    <span>{fix}</span>
                  </div>
                ))}

                {/* If Cancelled GSTIN (e.g. K01), offer 1-tap quote amendment button */}
                {verifyResult.fix_messages.some((m) => m.toLowerCase().includes("cancelled") || m.toLowerCase().includes("gstin")) && (
                  <div className="pt-2">
                    <Link
                      to={`/quote/${quoteId}?gstin_invalid=true`}
                      className="inline-flex items-center space-x-1.5 bg-amber-800 hover:bg-amber-900 text-white font-bold text-xs px-4 py-2.5 rounded-xl shadow-xs transition-all"
                    >
                      <span>Downgrade to Consumer Tier & Amend Quote</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Detailed Checks Breakdown */}
        {kycCase?.checks && kycCase.checks.length > 0 && (
          <div className="space-y-2 pt-2">
            <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Deterministic Inspection Checks:
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {kycCase.checks.map((chk, i) => (
                <div
                  key={i}
                  className={`p-3 rounded-xl border flex items-center justify-between text-xs ${
                    chk.outcome === "PASS"
                      ? "bg-slate-50 border-slate-200 text-slate-800"
                      : "bg-red-50/70 border-red-200 text-red-900"
                  }`}
                >
                  <div className="font-mono font-bold">{chk.check_code}</div>
                  <div
                    className={`font-bold px-2 py-0.5 rounded text-[10px] ${
                      chk.outcome === "PASS"
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-red-100 text-red-800"
                    }`}
                  >
                    {chk.outcome}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Next Step CTA */}
      <div className="p-4 bg-white rounded-3xl border border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <div className="font-bold text-slate-900 text-sm">Next Step: Contract Signing & Mandate</div>
          <div className="text-xs text-slate-500">
            {isVerifiedPass
              ? "All KYC checks verified successfully! Proceed to digital signing."
              : "Complete KYC verification to unlock agreement signing."}
          </div>
        </div>

        <Link
          to={`/sign/${quoteId}?leadId=${leadId}&caseId=${caseId}`}
          className={`h-12 px-6 rounded-xl font-bold text-sm flex items-center space-x-2 transition-all tap-target ${
            isVerifiedPass
              ? "bg-emerald-600 hover:bg-emerald-700 text-white shadow-md active:scale-95"
              : "bg-slate-200 text-slate-400 pointer-events-none"
          }`}
        >
          <span>Proceed to Sign Agreement</span>
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  );
};
