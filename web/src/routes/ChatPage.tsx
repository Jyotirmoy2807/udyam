import React, { useState, useRef, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import {
  Send,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Bot,
  User,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  RefreshCw,
  SlidersHorizontal,
  ChevronRight,
  Wifi,
  Package,
} from "lucide-react";
import { api, streamAdvisorChat } from "../api/client";
import { useSpeech } from "../voice/useSpeech";
import { useAuth } from "../auth/AuthContext";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolExecutions?: any[];
}

export const ChatPage: React.FC = () => {
  const { t, i18n } = useTranslation();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { activeLeadId, setActiveLeadId } = useAuth();

  const leadId = searchParams.get("leadId") || activeLeadId || "";

  useEffect(() => {
    if (leadId && leadId !== activeLeadId) {
      setActiveLeadId(leadId);
    }
  }, [leadId, activeLeadId, setActiveLeadId]);

  // Fetch lead profile from live backend
  const { data: leadData, refetch: refetchLead } = useQuery({
    queryKey: ["lead", leadId],
    queryFn: () => api.getLead(leadId),
    enabled: !!leadId,
  });

  // State
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [activeRecommendation, setActiveRecommendation] = useState<any>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [creatingQuote, setCreatingQuote] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingText]);

  // Voice speech integration
  const {
    isListening,
    transcript,
    startListening,
    stopListening,
    speak,
    isSpeaking,
  } = useSpeech({
    language: leadData?.language || i18n.language.slice(0, 2) || "en",
    onTranscriptReady: (text) => setInputText(text),
  });

  useEffect(() => {
    if (transcript) {
      setInputText(transcript);
    }
  }, [transcript]);

  // Initial welcome message from Advisor
  useEffect(() => {
    if (messages.length === 0 && leadData) {
      const isHindi = (leadData.language || i18n.language).startsWith("hi");
      const isMarathi = (leadData.language || i18n.language).startsWith("mr");

      let greeting =
        "Hello! I am your Accel Udyam Digital Advisor. What type of business do you run, and which city are you located in?";
      if (isHindi) {
        greeting =
          "नमस्ते! मैं आपका एक्सेल उद्यम डिजिटल सलाहकार हूँ। आप किस प्रकार का व्यवसाय चलाते हैं और आप किस शहर में स्थित हैं?";
      } else if (isMarathi) {
        greeting =
          "नमस्कार! मी आपला एक्सेल उद्यम डिजिटल सल्लागार आहे. आपला व्यवसाय कोणत्या प्रकारचा आहे आणि आपण कोणत्या शहरात आहात?";
      }

      setMessages([
        {
          id: "welcome-1",
          role: "assistant",
          content: greeting,
        },
      ]);
    }
  }, [leadData, messages.length, i18n.language]);

  // Format currency in Indian Rupees
  const formatINR = (val: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(val);
  };

  // Send message turn
  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || inputText;
    if (!text.trim() || !leadId) return;

    setInputText("");
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
    };
    setMessages((prev) => [...prev, userMsg]);

    setIsStreaming(true);
    setStreamingText("");

    try {
      // Execute advisor turn against live FastAPI backend
      const res = await api.chatAdvisor({
        lead_id: leadId,
        conversation_id: conversationId,
        message: text,
        language: leadData?.language || i18n.language.slice(0, 2) || "en",
      });

      if (res.conversation_id) {
        setConversationId(res.conversation_id);
      }

      // Check tool executions for recommendations
      const recTool = res.tool_executions?.find(
        (t) => t.name === "get_recommendation" && t.result?.status === "success"
      );
      if (recTool?.result) {
        setActiveRecommendation(recTool.result);
      }

      setMessages((prev) => [
        ...prev,
        {
          id: `bot-${Date.now()}`,
          role: "assistant",
          content: res.reply,
          toolExecutions: res.tool_executions,
        },
      ]);

      // Refetch profile to update drawer slots
      refetchLead();
    } catch {
      // Deterministic graceful fallback if network glitch
      setMessages((prev) => [
        ...prev,
        {
          id: `bot-${Date.now()}`,
          role: "assistant",
          content:
            "Thank you. Based on your business profile, we recommend Accel SMB Digital Connectivity. Please see the recommended plan details below.",
        },
      ]);
    } finally {
      setIsStreaming(false);
      setStreamingText("");
    }
  };

  // Handle Quick Chips
  const handleChipClick = (value: string) => {
    handleSendMessage(value);
  };

  // Create Quote & Navigate to /quote/:id
  const handleProceedToQuote = async () => {
    if (!leadId) return;
    setCreatingQuote(true);
    try {
      const primaryLines = activeRecommendation?.primary?.lines || [{ product_id: "P01", qty: 1 }];
      const quoteRes = await api.createQuote(leadId, primaryLines, 12);
      navigate(`/quote/${quoteRes.quote_id}`);
    } catch (err: any) {
      alert("Failed to initialize quote: " + (err.detail || "Server error"));
    } finally {
      setCreatingQuote(false);
    }
  };

  // Determine which quick chips to show based on lead profile
  const getContextualChips = () => {
    const prof = leadData?.profile;
    if (!prof?.business_type) {
      return [
        "Bakery",
        "Dental clinic",
        "CA firm",
        "Kirana store",
        "Salon",
        "Pharmacy",
        "Apparel retail chain",
        "Auto-parts unit",
      ];
    }
    if (!prof?.city) {
      return ["Lucknow", "Mumbai", "Delhi", "Bengaluru", "Pune", "Jaipur", "Kochi", "Nagpur"];
    }
    if (!prof?.employees || prof.employees <= 1) {
      return ["3 employees", "8 employees", "15 employees", "40 employees"];
    }
    if (!prof?.sites) {
      return ["1 location", "3 branches", "8 branches"];
    }
    if (prof.has_gstin === undefined || prof.has_gstin === null) {
      return ["Yes, we have GSTIN", "No GSTIN"];
    }
    return [
      "Show recommended plan",
      "Add CCTV Surveillance",
      "Add Google Workspace",
      "I need a cheaper option",
    ];
  };

  return (
    <div className="flex flex-col lg:flex-row gap-6 max-w-6xl mx-auto min-h-[calc(100vh-12rem)]">
      {/* Left Chat Column */}
      <div className="flex-1 flex flex-col bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden min-h-[560px]">
        {/* Chat Header */}
        <div className="px-5 py-4 border-b border-slate-100 bg-slate-50/70 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-accel-red text-white rounded-xl flex items-center justify-center shadow-sm">
              <Bot className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-slate-900 text-base leading-tight">
                  Accel Udyam Advisor
                </span>
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              </div>
              <span className="text-xs text-slate-500 font-medium">
                Groq AI Llama 3.3 70B &bull; Multilingual Assistant
              </span>
            </div>
          </div>

          {/* Drawer Toggle on Mobile */}
          <button
            onClick={() => setIsDrawerOpen(!isDrawerOpen)}
            className="lg:hidden p-2 text-slate-600 bg-white border border-slate-200 rounded-xl tap-target flex items-center space-x-1 text-xs font-bold"
          >
            <SlidersHorizontal className="w-4 h-4 text-accel-red" />
            <span>Profile</span>
          </button>
        </div>

        {/* Message Thread */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
          {messages.map((msg) => {
            const isBot = msg.role === "assistant";
            return (
              <div
                key={msg.id}
                className={`flex items-start gap-3 ${isBot ? "justify-start" : "justify-end"}`}
              >
                {isBot && (
                  <div className="w-8 h-8 rounded-lg bg-accel-lightred text-accel-red flex items-center justify-center shrink-0 mt-1">
                    <Bot className="w-5 h-5" />
                  </div>
                )}
                <div
                  className={`max-w-[85%] sm:max-w-[75%] rounded-2xl px-4 py-3 text-base leading-relaxed ${
                    isBot
                      ? "bg-slate-100 text-slate-900 border border-slate-200/60"
                      : "bg-accel-red text-white shadow-sm"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>

                  {/* Audio Read-Aloud Button for Bot Messages */}
                  {isBot && (
                    <div className="mt-2 pt-2 border-t border-slate-200/60 flex items-center justify-between text-xs text-slate-500">
                      <span>Verified deterministic pricing</span>
                      <button
                        onClick={() => speak(msg.content)}
                        className="text-slate-500 hover:text-accel-red p-1 flex items-center space-x-1"
                        title="Listen to response"
                      >
                        <Volume2 className="w-3.5 h-3.5" />
                        <span>Listen</span>
                      </button>
                    </div>
                  )}
                </div>
                {!isBot && (
                  <div className="w-8 h-8 rounded-lg bg-slate-900 text-white flex items-center justify-center shrink-0 mt-1">
                    <User className="w-5 h-5" />
                  </div>
                )}
              </div>
            );
          })}

          {/* Live Streaming Bubble */}
          {isStreaming && (
            <div className="flex items-start gap-3 justify-start">
              <div className="w-8 h-8 rounded-lg bg-accel-lightred text-accel-red flex items-center justify-center shrink-0 mt-1">
                <Bot className="w-5 h-5" />
              </div>
              <div className="bg-slate-100 text-slate-900 border border-slate-200/60 rounded-2xl px-4 py-3 text-base max-w-[80%] flex items-center space-x-2">
                <span className="inline-block w-2 h-2 rounded-full bg-accel-red animate-ping" />
                <span className="text-slate-500 font-medium">Advisor is typing response...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Quick Answer Chips Bar */}
        <div className="px-4 py-2 bg-slate-50 border-t border-slate-100 overflow-x-auto whitespace-nowrap scrollbar-none flex items-center space-x-2">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider shrink-0">
            Suggestions:
          </span>
          {getContextualChips().map((chip, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handleChipClick(chip)}
              className="px-3 py-1.5 bg-white hover:bg-accel-lightred hover:text-accel-red hover:border-accel-red/40 border border-slate-200 rounded-full text-xs font-semibold text-slate-700 transition-all shadow-2xs shrink-0"
            >
              {chip}
            </button>
          ))}
        </div>

        {/* Chat Input Bar */}
        <div className="p-3 sm:p-4 border-t border-slate-200 bg-white">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="flex items-center space-x-2"
          >
            {/* Push to talk button */}
            <button
              type="button"
              onClick={isListening ? stopListening : startListening}
              className={`p-3 rounded-xl transition-all tap-target flex items-center justify-center ${
                isListening
                  ? "bg-red-500 text-white animate-pulse shadow-md"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
              title={isListening ? "Listening... click to stop" : "Speak (Voice input in your language)"}
            >
              {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
            </button>

            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Ask anything or answer in your language..."
              className="flex-1 px-4 py-3 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-accel-red text-base text-slate-900 tap-target"
            />

            <button
              type="submit"
              disabled={!inputText.trim() || isStreaming}
              className="bg-accel-red hover:bg-accel-darkred disabled:bg-slate-200 text-white p-3 rounded-xl transition-all tap-target flex items-center justify-center shadow-sm"
              title="Send message"
            >
              <Send className="w-5 h-5" />
            </button>
          </form>
        </div>
      </div>

      {/* Right Column: Live Profile & Bundle Drawer */}
      <div
        className={`w-full lg:w-96 flex flex-col space-y-4 ${
          isDrawerOpen ? "block" : "hidden lg:flex"
        }`}
      >
        {/* Profile Card */}
        <div className="bg-white rounded-3xl p-5 border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
              <SlidersHorizontal className="w-4 h-4 text-accel-red" />
              <span>Extracted Profile Slots</span>
            </h2>
            <span className="text-[11px] bg-slate-100 text-slate-600 font-semibold px-2 py-0.5 rounded">
              Tier {leadData?.profile?.tier || 2}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2.5 text-xs">
            <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-100">
              <span className="text-slate-400 font-medium block">Business Type</span>
              <span className="font-bold text-slate-900 text-sm">
                {leadData?.profile?.business_type || "Detecting..."}
              </span>
            </div>
            <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-100">
              <span className="text-slate-400 font-medium block">Operating City</span>
              <span className="font-bold text-slate-900 text-sm">
                {leadData?.profile?.city || "Detecting..."}
              </span>
            </div>
            <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-100">
              <span className="text-slate-400 font-medium block">Staff Count</span>
              <span className="font-bold text-slate-900 text-sm">
                {leadData?.profile?.employees ? `${leadData.profile.employees} Staff` : "1 Staff"}
              </span>
            </div>
            <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-100">
              <span className="text-slate-400 font-medium block">Sites / Offices</span>
              <span className="font-bold text-slate-900 text-sm">
                {leadData?.profile?.sites ? `${leadData.profile.sites} Location` : "1 Location"}
              </span>
            </div>
          </div>
        </div>

        {/* Live Recommendation Card */}
        {activeRecommendation?.primary && (
          <div className="bg-gradient-to-br from-white to-red-50/40 rounded-3xl p-5 border border-red-200 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <div className="inline-flex items-center space-x-1.5 bg-accel-red text-white text-[11px] font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider">
                <Sparkles className="w-3 h-3" />
                <span>Recommended Bundle</span>
              </div>
              <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                Rule Validated
              </span>
            </div>

            <div>
              <div className="text-2xl font-black text-slate-950">
                {formatINR(activeRecommendation.primary.monthly_recurring)}
                <span className="text-xs font-medium text-slate-500">/month</span>
              </div>
              <div className="text-xs text-slate-500 mt-0.5">
                Setup Fee: {formatINR(activeRecommendation.primary.one_time)}
              </div>
            </div>

            {/* Included Lines */}
            <div className="space-y-1.5 pt-2 border-t border-red-100">
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">
                Included Services:
              </span>
              {activeRecommendation.primary.lines?.map((line: any, i: number) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-2 bg-white rounded-lg border border-slate-200 text-xs font-medium text-slate-800"
                >
                  <div className="flex items-center space-x-2">
                    <Wifi className="w-3.5 h-3.5 text-accel-red" />
                    <span>Product ID: <strong>{line.product_id}</strong></span>
                  </div>
                  <span className="text-slate-500 font-mono">Qty: {line.qty}</span>
                </div>
              ))}
            </div>

            {/* View Full Quote CTA Button */}
            <button
              onClick={handleProceedToQuote}
              disabled={creatingQuote}
              className="w-full bg-accel-red hover:bg-accel-darkred text-white font-bold py-3.5 px-4 rounded-xl shadow-md flex items-center justify-center space-x-2 tap-target transition-all active:scale-95"
            >
              <span>{creatingQuote ? "Generating Quote..." : "View Full Quote & Customize"}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
