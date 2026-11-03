import React from "react";
import { useLocation, Link } from "react-router-dom";
import { ArrowRight, Sparkles } from "lucide-react";

export const RoutePlaceholder: React.FC<{ title: string; stepNumber: number }> = ({ title, stepNumber }) => {
  const location = useLocation();

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 text-center max-w-xl mx-auto my-12">
      <div className="w-14 h-14 bg-airtel-lightred text-airtel-red rounded-full flex items-center justify-center mx-auto mb-4 font-bold text-xl">
        {stepNumber}
      </div>
      <h1 className="text-2xl font-bold text-slate-900 mb-2">{title}</h1>
      <p className="text-slate-600 text-sm mb-6">
        Route <code className="bg-slate-100 text-airtel-red px-2 py-0.5 rounded font-mono">{location.pathname}</code> is scaffolded and will be activated in Frontend Checkpoint {stepNumber}.
      </p>

      <div className="flex justify-center space-x-3">
        <Link
          to="/"
          className="inline-flex items-center space-x-2 bg-slate-900 text-white font-semibold text-sm px-5 py-2.5 rounded-lg hover:bg-slate-800 transition-colors"
        >
          <span>Return to Dashboard</span>
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  );
};
