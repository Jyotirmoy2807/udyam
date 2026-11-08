import React, { useState } from "react";
import { useParams, useNavigate, useSearchParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  FileText,
  Download,
  CheckCircle2,
  AlertTriangle,
  Plus,
  Minus,
  Trash2,
  Sparkles,
  ArrowRight,
  Shield,
  Layers,
  HelpCircle,
  TrendingDown,
  Info,
  Wifi,
} from "lucide-react";
import { api } from "../api/client";
import { Quote } from "../api/types";

export const QuotePage: React.FC = () => {
  const { quoteId } = useParams<{ quoteId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useTranslation();

  const isGstinInvalidNotice = searchParams.get("gstin_invalid") === "true";

  // State
  const [repairToast, setRepairToast] = useState<{ message: string; details?: any[] } | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // 1. Fetch Quote from backend
  const {
    data: quote,
    isLoading: quoteLoading,
    error: quoteError,
  } = useQuery({
    queryKey: ["quote", quoteId],
    queryFn: () => api.getQuote(quoteId!),
    enabled: !!quoteId && quoteId !== "demo",
  });

  // 2. Fetch Available Products Catalogue from backend
  const { data: catalogueProducts } = useQuery({
    queryKey: ["catalogue-products"],
    queryFn: () => api.getProducts(),
  });

  // Currency Formatter
  const formatINR = (val: number | null | undefined) => {
    if (val === null || val === undefined) return "₹0";
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(val);
  };

  // Mutation: Update Quote (add, remove, quantity, term)
  const updateMutation = useMutation({
    mutationFn: (updates: {
      add_products?: string[];
      remove_products?: string[];
      qty_updates?: Record<string, number>;
      term_months?: number;
    }) => api.updateQuote(quoteId!, updates),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["quote", quoteId] });
      if (data.changes_log && data.changes_log.length > 0) {
        const descriptions = data.changes_log
          .map((c: any) => c.reason || c.action || JSON.stringify(c))
          .join("; ");
        setRepairToast({
          message: "Rules Engine automatically adjusted dependent items:",
          details: data.changes_log,
        });
      } else {
        setRepairToast(null);
      }
    },
    onError: (err: any) => {
      alert("Catalogue rule error: " + (err.detail || "Unable to update bundle"));
    },
  });

  // Handlers
  const handleQtyChange = (productId: string, currentQty: number, delta: number) => {
    const newQty = currentQty + delta;
    if (newQty <= 0) {
      updateMutation.mutate({ remove_products: [productId] });
    } else {
      updateMutation.mutate({ qty_updates: { [productId]: newQty } });
    }
  };

  const handleAddProduct = (productId: string) => {
    updateMutation.mutate({ add_products: [productId] });
  };

  const handleRemoveProduct = (productId: string) => {
    updateMutation.mutate({ remove_products: [productId] });
  };

  const handleTermChange = (months: number) => {
    updateMutation.mutate({ term_months: months });
  };

  const handleAcceptQuote = async () => {
    if (!quoteId) return;
    setActionLoading(true);
    try {
      await api.acceptQuote(quoteId);
      navigate(`/consent?leadId=${quote?.lead_id}&quoteId=${quoteId}`);
    } catch (err: any) {
      alert("Failed to accept quote: " + (err.detail || "Server error"));
    } finally {
      setActionLoading(false);
    }
  };

  const handleAmendGstin = async () => {
    if (!quoteId) return;
    setActionLoading(true);
    try {
      const res = await api.amendQuoteForGstin(quoteId);
      navigate(`/quote/${res.new_quote_id}`);
    } catch (err: any) {
      alert("Amendment failed: " + (err.detail || "Server error"));
    } finally {
      setActionLoading(false);
    }
  };

  if (quoteLoading) {
    return (
      <div className="max-w-4xl mx-auto py-16 text-center">
        <div className="w-12 h-12 border-4 border-accel-red border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-slate-600 font-medium">Fetching verified quote from pricing engine...</p>
      </div>
    );
  }

  if (quoteError || !quote) {
    return (
      <div className="max-w-xl mx-auto py-12 text-center bg-white rounded-3xl p-8 border border-slate-200">
        <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-3" />
        <h2 className="text-xl font-bold text-slate-900 mb-2">Quote Not Found</h2>
        <p className="text-slate-600 text-sm mb-6">
          Unable to locate quote <code>{quoteId}</code>. Please return to the advisor to generate a bundle.
        </p>
        <Link
          to="/chat"
          className="bg-accel-red text-white font-bold py-3 px-6 rounded-xl inline-flex items-center space-x-2"
        >
          <span>Return to Advisor</span>
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    );
  }

  // Active product IDs in quote
  const activeProductIds = new Set((quote.lines || []).map((l) => l.product_id));
  const availableAddons = (catalogueProducts || []).filter(
    (p) => !activeProductIds.has(p.product_id) && !p.product_id.startsWith("P01") && !p.product_id.startsWith("P02") && !p.product_id.startsWith("P03") && !p.product_id.startsWith("P04") && !p.product_id.startsWith("P05")
  );

  return (
    <div className="max-w-4xl mx-auto py-4 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center space-x-2 bg-accel-lightred text-accel-red text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider mb-1.5">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Step 2 of 5 &bull; Transparent Quote</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-black text-slate-950 tracking-tight">
            Official Pricing & Digital Bundle
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 font-mono mt-0.5">
            Quote Ref: {quote.quote_id} &bull; Version v{quote.version}
          </p>
        </div>

        <button
          onClick={() => api.downloadQuotePdf(quote.quote_id)}
          className="inline-flex items-center justify-center space-x-2 bg-white hover:bg-slate-50 text-slate-800 font-bold text-sm px-4 py-2.5 rounded-xl border border-slate-300 shadow-2xs tap-target transition-all"
        >
          <Download className="w-4 h-4 text-accel-red" />
          <span>{t("common.download_pdf")}</span>
        </button>
      </div>

      {/* GSTIN Amendment Banner (K01 Scenario) */}
      {isGstinInvalidNotice && (
        <div className="bg-amber-50 border border-amber-300 p-4 rounded-2xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-sm">
          <div className="flex items-start space-x-3">
            <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div className="text-sm">
              <span className="font-bold text-amber-900 block">GSTIN Verification Notice</span>
              <span className="text-amber-800">
                Your GSTIN was identified as Cancelled/Suspended. You can proceed without GST benefits with our amended non-GST bundle.
              </span>
            </div>
          </div>
          <button
            onClick={handleAmendGstin}
            disabled={actionLoading}
            className="bg-amber-700 hover:bg-amber-800 text-white font-bold text-xs px-4 py-2 rounded-xl shrink-0 transition-all tap-target"
          >
            Switch to Non-GST Quote
          </button>
        </div>
      )}

      {/* Dependency Repair Toast */}
      {repairToast && (
        <div className="bg-blue-50 border border-blue-200 p-4 rounded-2xl flex items-start space-x-3 text-sm text-blue-900 shadow-sm animate-fadeIn">
          <Info className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
          <div className="flex-1">
            <span className="font-bold block">{repairToast.message}</span>
            <ul className="mt-1 list-disc list-inside text-xs text-blue-800 space-y-0.5">
              {repairToast.details?.map((d: any, i: number) => (
                <li key={i}>{typeof d === "string" ? d : d.reason || d.action || JSON.stringify(d)}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Main Transparent Summary Card */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-sm space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pb-6 border-b border-slate-100">
          {/* Monthly Recurring */}
          <div className="bg-slate-50 p-4 rounded-2xl border border-slate-100">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1">
              Monthly Recurring
            </span>
            <span className="text-2xl sm:text-3xl font-black text-slate-950 block">
              {formatINR(quote.monthly_recurring)}
            </span>
            <span className="text-xs text-slate-500 font-medium">Billed monthly with GST input</span>
          </div>

          {/* One-Time Setup */}
          <div className="bg-slate-50 p-4 rounded-2xl border border-slate-100">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1">
              One-Time Setup Fee
            </span>
            <span className="text-2xl sm:text-3xl font-black text-slate-950 block">
              {formatINR(quote.one_time)}
            </span>
            <span className="text-xs text-slate-500 font-medium">Installation & ONT device fee</span>
          </div>

          {/* First Month Total */}
          <div className="bg-accel-lightred/50 p-4 rounded-2xl border border-red-200">
            <span className="text-xs font-bold text-accel-red uppercase tracking-wider block mb-1">
              First Month Outflow
            </span>
            <span className="text-2xl sm:text-3xl font-black text-accel-red block">
              {formatINR(quote.first_month_total)}
            </span>
            <span className="text-xs text-red-700/80 font-medium">Recurring + Setup combined</span>
          </div>
        </div>

        {/* Contract Duration Selector */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
          <div>
            <span className="text-sm font-bold text-slate-900 block">Contract Term & Pricing Tier</span>
            <span className="text-xs text-slate-500">Longer commitments unlock higher position discounts</span>
          </div>
          <div className="inline-flex bg-slate-100 p-1 rounded-xl border border-slate-200">
            {[12, 24, 36].map((months) => (
              <button
                key={months}
                type="button"
                onClick={() => handleTermChange(months)}
                disabled={updateMutation.isPending}
                className={`py-1.5 px-4 rounded-lg text-xs font-bold transition-all tap-target flex items-center justify-center ${
                  quote.term_months === months
                    ? "bg-white text-accel-red shadow-sm border border-slate-200"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {months} Months
              </button>
            ))}
          </div>
        </div>

        {/* Conditional Savings Banner */}
        {quote.savings_vs_current && quote.savings_vs_current > 0 ? (
          <div className="bg-emerald-50 border border-emerald-200 p-4 rounded-2xl flex items-center space-x-3 text-emerald-900">
            <TrendingDown className="w-5 h-5 text-emerald-600 shrink-0" />
            <div className="text-xs sm:text-sm">
              <span className="font-bold">Verified Cost Optimization: </span>
              <span>
                You save <strong>{formatINR(quote.savings_vs_current)}/month</strong> (
                <strong>{formatINR(quote.savings_vs_current * 12)}/year</strong>) compared to your current telecom spend!
              </span>
            </div>
          </div>
        ) : (
          <div className="bg-slate-50 border border-slate-200 p-3.5 rounded-2xl flex items-center space-x-3 text-slate-700 text-xs">
            <Shield className="w-4 h-4 text-accel-red shrink-0" />
            <span>
              <strong>Enterprise SLA Included:</strong> 99.5% uptime guarantee, 4-hour MTTR resolution, and dedicated business relationship manager.
            </span>
          </div>
        )}
      </div>

      {/* Active Line Items */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-sm space-y-4">
        <h2 className="text-base font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
          <Layers className="w-4 h-4 text-accel-red" />
          <span>Configured Bundle Line Items</span>
        </h2>

        <div className="divide-y divide-slate-100">
          {(quote.lines || []).map((line) => (
            <div key={line.product_id} className="py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-start space-x-3">
                <div className="w-10 h-10 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center font-bold text-sm shrink-0 mt-0.5">
                  {line.product_id}
                </div>
                <div>
                  <div className="font-bold text-slate-900 text-base leading-tight">
                    {line.name || line.product_id}
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    Monthly: {formatINR(line.unit_price)} each &bull; Setup: {formatINR(line.setup_fee || 0)}
                  </div>
                </div>
              </div>

              {/* Quantity Stepper & Price */}
              <div className="flex items-center justify-between sm:justify-end space-x-4">
                <div className="flex items-center space-x-2 bg-slate-100 p-1 rounded-xl border border-slate-200">
                  <button
                    type="button"
                    onClick={() => handleQtyChange(line.product_id, line.qty, -1)}
                    disabled={updateMutation.isPending}
                    className="w-8 h-8 rounded-lg bg-white hover:bg-slate-200 text-slate-700 flex items-center justify-center tap-target shadow-2xs font-bold"
                  >
                    <Minus className="w-3.5 h-3.5" />
                  </button>
                  <span className="w-8 text-center text-sm font-bold font-mono text-slate-900">
                    {line.qty}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleQtyChange(line.product_id, line.qty, 1)}
                    disabled={updateMutation.isPending}
                    className="w-8 h-8 rounded-lg bg-white hover:bg-slate-200 text-slate-700 flex items-center justify-center tap-target shadow-2xs font-bold"
                  >
                    <Plus className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className="text-right min-w-[90px]">
                  <span className="font-bold text-slate-900 text-base block font-mono">
                    {formatINR((line.discounted_price || line.unit_price || 0) * line.qty)}
                  </span>
                  <span className="text-[11px] text-slate-500">/month</span>
                </div>

                <button
                  type="button"
                  onClick={() => handleRemoveProduct(line.product_id)}
                  disabled={updateMutation.isPending}
                  className="p-2 text-slate-400 hover:text-red-600 tap-target flex items-center justify-center transition-colors"
                  title="Remove from bundle"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Available Add-Ons Drawer */}
      {availableAddons.length > 0 && (
        <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-sm space-y-4">
          <h2 className="text-base font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
            <Plus className="w-4 h-4 text-accel-red" />
            <span>Add Compatible Services & Hardware</span>
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {availableAddons.slice(0, 6).map((addon) => (
              <div
                key={addon.product_id}
                className="p-4 rounded-2xl border border-slate-200 hover:border-accel-red/30 bg-slate-50 hover:bg-accel-lightred/20 flex items-center justify-between transition-all"
              >
                <div>
                  <span className="text-xs font-bold text-accel-red uppercase tracking-wide block">
                    {addon.category} ({addon.product_id})
                  </span>
                  <span className="text-sm font-bold text-slate-900 block leading-tight mt-0.5">
                    {addon.name}
                  </span>
                  <span className="text-xs text-slate-500 font-mono mt-1 block">
                    from {formatINR(addon.price_min)}/mo
                  </span>
                </div>

                <button
                  type="button"
                  onClick={() => handleAddProduct(addon.product_id)}
                  disabled={updateMutation.isPending}
                  className="px-3 py-1.5 bg-white hover:bg-accel-red hover:text-white border border-slate-300 rounded-xl text-xs font-bold text-slate-800 shadow-2xs transition-all tap-target flex items-center space-x-1"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add</span>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Bottom Sticky Action Bar */}
      <div className="sticky bottom-4 bg-white/95 backdrop-blur-md p-4 rounded-2xl border border-slate-200 shadow-xl flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <span className="text-xs text-slate-500 block font-medium">Agreed Monthly Commitment</span>
          <span className="text-xl sm:text-2xl font-black text-slate-950 font-mono">
            {formatINR(quote.monthly_recurring)}{" "}
            <span className="text-xs text-slate-500 font-sans font-normal">/mo + setup {formatINR(quote.one_time)}</span>
          </span>
        </div>

        <button
          type="button"
          onClick={handleAcceptQuote}
          disabled={actionLoading}
          className="w-full sm:w-auto bg-accel-red hover:bg-accel-darkred disabled:bg-slate-300 text-white font-bold py-3.5 px-8 rounded-xl shadow-md transition-all tap-target flex items-center justify-center space-x-2 active:scale-95"
        >
          <span>{actionLoading ? "Locking Quote..." : t("common.accept_quote")}</span>
          <ArrowRight className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
};
