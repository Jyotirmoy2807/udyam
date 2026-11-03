import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ShieldCheck,
  FileCheck,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Eye,
  Building,
  Calendar,
  MapPin,
  FileText,
  UserCheck,
  Check,
  X,
  Sparkles,
} from "lucide-react";
import { api } from "../api/client";
import { KycReviewCase } from "../api/types";

export const OpsKycReviewPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedCase, setSelectedCase] = useState<KycReviewCase | null>(null);
  const [decisionReason, setDecisionReason] = useState<string>("");
  const [supervisorEmail, setSupervisorEmail] = useState<string>("supervisor@airtel.com");

  // Fetch KYC Cases
  const { data: cases, isLoading } = useQuery({
    queryKey: ["ops-kyc-cases"],
    queryFn: () => api.getKycReviewCases(),
  });

  // Decision Mutation
  const decisionMutation = useMutation({
    mutationFn: ({
      caseId,
      decision,
      reason,
      actor,
    }: {
      caseId: string;
      decision: "APPROVE" | "REJECT";
      reason: string;
      actor: string;
    }) => api.decideKycReviewCase(caseId, decision, reason, actor),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["ops-kyc-cases"] });
      alert(`KYC Case verdict successfully updated to ${data.verdict}!`);
      setDecisionReason("");
      setSelectedCase(null);
    },
    onError: (err: any) => {
      alert(`Failed to record decision: ${err.detail || err.message}`);
    },
  });

  const getVerdictBadge = (verdict: string) => {
    switch (verdict) {
      case "PASS":
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            <span>APPROVED</span>
          </span>
        );
      case "MANUAL_REVIEW":
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-purple-100 text-purple-800 border border-purple-200">
            <AlertCircle className="w-3 h-3 text-purple-600" />
            <span>MANUAL REVIEW</span>
          </span>
        );
      case "NEEDS_FIX":
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-200">
            <XCircle className="w-3 h-3 text-amber-600" />
            <span>NEEDS FIX</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-700 border border-slate-200">
            <span>PENDING</span>
          </span>
        );
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-10">
      {/* Header */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-purple-700 bg-purple-50 px-3 py-1 rounded-full mb-2">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Statutory Compliance & Review</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900">
            KYC Supervisor Review & Override
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Manual exception desk with OCR document inspection, National GSTN & Udyam registry cross-checks, and immutable audit logs.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <Link
            to="/ops/leads"
            className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold rounded-xl transition-colors"
          >
            Lead Queue
          </Link>
          <Link
            to="/ops/funnel"
            className="px-4 py-2 bg-airtel-red hover:bg-airtel-darkred text-white text-xs font-bold rounded-xl shadow-sm transition-colors"
          >
            Conversion Funnel
          </Link>
        </div>
      </div>

      {/* Main Grid: Cases List & Inspection Pane */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Cases List (1 col) */}
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs font-bold text-slate-600 px-1">
            <span>Pending & Exception Cases</span>
            <span>{cases ? `${cases.length} cases` : "Loading..."}</span>
          </div>

          {isLoading ? (
            <div className="bg-white rounded-2xl p-8 text-center border border-slate-200">
              <div className="inline-block w-6 h-6 border-3 border-purple-600 border-t-transparent rounded-full animate-spin mb-2" />
              <p className="text-xs font-semibold text-slate-500">Loading cases...</p>
            </div>
          ) : cases && cases.length > 0 ? (
            cases.map((c) => (
              <div
                key={c.case_id}
                onClick={() => setSelectedCase(c)}
                className={`bg-white rounded-xl p-4 border transition-all cursor-pointer shadow-sm hover:shadow-md ${
                  selectedCase?.case_id === c.case_id
                    ? "border-purple-600 ring-1 ring-purple-600 bg-purple-50/20"
                    : "border-slate-200 hover:border-slate-300"
                }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <span className="font-mono text-xs font-bold text-slate-800 bg-slate-100 px-2 py-0.5 rounded">
                    #{c.case_id.slice(0, 8).toUpperCase()}
                  </span>
                  {getVerdictBadge(c.verdict)}
                </div>

                <div className="text-xs space-y-1 text-slate-600">
                  <div className="font-semibold text-slate-900 truncate">
                    {c.registry?.trade_name || c.business_name}
                  </div>
                  <div className="flex items-center justify-between text-slate-500">
                    <span>GSTIN: {c.registry?.identifier || "None"}</span>
                    <span>{c.phone_masked}</span>
                  </div>
                </div>

                <div className="mt-3 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
                  <span>{c.documents.length} docs &bull; {c.checks.length} checks</span>
                  <span className="font-medium text-purple-700">Inspect &rarr;</span>
                </div>
              </div>
            ))
          ) : (
            <div className="bg-white rounded-2xl p-8 text-center border border-slate-200 text-slate-500">
              <CheckCircle2 className="w-8 h-8 mx-auto text-emerald-500 mb-2" />
              <p className="font-bold text-slate-700 text-sm">No Pending KYC Reviews</p>
              <p className="text-xs text-slate-400 mt-1">All digital customer cases have been verified automatically.</p>
            </div>
          )}
        </div>

        {/* Case Inspection View (2 cols) */}
        <div className="lg:col-span-2">
          {selectedCase ? (
            <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-6">
              {/* Case Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-slate-100">
                <div>
                  <div className="flex items-center space-x-2">
                    <h2 className="text-xl font-black text-slate-900">
                      {selectedCase.registry?.trade_name || selectedCase.business_name}
                    </h2>
                    {getVerdictBadge(selectedCase.verdict)}
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5 font-mono">
                    Case ID: {selectedCase.case_id} &bull; Lead: #{selectedCase.lead_id.slice(0, 8)}
                  </p>
                </div>
                <div className="text-right">
                  <span className="text-xs text-slate-400 block">Retry Attempts</span>
                  <span className="font-bold text-slate-800 text-sm">
                    {selectedCase.retry_count} of 3 max
                  </span>
                </div>
              </div>

              {/* Side-by-Side: Official Registry Truth vs Extracted Application */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Official Registry Card */}
                <div className="bg-emerald-50/50 p-4 rounded-xl border border-emerald-100 space-y-2">
                  <div className="flex items-center space-x-1.5 text-xs font-bold text-emerald-900 uppercase">
                    <Building className="w-3.5 h-3.5 text-emerald-700" />
                    <span>Official National Registry Record</span>
                  </div>
                  {selectedCase.registry ? (
                    <div className="space-y-1.5 text-xs">
                      <div>
                        <span className="text-slate-400 block text-[10px]">Source & Identifier:</span>
                        <span className="font-mono font-bold text-slate-900">
                          {selectedCase.registry.source}: {selectedCase.registry.identifier}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">Legal Name:</span>
                        <span className="font-semibold text-slate-800">{selectedCase.registry.legal_name}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">Trade Name:</span>
                        <span className="font-semibold text-slate-800">{selectedCase.registry.trade_name}</span>
                      </div>
                      <div className="flex items-center justify-between pt-1">
                        <span className="text-slate-500">Registry Status:</span>
                        <span
                          className={`font-bold px-2 py-0.5 rounded text-[11px] ${
                            selectedCase.registry.status.toLowerCase() === "active"
                              ? "bg-emerald-100 text-emerald-800"
                              : "bg-red-100 text-red-800"
                          }`}
                        >
                          {selectedCase.registry.status}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-500">State & Pincode:</span>
                        <span className="font-semibold text-slate-800">
                          {selectedCase.registry.state} &bull; {selectedCase.registry.pincode}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="text-xs text-slate-500 italic py-2">
                      No matching record in GSTN or Udyam registry (Exempt bundle or unregistered).
                    </div>
                  )}
                </div>

                {/* Validation Checks Card */}
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2">
                  <div className="flex items-center space-x-1.5 text-xs font-bold text-slate-800 uppercase">
                    <FileCheck className="w-3.5 h-3.5 text-airtel-red" />
                    <span>Automated Rule Checks ({selectedCase.checks.length})</span>
                  </div>
                  <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                    {selectedCase.checks.map((chk) => (
                      <div
                        key={chk.id}
                        className="bg-white p-2 rounded-lg border border-slate-200/80 text-xs flex items-center justify-between"
                      >
                        <div>
                          <span className="font-bold text-slate-800 block text-[11px]">
                            {chk.name}
                          </span>
                          {chk.score !== null && (
                            <span className="text-[10px] text-slate-500 font-mono">
                              Similarity: {(chk.score * 100).toFixed(0)}%
                            </span>
                          )}
                        </div>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            chk.outcome === "PASS"
                              ? "bg-emerald-100 text-emerald-800"
                              : chk.outcome === "WARN"
                              ? "bg-amber-100 text-amber-800"
                              : "bg-red-100 text-red-800"
                          }`}
                        >
                          {chk.outcome}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Uploaded Documents with Presigned URLs */}
              <div className="space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center space-x-1.5">
                  <FileText className="w-4 h-4 text-slate-400" />
                  <span>Inspected Documents ({selectedCase.documents.length})</span>
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {selectedCase.documents.map((doc) => (
                    <div
                      key={doc.id}
                      className="bg-slate-50 rounded-xl p-3 border border-slate-200 flex flex-col justify-between space-y-2"
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <span className="font-bold text-xs text-slate-900 block capitalize">
                            Slot: {doc.slot.replace("_", " ")}
                          </span>
                          <span className="text-[11px] text-slate-500 font-mono truncate max-w-[200px] block">
                            {doc.filename}
                          </span>
                        </div>
                        {doc.quality_score !== null && (
                          <span className="text-[10px] bg-slate-200 text-slate-800 font-bold px-1.5 py-0.5 rounded">
                            Quality: {(doc.quality_score * 100).toFixed(0)}%
                          </span>
                        )}
                      </div>

                      {/* OCR Extracted Fields snippet */}
                      {doc.extracted_fields && Object.keys(doc.extracted_fields).length > 0 && (
                        <div className="bg-white p-2 rounded border border-slate-200 text-[11px] space-y-1">
                          <span className="text-[10px] text-slate-400 font-bold uppercase block">
                            OCR Extracted
                          </span>
                          {Object.entries(doc.extracted_fields).slice(0, 3).map(([k, v]) => (
                            <div key={k} className="flex justify-between truncate">
                              <span className="text-slate-500">{k}:</span>
                              <span className="font-semibold text-slate-800 font-mono">
                                {String(v)}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Presigned Document Link */}
                      {doc.url && (
                        <a
                          href={doc.url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center justify-center space-x-1 w-full py-1.5 bg-white hover:bg-slate-100 text-slate-700 text-xs font-bold rounded border border-slate-200 transition-colors"
                        >
                          <Eye className="w-3.5 h-3.5 text-slate-500" />
                          <span>View Presigned Document</span>
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Supervisor Decision Desk */}
              <div className="bg-slate-900 text-white rounded-xl p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <UserCheck className="w-5 h-5 text-airtel-red" />
                    <h3 className="font-bold text-sm">Supervisor Verification Decision</h3>
                  </div>
                  <span className="text-xs text-slate-400 font-mono">
                    Audited under DPDP & Airtel Policy
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div>
                    <label className="text-slate-400 block mb-1 font-medium">Supervisor Actor</label>
                    <input
                      type="text"
                      value={supervisorEmail}
                      onChange={(e) => setSupervisorEmail(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-slate-400 block mb-1 font-medium">
                      Mandatory Decision Justification
                    </label>
                    <input
                      type="text"
                      placeholder="e.g., Cross-verified with state commercial tax portal; proprietor name matches exactly."
                      value={decisionReason}
                      onChange={(e) => setDecisionReason(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none placeholder-slate-500"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-end space-x-3 pt-2">
                  <button
                    onClick={() => {
                      if (!decisionReason.trim()) {
                        alert("Please provide a mandatory decision justification for the audit trail.");
                        return;
                      }
                      decisionMutation.mutate({
                        caseId: selectedCase.case_id,
                        decision: "REJECT",
                        reason: decisionReason,
                        actor: supervisorEmail,
                      });
                    }}
                    disabled={decisionMutation.isPending}
                    className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-bold rounded-lg flex items-center space-x-1.5 transition-colors disabled:opacity-50"
                  >
                    <X className="w-4 h-4" />
                    <span>Reject / Request Fix</span>
                  </button>

                  <button
                    onClick={() => {
                      if (!decisionReason.trim()) {
                        alert("Please provide a mandatory decision justification for the audit trail.");
                        return;
                      }
                      decisionMutation.mutate({
                        caseId: selectedCase.case_id,
                        decision: "APPROVE",
                        reason: decisionReason,
                        actor: supervisorEmail,
                      });
                    }}
                    disabled={decisionMutation.isPending}
                    className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg flex items-center space-x-1.5 transition-colors disabled:opacity-50"
                  >
                    <Check className="w-4 h-4" />
                    <span>Approve Case (PASS)</span>
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-slate-50 rounded-2xl p-12 text-center border border-dashed border-slate-300 text-slate-500">
              <ShieldCheck className="w-10 h-10 mx-auto text-slate-300 mb-2" />
              <p className="font-semibold text-sm">Select a KYC case from the left queue to review document proofs and registry cross-checks.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
