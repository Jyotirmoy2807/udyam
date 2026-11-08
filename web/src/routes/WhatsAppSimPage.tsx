import React, { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  Send,
  Paperclip,
  Smile,
  CheckCheck,
  ChevronLeft,
  MoreVertical,
  Phone,
  Video,
  FileCheck,
  Sparkles,
  ExternalLink,
  ShieldCheck,
  Building,
} from "lucide-react";
import { api } from "../api/client";
import { WhatsAppMessageResponse } from "../api/types";

interface ChatBubble {
  id: string;
  sender: "user" | "bot";
  text: string;
  time: string;
  buttons?: Array<{ id: string; title: string }>;
  media?: {
    type: "image" | "doc";
    title: string;
    url?: string;
  };
}

export const WhatsAppSimPage: React.FC = () => {
  const [phoneNumber, setPhoneNumber] = useState("9876543210");
  const [inputText, setInputText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState<ChatBubble[]>([
    {
      id: "msg-1",
      sender: "bot",
      text: "Namaste! Welcome to *Accel Business Enterprise Advisor* on WhatsApp.\n\nI can instantly help you with:\n1. Custom high-speed corporate fiber & 5G AirFiber plans\n2. Generating official PDF quotes\n3. Instant KYC document upload & registry verification\n\nPlease tell us about your business or tap a quick action below:",
      time: "10:00 AM",
      buttons: [
        { id: "VIEW_PLANS", title: "View Biz Fibre Plans" },
        { id: "ACCEPT_QUOTE", title: "Get Official Quote" },
      ],
    },
  ]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSendMessage = async (textToSend?: string, buttonId?: string, mediaUrl?: string) => {
    const text = textToSend !== undefined ? textToSend : inputText;
    if (!text.trim() && !buttonId && !mediaUrl) return;

    const timeNow = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    // Add user bubble
    if (buttonId) {
      const buttonTitle =
        messages
          .flatMap((m) => m.buttons || [])
          .find((b) => b.id === buttonId)?.title || buttonId;
      setMessages((prev) => [
        ...prev,
        { id: `user-${Date.now()}`, sender: "user", text: buttonTitle, time: timeNow },
      ]);
    } else if (mediaUrl) {
      setMessages((prev) => [
        ...prev,
        {
          id: `user-${Date.now()}`,
          sender: "user",
          text: "Uploaded document for Smart KYC verification",
          time: timeNow,
          media: { type: "image", title: "Electricity_Bill_Specimen.png" },
        },
      ]);
    } else {
      setMessages((prev) => [
        ...prev,
        { id: `user-${Date.now()}`, sender: "user", text, time: timeNow },
      ]);
      setInputText("");
    }

    setIsLoading(true);

    try {
      const res: WhatsAppMessageResponse = await api.sendWhatsAppMessage({
        phone: phoneNumber,
        text: text || undefined,
        button_id: buttonId || undefined,
        media_url: mediaUrl || undefined,
      });

      const botTime = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      setMessages((prev) => [
        ...prev,
        {
          id: `bot-${Date.now()}`,
          sender: "bot",
          text: res.reply,
          time: botTime,
          buttons: res.buttons,
        },
      ]);
    } catch (err: any) {
      const botTime = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      setMessages((prev) => [
        ...prev,
        {
          id: `bot-err-${Date.now()}`,
          sender: "bot",
          text: "We are currently experiencing a brief connectivity glitch. Our enterprise specialist will get back to you immediately.",
          time: botTime,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto pb-10">
      {/* Header Info */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-emerald-800 bg-emerald-50 px-3 py-1 rounded-full mb-2">
            <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
            <span>Omnichannel Stretch Module</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900">
            WhatsApp Business Enterprise Simulator
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Zero-install WhatsApp customer channel executing identical catalogue rules, instant quote creation, and OCR document processing.
          </p>
        </div>

        <div className="flex items-center space-x-2 text-xs">
          <span className="font-bold text-slate-600">Simulate Phone:</span>
          <input
            type="text"
            value={phoneNumber}
            onChange={(e) => setPhoneNumber(e.target.value)}
            className="w-28 bg-slate-100 border border-slate-200 rounded-lg px-2.5 py-1.5 font-mono text-slate-800 font-bold focus:outline-none"
          />
        </div>
      </div>

      {/* WhatsApp Frame Mockup */}
      <div className="max-w-md mx-auto bg-[#efeae2] rounded-3xl overflow-hidden border-4 border-slate-800 shadow-2xl flex flex-col h-[650px] relative">
        {/* WhatsApp Top Header Bar */}
        <div className="bg-[#075e54] text-white p-3.5 flex items-center justify-between shadow-md z-10">
          <div className="flex items-center space-x-2">
            <button className="text-white/80 hover:text-white">
              <ChevronLeft className="w-5 h-5" />
            </button>
            <div className="relative">
              <div className="w-10 h-10 rounded-full bg-white flex items-center justify-center text-accel-red font-black text-xl shadow-inner">
                a
              </div>
              <div className="absolute -bottom-0.5 -right-0.5 bg-emerald-500 rounded-full p-0.5 border border-white">
                <CheckCheck className="w-2.5 h-2.5 text-white" />
              </div>
            </div>
            <div>
              <div className="flex items-center space-x-1">
                <span className="font-bold text-sm leading-tight">Accel Business</span>
                <span className="bg-emerald-400 text-white rounded-full p-0.5" title="Official Enterprise Account">
                  <CheckCheck className="w-2.5 h-2.5" />
                </span>
              </div>
              <span className="text-[11px] text-emerald-100 block">Verified Business &bull; Online</span>
            </div>
          </div>

          <div className="flex items-center space-x-3 text-white/90">
            <button title="Voice Call" className="hover:text-white">
              <Phone className="w-4 h-4" />
            </button>
            <button title="Video Call" className="hover:text-white">
              <Video className="w-4 h-4" />
            </button>
            <button title="Options" className="hover:text-white">
              <MoreVertical className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Chat Message Scrollable Feed */}
        <div className="flex-1 p-3 overflow-y-auto space-y-3">
          {/* Encryption Note */}
          <div className="text-center my-2">
            <span className="bg-[#ffeecd] text-[#54656f] text-[10px] font-medium px-2.5 py-1 rounded-md shadow-xs inline-block max-w-[90%]">
              🔒 Messages and calls are end-to-end encrypted. No one outside of this chat, not even WhatsApp, can read or listen to them.
            </span>
          </div>

          {messages.map((m) => (
            <div
              key={m.id}
              className={`flex flex-col ${
                m.sender === "user" ? "items-end" : "items-start"
              }`}
            >
              <div
                className={`max-w-[85%] rounded-2xl p-3 shadow-xs relative text-xs leading-relaxed ${
                  m.sender === "user"
                    ? "bg-[#d9fdd3] text-slate-900 rounded-tr-none"
                    : "bg-white text-slate-900 rounded-tl-none border border-slate-100"
                }`}
              >
                {/* Media preview */}
                {m.media && (
                  <div className="bg-slate-100 rounded-xl p-2 mb-2 flex items-center space-x-2 border border-slate-200">
                    <FileCheck className="w-6 h-6 text-emerald-600" />
                    <span className="text-xs font-semibold text-slate-800 truncate">
                      {m.media.title}
                    </span>
                  </div>
                )}

                {/* Body Text */}
                <div className="whitespace-pre-line select-text">
                  {m.text}
                </div>

                {/* Timestamp */}
                <div className="flex items-center justify-end space-x-1 mt-1 text-[10px] text-slate-400">
                  <span>{m.time}</span>
                  {m.sender === "user" && <CheckCheck className="w-3 h-3 text-blue-500" />}
                </div>

                {/* Interactive Action Buttons */}
                {m.buttons && m.buttons.length > 0 && (
                  <div className="mt-2.5 pt-2 border-t border-slate-100 space-y-1.5">
                    {m.buttons.map((btn) => (
                      <button
                        key={btn.id}
                        onClick={() => handleSendMessage(undefined, btn.id)}
                        disabled={isLoading}
                        className="w-full text-center py-1.5 px-3 bg-slate-50 hover:bg-[#e7f8e4] text-[#075e54] font-bold text-xs rounded-xl border border-slate-200 transition-colors disabled:opacity-50"
                      >
                        {btn.title}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex items-center space-x-1.5 text-xs text-slate-500 bg-white/80 backdrop-blur-xs px-3 py-1.5 rounded-full w-fit">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Accel Business is typing...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* WhatsApp Bottom Input Bar */}
        <div className="bg-[#f0f2f5] p-2 flex items-center space-x-1.5 border-t border-slate-200">
          <button
            type="button"
            className="p-2 text-slate-500 hover:text-slate-700"
            title="Add Emoji"
          >
            <Smile className="w-5 h-5" />
          </button>

          {/* Quick Specimen Document Upload Simulation */}
          <button
            type="button"
            onClick={() => handleSendMessage(undefined, undefined, "https://minio.accel.in/specimens/k04_bill.png")}
            disabled={isLoading}
            className="p-2 text-slate-500 hover:text-emerald-700"
            title="Simulate Document Attachment"
          >
            <Paperclip className="w-5 h-5" />
          </button>

          <input
            type="text"
            placeholder="Type a message or plan enquiry..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleSendMessage();
              }
            }}
            disabled={isLoading}
            className="flex-1 bg-white border border-slate-200 rounded-full px-4 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
          />

          <button
            onClick={() => handleSendMessage()}
            disabled={isLoading || !inputText.trim()}
            className="w-9 h-9 rounded-full bg-[#00a884] hover:bg-[#075e54] text-white flex items-center justify-center transition-colors disabled:opacity-50 shadow-sm"
          >
            <Send className="w-4 h-4 ml-0.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
