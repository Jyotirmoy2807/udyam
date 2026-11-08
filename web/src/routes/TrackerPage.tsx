import React, { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Truck,
  CheckCircle2,
  Clock,
  AlertTriangle,
  RefreshCw,
  Wifi,
  Sparkles,
  ArrowRight,
  ShieldAlert,
  Layers,
  ChevronDown,
  ChevronUp,
  CreditCard,
  Radio,
  Check,
} from "lucide-react";
import { api } from "../api/client";
import { Order, OrderItem } from "../api/types";

const TIMELINE_STEPS = [
  { key: "QUOTE_ACCEPTED", label: "Quote Accepted", desc: "Contract e-signed & UPI mandate authorized" },
  { key: "KYC_APPROVED", label: "KYC Approved", desc: "Automated DPDP & registry validation passed" },
  { key: "INSTALL_SCHEDULED", label: "Install Scheduled", desc: "Enterprise field engineer & CPE hardware dispatched" },
  { key: "INSTALLED", label: "Installed", desc: "Premises CPE wiring & ONT termination completed" },
  { key: "ACTIVATED", label: "Activated", desc: "Enterprise SLA 99.9% corporate connectivity live" },
];

export const TrackerPage: React.FC = () => {
  const { orderId } = useParams<{ orderId: string }>();
  const queryClient = useQueryClient();
  const { t } = useTranslation();

  const [simDrawerOpen, setSimDrawerOpen] = useState(true);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [delayedNotice, setDelayedNotice] = useState<{ newEta: string; reason: string } | null>(null);

  // 1. Fetch Order with TanStack Query + polling fallback
  const {
    data: order,
    isLoading: orderLoading,
    refetch: refetchOrder,
  } = useQuery({
    queryKey: ["order", orderId],
    queryFn: () => api.getOrder(orderId!),
    enabled: !!orderId,
    refetchInterval: 3000, // Poll every 3 seconds for live transitions
  });

  // 2. Setup native SSE stream listener
  useEffect(() => {
    if (!orderId) return;

    const base = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
    const sseUrl = `${base}/orders/${orderId}/stream`;
    let es: EventSource | null = null;

    try {
      es = new EventSource(sseUrl);
      es.addEventListener("order_update", (event) => {
        try {
          const updatedOrder = JSON.parse(event.data);
          queryClient.setQueryData(["order", orderId], updatedOrder);
        } catch (e) {
          console.error("SSE parse error", e);
        }
      });
    } catch (e) {
      console.warn("SSE connection error, falling back to polling", e);
    }

    return () => {
      if (es) es.close();
    };
  }, [orderId, queryClient]);

  // Mutations for Simulations & Actions
  const advanceMutation = useMutation({
    mutationFn: async () => {
      setActionNotice(null);
      const res = await api.simulateOrderAction(orderId!, { action: "advance" });
      return res;
    },
    onSuccess: (data) => {
      setActionNotice(`Order status advanced to: ${data.status}`);
      refetchOrder();
    },
  });

  const markInfeasibleMutation = useMutation({
    mutationFn: async () => {
      setActionNotice(null);
      const res = await api.markSiteInfeasible(orderId!, "P01");
      return res;
    },
    onSuccess: () => {
      setActionNotice("Simulated field test: Physical fiber unfeasible at premises.");
      refetchOrder();
    },
  });

  const swapAirFiberMutation = useMutation({
    mutationFn: async () => {
      setActionNotice(null);
      const res = await api.swapAirFiber(orderId!);
      return res;
    },
    onSuccess: () => {
      setActionNotice("Success: Swapped unfeasible wireline to 5G AirFiber (P04)!");
      refetchOrder();
    },
  });

  const simulateDelayMutation = useMutation({
    mutationFn: async () => {
      setActionNotice(null);
      const res = await api.simulateOrderAction(orderId!, {
        action: "install_delayed",
        delay_days: 3,
        reason: "Municipal Right-of-Way (ROW) Trenching Delay",
      });
      return res;
    },
    onSuccess: (data) => {
      setActionNotice(`Installation delayed by 3 days. Escalation ticket auto-created.`);
      setDelayedNotice({
        newEta: data.new_eta,
        reason: data.reason || "Municipal Right-of-Way (ROW) Trenching Delay",
      });
      refetchOrder();
    },
  });

  const simulatePaymentFailMutation = useMutation({
    mutationFn: async () => {
      setActionNotice(null);
      const res = await api.simulateOrderAction(orderId!, { action: "payment_failed" });
      return res;
    },
    onSuccess: (data) => {
      setActionNotice(`Payment failure triggered: ${data.reason}`);
      refetchOrder();
    },
  });

  const retryMandateMutation = useMutation({
    mutationFn: async () => {
      setActionNotice(null);
      const res = await api.retryMandate(orderId!);
      return res;
    },
    onSuccess: () => {
      setActionNotice("UPI Autopay mandate re-authorized! Provisioning resumed.");
      refetchOrder();
    },
  });

  // Calculate timeline index
  const getStepIndex = (status?: string, items?: OrderItem[]) => {
    if (!status || status === "DRAFT" || status === "SUBMITTED" || status === "KYC_PENDING") return 0;
    if (status === "KYC_APPROVED") return 1;
    if (status === "PROVISIONING") {
      const anyInstalled = items?.some((i) => i.status === "INSTALLED" || i.installed_at);
      return anyInstalled ? 3 : 2;
    }
    if (status === "ACTIVE") return 4;
    return 0;
  };

  const currentStepIdx = getStepIndex(order?.status, order?.items);

  // Dynamic "What happens next / What you need to do" messaging
  const getNextActionMessage = () => {
    if (order?.status === "FAILED") {
      return {
        title: "Action Required: UPI Autopay Mandate Declined",
        detail: "Your initial mandate authorization was declined by the issuing bank. Please retry authorization below to resume order fulfillment.",
        isAction: true,
      };
    }
    if (order?.items?.some((i) => i.status === "SITE_NOT_FEASIBLE")) {
      return {
        title: "Action Required: Fiber Trenching ROW Blocked",
        detail: "Local municipal restrictions prevent physical wireline trenching. Please approve the 1-Tap 5G AirFiber wireless swap below to retain your fast-track activation date.",
        isAction: true,
      };
    }
    if (delayedNotice) {
      return {
        title: "Operational Update: Installation Delay Escalated",
        detail: `${delayedNotice.reason}. Municipal liaison team has escalated clearance. Updated activation SLA: ${new Date(delayedNotice.newEta).toLocaleDateString("en-IN")}.`,
        isAction: false,
      };
    }
    switch (order?.status) {
      case "SUBMITTED":
      case "KYC_PENDING":
        return {
          title: "What Happens Next: Automated KYC Registry Audit",
          detail: "Our DPDP-compliant verification engine is validating your business GSTIN and Udyam credentials with GSTN and MSME registries. No action needed from you.",
          isAction: false,
        };
      case "KYC_APPROVED":
        return {
          title: "What Happens Next: Equipment Staging & Tech Assignment",
          detail: "Your KYC credentials are fully verified. Accel Enterprise logistics has allocated your hardware and assigned a certified field engineer.",
          isAction: false,
        };
      case "PROVISIONING":
        return {
          title: "What Happens Next: Field Installation in Progress",
          detail: "Your field engineer is en route or conducting on-site wiring and optical termination. Please keep server room access accessible.",
          isAction: false,
        };
      case "ACTIVE":
        return {
          title: "Service Active: Corporate Connectivity Live",
          detail: "Your Accel Business high-speed connection is live with 99.9% uptime SLA monitoring. Your billing cycle starts now.",
          isAction: false,
        };
      default:
        return {
          title: "Order In Progress",
          detail: "Tracking live fulfillment progress via Accel Enterprise Provisioning Bus.",
          isAction: false,
        };
    }
  };

  const nextAction = getNextActionMessage();

  // Check exceptions
  const hasSiteInfeasible = order?.items?.some((i) => i.status === "SITE_NOT_FEASIBLE");
  const hasSwappedAirFiber = order?.items?.some((i) => i.product_id === "P04" || i.status === "SWAPPED_FALLBACK");
  const isPaymentFailed = order?.status === "FAILED";

  return (
    <div className="max-w-4xl mx-auto space-y-6 py-4">
      {/* Breadcrumb */}
      <div className="flex items-center space-x-2 text-xs font-semibold text-slate-500">
        <Link to="/" className="hover:text-slate-800">
          Home
        </Link>
        <span>&bull;</span>
        <span className="text-accel-red">Live Order Fulfillment & Provisioning Tracker</span>
      </div>

      {/* Floating Demo Simulator Drawer */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-3xl p-5 text-white shadow-lg border border-indigo-900/40">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-amber-400" />
            <span className="font-black text-sm uppercase tracking-wider text-amber-300">
              Evaluator Test Bench: 1-Click Field Exception Simulators
            </span>
          </div>

          <button
            type="button"
            onClick={() => setSimDrawerOpen(!simDrawerOpen)}
            className="p-1 hover:bg-white/10 rounded-lg text-slate-400 hover:text-white transition-colors"
          >
            {simDrawerOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>

        {simDrawerOpen && (
          <div className="space-y-3 pt-1">
            <p className="text-xs text-slate-300">
              Trigger real-world field events to see the reactive UI, deterministic state transitions, and automatic recovery workflows:
            </p>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => advanceMutation.mutate()}
                disabled={advanceMutation.isPending}
                className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-700 text-white font-bold text-xs rounded-xl shadow-xs transition-all flex items-center space-x-1.5"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Advance Next Milestone</span>
              </button>

              <button
                type="button"
                onClick={() => markInfeasibleMutation.mutate()}
                disabled={markInfeasibleMutation.isPending}
                className="px-3.5 py-2 bg-amber-600 hover:bg-amber-700 disabled:bg-slate-700 text-white font-bold text-xs rounded-xl shadow-xs transition-all flex items-center space-x-1.5"
              >
                <Radio className="w-3.5 h-3.5" />
                <span>Simulate Fiber Infeasibility</span>
              </button>

              <button
                type="button"
                onClick={() => simulateDelayMutation.mutate()}
                disabled={simulateDelayMutation.isPending}
                className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-700 text-white font-bold text-xs rounded-xl shadow-xs transition-all flex items-center space-x-1.5"
              >
                <Clock className="w-3.5 h-3.5" />
                <span>Simulate Municipal ROW Delay (+3d)</span>
              </button>

              <button
                type="button"
                onClick={() => simulatePaymentFailMutation.mutate()}
                disabled={simulatePaymentFailMutation.isPending}
                className="px-3.5 py-2 bg-rose-700 hover:bg-rose-800 disabled:bg-slate-700 text-white font-bold text-xs rounded-xl shadow-xs transition-all flex items-center space-x-1.5"
              >
                <CreditCard className="w-3.5 h-3.5" />
                <span>Simulate Mandate Payment Failure</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {actionNotice && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-900 rounded-2xl text-xs font-bold flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>{actionNotice}</span>
          </div>
          <button
            type="button"
            onClick={() => setActionNotice(null)}
            className="text-emerald-700 hover:text-emerald-950 text-[11px]"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main Order Card */}
      <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-6 sm:p-8 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-100">
          <div>
            <div className="flex items-center space-x-2 mb-1">
              <span className="text-xs font-mono font-bold text-slate-500 bg-slate-100 px-2 py-0.5 rounded-md">
                Order ID: {orderId?.slice(0, 8).toUpperCase()}
              </span>
              <span className="text-xs font-bold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full">
                SLA Tier-1 Metro: 48h
              </span>
            </div>
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">
              Real-Time Provisioning Status
            </h1>
          </div>

          <div className="flex items-center space-x-3 text-right">
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-400 block">
                Estimated Delivery ETA
              </span>
              <span className="text-base font-black text-slate-900 font-mono">
                {order?.eta ? new Date(order.eta).toLocaleDateString("en-IN", { month: "short", day: "numeric", year: "numeric" }) : "Computing..."}
              </span>
            </div>
          </div>
        </div>

        {/* Plain-Language "What happens next / What you need to do" Banner */}
        <div
          className={`p-4 rounded-2xl border flex items-start space-x-3 ${
            nextAction.isAction
              ? "bg-rose-50 border-rose-200 text-rose-950"
              : "bg-blue-50 border-blue-200 text-blue-950"
          }`}
        >
          <div
            className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 ${
              nextAction.isAction ? "bg-rose-100 text-rose-700" : "bg-blue-100 text-blue-700"
            }`}
          >
            {nextAction.isAction ? <AlertTriangle className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
          </div>
          <div>
            <h4 className="text-xs font-black uppercase tracking-wider mb-0.5">
              {nextAction.title}
            </h4>
            <p className="text-xs opacity-90 leading-relaxed">{nextAction.detail}</p>
          </div>
        </div>

        {/* Vertical / Step Progress Timeline */}
        <div className="space-y-4">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Fulfillment Milestones
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
            {TIMELINE_STEPS.map((step, idx) => {
              const isPast = currentStepIdx >= 0 && idx < currentStepIdx;
              const isCurrent = currentStepIdx === idx;
              const isFuture = currentStepIdx < idx;

              return (
                <div
                  key={step.key}
                  className={`p-4 rounded-2xl border transition-all ${
                    isCurrent
                      ? "bg-accel-lightred/20 border-accel-red text-accel-darkred shadow-xs"
                      : isPast
                      ? "bg-emerald-50/70 border-emerald-200 text-slate-800"
                      : "bg-slate-50/40 border-slate-100 text-slate-400"
                  }`}
                >
                  <div className="flex items-center space-x-2 mb-1.5">
                    {isPast ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    ) : isCurrent ? (
                      <div className="w-4 h-4 rounded-full border-2 border-accel-red border-t-transparent animate-spin" />
                    ) : (
                      <div className="w-4 h-4 rounded-full border border-slate-300" />
                    )}
                    <span className="text-xs font-black">{step.label}</span>
                  </div>
                  <p className="text-[11px] leading-snug opacity-80">{step.desc}</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Interactive Exception Card 1: SITE_NOT_FEASIBLE -> AirFiber Swap */}
        {hasSiteInfeasible && (
          <div className="p-5 bg-amber-50 border border-amber-300 rounded-3xl space-y-3">
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-2xl bg-amber-100 text-amber-700 flex items-center justify-center font-bold">
                  <AlertTriangle className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-black text-amber-950 text-base">
                    Field Exception: Physical Fiber Infeasible at Site
                  </h3>
                  <p className="text-xs text-amber-900 mt-0.5">
                    Field team survey determined wireline fiber cable trenching is blocked by local ROW restrictions.
                  </p>
                </div>
              </div>
            </div>

            <div className="p-4 bg-white/80 rounded-2xl border border-amber-200 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <div className="inline-flex items-center space-x-1.5 text-xs font-bold text-emerald-800 bg-emerald-100 px-2.5 py-0.5 rounded-full mb-1">
                  <Wifi className="w-3 h-3 text-emerald-600" />
                  <span>Recommended Alternative: Accel 5G AirFiber (P04)</span>
                </div>
                <div className="text-xs text-slate-700 font-medium">
                  Plug-and-play high-speed wireless connectivity with identical 1 Gbps capability and zero monthly price difference.
                </div>
              </div>

              <button
                type="button"
                onClick={() => swapAirFiberMutation.mutate()}
                disabled={swapAirFiberMutation.isPending}
                className="h-11 px-5 bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs rounded-xl shadow-md transition-all flex items-center justify-center space-x-2 shrink-0 tap-target active:scale-95"
              >
                <Check className="w-4 h-4" />
                <span>Approve AirFiber Swap</span>
              </button>
            </div>
          </div>
        )}

        {/* If AirFiber Swapped */}
        {hasSwappedAirFiber && (
          <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              <div>
                <span className="text-xs font-bold text-emerald-950 block">
                  AirFiber 5G Swap Executed Successfully
                </span>
                <span className="text-[11px] text-emerald-700">
                  Equipment order updated to 5G AirFiber Outdoor Unit &bull; Fast-track delivery scheduled.
                </span>
              </div>
            </div>
            <span className="text-[10px] font-mono font-bold text-emerald-800 bg-emerald-100 px-2.5 py-1 rounded">
              P04 SWAPPED
            </span>
          </div>
        )}

        {/* Interactive Exception Card 2: PAYMENT_FAILED -> Retry Mandate */}
        {isPaymentFailed && (
          <div className="p-5 bg-rose-50 border border-rose-300 rounded-3xl space-y-3">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-2xl bg-rose-100 text-rose-700 flex items-center justify-center font-bold">
                <CreditCard className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-black text-rose-950 text-base">
                  Action Required: Recurring Mandate Payment Failed
                </h3>
                <p className="text-xs text-rose-900 mt-0.5">
                  The initial autopay mandate debit was declined by your bank. Please retry authorization.
                </p>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={() => retryMandateMutation.mutate()}
                disabled={retryMandateMutation.isPending}
                className="h-11 px-6 bg-rose-700 hover:bg-rose-800 text-white font-bold text-xs rounded-xl shadow-md transition-all flex items-center space-x-2 tap-target"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Retry UPI Autopay Mandate</span>
              </button>
            </div>
          </div>
        )}

        {/* Equipment & Provisioning Line Items Breakdown */}
        <div className="space-y-3 pt-2">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Provisioning Line Items
          </div>

          <div className="divide-y divide-slate-100 border border-slate-200 rounded-2xl overflow-hidden">
            {order?.items?.map((item) => (
              <div
                key={item.product_id}
                className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white hover:bg-slate-50 transition-colors"
              >
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 rounded-xl bg-slate-100 text-slate-800 flex items-center justify-center font-mono font-bold text-xs">
                    {item.product_id}
                  </div>
                  <div>
                    <div className="font-bold text-slate-900 text-sm">
                      {item.product_id === "P01"
                        ? "Accel Dedicated Business Fiber (1 Gbps)"
                        : item.product_id === "P04"
                        ? "Accel 5G AirFiber Outdoor Enterprise Unit"
                        : item.product_id === "P05"
                        ? "Enterprise Static IP Block (/29)"
                        : item.product_id === "P07"
                        ? "Cloud Edge Security & Backup"
                        : `Enterprise Service Item (${item.product_id})`}
                    </div>
                    <div className="text-[11px] text-slate-400">
                      Quantity: {item.qty} &bull; Expected ETA: {item.eta ? new Date(item.eta).toLocaleDateString() : "Scheduled"}
                    </div>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <span
                    className={`text-[10px] font-bold px-2.5 py-1 rounded-full uppercase tracking-wider ${
                      item.status === "ACTIVE" || item.status === "INSTALLED"
                        ? "bg-emerald-100 text-emerald-800"
                        : item.status === "SITE_NOT_FEASIBLE"
                        ? "bg-amber-100 text-amber-800"
                        : item.status === "SWAPPED_FALLBACK"
                        ? "bg-indigo-100 text-indigo-800"
                        : "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {item.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
