import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Users,
  Search,
  Filter,
  TrendingUp,
  AlertTriangle,
  Building2,
  MapPin,
  ExternalLink,
  ChevronRight,
  UserCheck,
  Zap,
  Sparkles,
  PhoneCall,
  CheckCircle2,
} from "lucide-react";
import { api } from "../api/client";
import { OpsLead, Partner } from "../api/types";

export const OpsLeadsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedCity, setSelectedCity] = useState<string>("");
  const [selectedSegment, setSelectedSegment] = useState<string>("");
  const [selectedException, setSelectedException] = useState<string>("");
  const [selectedLead, setSelectedLead] = useState<OpsLead | null>(null);
  const [assignPartnerId, setAssignPartnerId] = useState<string>("");

  // Queries
  const { data: leads, isLoading: leadsLoading, refetch: refetchLeads } = useQuery({
    queryKey: ["ops-leads", selectedCity, selectedSegment, selectedException],
    queryFn: () =>
      api.getOpsLeads({
        city: selectedCity || undefined,
        segment: selectedSegment || undefined,
        exception_reason: selectedException || undefined,
      }),
  });

  const { data: partners } = useQuery({
    queryKey: ["ops-partners"],
    queryFn: () => api.listPartners(),
  });

  // Assign Partner Mutation
  const assignMutation = useMutation({
    mutationFn: ({ leadId, partnerId }: { leadId: string; partnerId?: string }) =>
      api.assignOpsLead(leadId, partnerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ops-leads"] });
      alert("Lead successfully assigned to channel partner!");
    },
  });

  const getScoreBadge = (score: number) => {
    if (score >= 75) {
      return (
        <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
          <TrendingUp className="w-3 h-3 text-emerald-600" />
          <span>High ({score})</span>
        </span>
      );
    }
    if (score >= 50) {
      return (
        <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-100 text-blue-800 border border-blue-200">
          <Zap className="w-3 h-3 text-blue-600" />
          <span>Med ({score})</span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-700 border border-slate-200">
        <span>Low ({score})</span>
      </span>
    );
  };

  const getExceptionBadge = (reason: string | null) => {
    if (!reason) {
      return (
        <span className="text-xs font-medium text-emerald-600 flex items-center space-x-1">
          <CheckCircle2 className="w-3 h-3" />
          <span>Self-Serve Active</span>
        </span>
      );
    }
    const map: Record<string, { label: string; color: string }> = {
      PAYMENT_FAILED: { label: "Payment Failed", color: "bg-red-100 text-red-800 border-red-200" },
      SITE_NOT_FEASIBLE: { label: "Site Infeasible", color: "bg-amber-100 text-amber-800 border-amber-200" },
      KYC_MANUAL_REVIEW: { label: "KYC Review Required", color: "bg-purple-100 text-purple-800 border-purple-200" },
      ADVISOR_UNRESOLVED: { label: "Advisor Unresolved", color: "bg-orange-100 text-orange-800 border-orange-200" },
      ADVISOR_ABANDONED: { label: "Session Abandoned", color: "bg-slate-100 text-slate-700 border-slate-200" },
    };
    const conf = map[reason] || { label: reason, color: "bg-red-50 text-red-700 border-red-200" };
    return (
      <span className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded text-xs font-bold border ${conf.color}`}>
        <AlertTriangle className="w-3 h-3" />
        <span>{conf.label}</span>
      </span>
    );
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-10">
      {/* Header */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-airtel-red bg-airtel-lightred px-3 py-1 rounded-full mb-2">
            <Users className="w-3.5 h-3.5" />
            <span>Back-Office Operations</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900">
            Intelligent Lead Queue & ML Routing
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Prioritised lead queue ranked by gradient-boosted propensity models, exception reasons, and territory channel partners.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <Link
            to="/ops/review"
            className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold rounded-xl transition-colors"
          >
            KYC Review Queue
          </Link>
          <Link
            to="/ops/funnel"
            className="px-4 py-2 bg-airtel-red hover:bg-airtel-darkred text-white text-xs font-bold rounded-xl shadow-sm transition-colors"
          >
            Conversion Funnel
          </Link>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm flex flex-wrap items-center gap-3">
        <div className="flex items-center space-x-1.5 text-xs font-bold text-slate-700 mr-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <span>Filters:</span>
        </div>

        {/* City Filter */}
        <select
          value={selectedCity}
          onChange={(e) => setSelectedCity(e.target.value)}
          className="text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-700 font-semibold focus:outline-none focus:ring-1 focus:ring-airtel-red"
        >
          <option value="">All Cities</option>
          <option value="Bengaluru">Bengaluru (Tier 1)</option>
          <option value="Mumbai">Mumbai (Tier 1)</option>
          <option value="Delhi">Delhi (Tier 1)</option>
          <option value="Pune">Pune (Tier 2)</option>
          <option value="Jaipur">Jaipur (Tier 2)</option>
          <option value="Lucknow">Lucknow (Tier 2)</option>
        </select>

        {/* Segment Filter */}
        <select
          value={selectedSegment}
          onChange={(e) => setSelectedSegment(e.target.value)}
          className="text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-700 font-semibold focus:outline-none focus:ring-1 focus:ring-airtel-red"
        >
          <option value="">All Segments</option>
          <option value="Retail & POS">Retail & POS</option>
          <option value="Offices & Tech">Offices & Tech</option>
          <option value="Multi-Site Retail">Multi-Site Retail</option>
          <option value="Manufacturing">Manufacturing</option>
        </select>

        {/* Exception Reason Filter */}
        <select
          value={selectedException}
          onChange={(e) => setSelectedException(e.target.value)}
          className="text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-700 font-semibold focus:outline-none focus:ring-1 focus:ring-airtel-red"
        >
          <option value="">All Exception States</option>
          <option value="PAYMENT_FAILED">Payment Failed (UPI/Mandate)</option>
          <option value="SITE_NOT_FEASIBLE">Site Infeasible (Fibre Swap)</option>
          <option value="KYC_MANUAL_REVIEW">KYC Manual Review Needed</option>
          <option value="ADVISOR_UNRESOLVED">Advisor Escalated</option>
          <option value="ADVISOR_ABANDONED">Session Abandoned</option>
        </select>

        {(selectedCity || selectedSegment || selectedException) && (
          <button
            onClick={() => {
              setSelectedCity("");
              setSelectedSegment("");
              setSelectedException("");
            }}
            className="text-xs text-airtel-red font-bold hover:underline ml-auto"
          >
            Clear Filters
          </button>
        )}
      </div>

      {/* Main Grid: Leads Table & Detail Pane */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Leads List (2 cols) */}
        <div className="lg:col-span-2 space-y-3">
          {leadsLoading ? (
            <div className="bg-white rounded-2xl p-12 text-center border border-slate-200">
              <div className="inline-block w-8 h-8 border-4 border-airtel-red border-t-transparent rounded-full animate-spin mb-3" />
              <p className="text-sm font-semibold text-slate-600">Loading intelligent lead queue...</p>
            </div>
          ) : leads && leads.length > 0 ? (
            leads.map((lead) => (
              <div
                key={lead.lead_id}
                onClick={() => {
                  setSelectedLead(lead);
                  setAssignPartnerId(lead.assigned_partner?.id || "");
                }}
                className={`bg-white rounded-xl p-4 border transition-all cursor-pointer shadow-sm hover:shadow-md ${
                  selectedLead?.lead_id === lead.lead_id
                    ? "border-airtel-red ring-1 ring-airtel-red bg-red-50/20"
                    : "border-slate-200 hover:border-slate-300"
                }`}
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-xs font-bold text-slate-800 bg-slate-100 px-2 py-0.5 rounded">
                      #{lead.lead_id.slice(0, 8).toUpperCase()}
                    </span>
                    <span className="text-xs font-semibold text-slate-600">
                      {lead.phone_masked}
                    </span>
                    <span className="text-[10px] uppercase font-bold text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded">
                      {lead.language}
                    </span>
                  </div>
                  <div>{getScoreBadge(lead.score?.score || 60)}</div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs text-slate-600 mb-3">
                  <div>
                    <span className="text-slate-400 block text-[10px]">Business Type</span>
                    <span className="font-semibold text-slate-800">
                      {lead.profile?.business_type || "Commercial SMB"}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px]">Location</span>
                    <span className="font-semibold text-slate-800">
                      {lead.profile?.city || "National"} {lead.profile?.tier ? `(Tier ${lead.profile.tier})` : ""}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px]">Draft Monthly Value</span>
                    <span className="font-bold text-slate-900">
                      {lead.draft_quote ? `₹${lead.draft_quote.monthly_recurring.toLocaleString("en-IN")}/mo` : "Quote In-Progress"}
                    </span>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-xs">
                  <div>{getExceptionBadge(lead.exception_reason)}</div>
                  <div className="flex items-center space-x-1 text-slate-500 font-medium">
                    <span>
                      {lead.assigned_partner ? `Partner: ${lead.assigned_partner.name}` : "Unassigned"}
                    </span>
                    <ChevronRight className="w-4 h-4 text-slate-400" />
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="bg-white rounded-2xl p-12 text-center border border-slate-200 text-slate-500">
              <Users className="w-10 h-10 mx-auto text-slate-300 mb-3" />
              <p className="font-bold text-slate-700">No leads match the specified filter criteria</p>
              <p className="text-xs text-slate-400 mt-1">Try resetting filters to view all incoming leads.</p>
            </div>
          )}
        </div>

        {/* Detail Inspection Pane (1 col) */}
        <div className="space-y-4">
          {selectedLead ? (
            <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm sticky top-20 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <h3 className="font-bold text-slate-900 text-base flex items-center space-x-2">
                  <Building2 className="w-4 h-4 text-airtel-red" />
                  <span>Lead Intelligence</span>
                </h3>
                <span className="font-mono text-xs font-bold text-slate-500">
                  #{selectedLead.lead_id.slice(0, 8).toUpperCase()}
                </span>
              </div>

              {/* Propensity ML Insight */}
              <div className="bg-gradient-to-br from-indigo-50/60 to-purple-50/60 p-4 rounded-xl border border-indigo-100 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-1.5">
                    <Sparkles className="w-4 h-4 text-indigo-600" />
                    <span className="text-xs font-bold text-indigo-950">ML Propensity Model</span>
                  </div>
                  <span className="text-xs font-bold font-mono text-indigo-700">
                    {selectedLead.score?.model_version || "scikit_propensity_v2"}
                  </span>
                </div>
                <div className="text-2xl font-black text-indigo-950 flex items-baseline space-x-1">
                  <span>{selectedLead.score?.score || 65}</span>
                  <span className="text-xs font-semibold text-indigo-600">/ 100 Propensity</span>
                </div>
                <div className="pt-2 border-t border-indigo-100/80">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-800 block mb-1">
                    Top Contributing Signals:
                  </span>
                  <div className="space-y-1">
                    {(selectedLead.score?.top_factors || []).map((f, i) => (
                      <div key={i} className="text-xs text-indigo-900 flex items-center justify-between">
                        <span>• {typeof f === "string" ? f : f.factor}</span>
                        {typeof f !== "string" && f.impact && (
                          <span className="font-mono text-[11px] font-bold text-emerald-700">{f.impact}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Profile Details */}
              <div className="space-y-2 text-xs">
                <h4 className="font-bold text-slate-800 text-[11px] uppercase tracking-wider">
                  Enterprise Profile
                </h4>
                <div className="bg-slate-50 p-3 rounded-xl border border-slate-100 space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Segment:</span>
                    <span className="font-semibold text-slate-800">{selectedLead.profile?.segment || "General SME"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Employees & Sites:</span>
                    <span className="font-semibold text-slate-800">
                      {selectedLead.profile?.employees || 1} staff &bull; {selectedLead.profile?.sites || 1} branch(es)
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Current Spend:</span>
                    <span className="font-semibold text-slate-800">
                      {selectedLead.profile?.monthly_spend ? `₹${selectedLead.profile.monthly_spend.toLocaleString("en-IN")}/mo` : "Not Stated"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">GST Registration:</span>
                    <span className={`font-semibold ${selectedLead.profile?.has_gstin ? "text-emerald-700" : "text-amber-700"}`}>
                      {selectedLead.profile?.has_gstin ? "Registered GSTIN" : "Exempt / Non-GST"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Exception & Handoff Context */}
              <div className="space-y-2 text-xs">
                <h4 className="font-bold text-slate-800 text-[11px] uppercase tracking-wider">
                  Status & Conversation Context
                </h4>
                <div className="bg-slate-50 p-3 rounded-xl border border-slate-100">
                  <p className="text-slate-600 italic">
                    "{selectedLead.conversation_summary || "Lead actively exploring Airtel Biz Fibre bundles."}"
                  </p>
                </div>
              </div>

              {/* Channel Partner Assignment */}
              <div className="space-y-2 pt-2 border-t border-slate-100">
                <label className="text-xs font-bold text-slate-800 block">
                  Assign Channel Partner
                </label>
                <div className="flex items-center gap-2">
                  <select
                    value={assignPartnerId}
                    onChange={(e) => setAssignPartnerId(e.target.value)}
                    className="flex-1 text-xs bg-slate-50 border border-slate-200 rounded-lg p-2 font-semibold text-slate-800 focus:outline-none"
                  >
                    <option value="">Auto-Assign (Least Loaded)</option>
                    {(partners || []).map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} ({p.cities.join(", ")})
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() =>
                      assignMutation.mutate({
                        leadId: selectedLead.lead_id,
                        partnerId: assignPartnerId || undefined,
                      })
                    }
                    disabled={assignMutation.isPending}
                    className="px-3 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded-lg transition-colors disabled:opacity-50"
                  >
                    {assignMutation.isPending ? "Saving..." : "Assign"}
                  </button>
                </div>
              </div>

              {/* Action Links */}
              <div className="pt-2 flex items-center gap-2">
                {selectedLead.draft_quote && (
                  <Link
                    to={`/quote/${selectedLead.draft_quote.quote_id}`}
                    className="flex-1 py-2 text-center text-xs font-bold bg-airtel-lightred text-airtel-red rounded-lg hover:bg-red-100 transition-colors"
                  >
                    View Active Quote
                  </Link>
                )}
                <a
                  href={`tel:${selectedLead.phone_masked}`}
                  className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg flex items-center justify-center"
                  title="Contact customer"
                >
                  <PhoneCall className="w-4 h-4" />
                </a>
              </div>
            </div>
          ) : (
            <div className="bg-slate-50 rounded-2xl p-8 text-center border border-dashed border-slate-300 text-slate-500">
              <UserCheck className="w-8 h-8 mx-auto text-slate-400 mb-2" />
              <p className="text-xs font-semibold">Select a lead from the queue to inspect details and assign channel partners.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
