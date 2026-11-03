import {
  ApiError,
  BackendHealthResponse,
  AuthResponse,
  OtpSendResponse,
  Lead,
  CreateLeadRequest,
  AdvisorChatRequest,
  AdvisorChatResponse,
  Quote,
  KycConsentResponse,
  KycCase,
  KycVerifyResponse,
  Order,
  FunnelResponse,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

let currentToken: string | null = null;
let currentLanguage: string = "en";

export const setAuthToken = (token: string | null) => {
  currentToken = token;
};

export const setClientLanguage = (lang: string) => {
  currentLanguage = lang;
};

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has("Accept-Language")) {
    headers.set("Accept-Language", currentLanguage);
  }

  if (currentToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${currentToken}`);
  }

  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    let errorObj: ApiError = {
      code: `HTTP_${response.status}`,
      message_key: "errors.generic",
      detail: response.statusText,
    };
    try {
      const errJson = await response.json();
      if (errJson.detail) {
        errorObj = {
          code: `HTTP_${response.status}`,
          message_key: typeof errJson.detail === "string" ? errJson.detail : "errors.server",
          detail: errJson.detail,
        };
      }
    } catch {
      // Non-JSON error body
    }
    throw errorObj;
  }

  return response.json();
}

/** Native ReadableStream SSE reader for instant token streaming */
export async function streamAdvisorChat(
  leadId: string,
  message: string,
  lang: string = "en",
  onToken: (token: string) => void,
  onDone: () => void,
  onError: (err: any) => void
) {
  const url = `${API_BASE_URL}/advisor/stream?lead_id=${encodeURIComponent(leadId)}&message=${encodeURIComponent(message)}&lang=${encodeURIComponent(lang)}`;
  try {
    const headers: Record<string, string> = {
      Accept: "text/event-stream",
    };
    if (currentToken) {
      headers["Authorization"] = `Bearer ${currentToken}`;
    }

    const res = await fetch(url, { headers });
    if (!res.ok) {
      throw new Error(`SSE stream failed with status ${res.status}`);
    }

    const reader = res.body?.getReader();
    if (!reader) throw new Error("ReadableStream not supported by browser");

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || "";

      for (const block of lines) {
        const line = block.trim();
        if (line.startsWith("data:")) {
          const raw = line.slice(5).trim();
          if (raw === "[DONE]") {
            onDone();
            return;
          }
          try {
            const parsed = JSON.parse(raw);
            if (parsed.token) {
              onToken(parsed.token);
            }
          } catch {
            onToken(raw);
          }
        }
      }
    }
    onDone();
  } catch (err) {
    onError(err);
  }
}

// ----------------------------------------------------------------------
// EXPORTED API METHODS
// ----------------------------------------------------------------------

export const api = {
  // Health
  checkHealth: () => request<BackendHealthResponse>("/health"),

  // Auth
  sendOtp: (phone: string, channel: string = "SMS") =>
    request<OtpSendResponse>("/auth/otp/send", {
      method: "POST",
      body: JSON.stringify({ phone, channel }),
    }),

  verifyOtp: (phone: string, otp: string, role: string = "customer") =>
    request<AuthResponse>("/auth/otp/verify", {
      method: "POST",
      body: JSON.stringify({ phone, otp, role }),
    }),

  // Leads
  createLead: (data: CreateLeadRequest) =>
    request<Lead>("/leads", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getLead: (leadId: string) => request<Lead>(`/leads/${leadId}`),

  getPartnerQueue: (partnerId: string) => request<Lead[]>(`/leads/queue/${partnerId}`),

  // Advisor
  chatAdvisor: (data: AdvisorChatRequest) =>
    request<AdvisorChatResponse>("/advisor/chat", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  transcribeVoice: async (audioBlob: Blob, language: string = "en"): Promise<{ transcription: string }> => {
    const formData = new FormData();
    formData.append("file", audioBlob, "voice_input.wav");
    return request<{ transcription: string }>(`/advisor/voice?language=${encodeURIComponent(language)}`, {
      method: "POST",
      body: formData,
    });
  },

  // Quotes
  createQuote: (leadId: string, products: Array<{ product_id: string; qty: number }>, termMonths: number = 12) =>
    request<Quote>("/quotes", {
      method: "POST",
      body: JSON.stringify({ lead_id: leadId, products, term_months: termMonths }),
    }),

  getQuote: (quoteId: string) => request<Quote>(`/quotes/${quoteId}`),

  getProducts: (category?: string) =>
    request<any[]>(category ? `/products?category=${encodeURIComponent(category)}` : "/products"),

  updateQuote: (
    quoteId: string,
    updates: {
      add_products?: string[];
      remove_products?: string[];
      qty_updates?: Record<string, number>;
      term_months?: number;
    }
  ) =>
    request<any>(`/quotes/${quoteId}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    }),

  acceptQuote: (quoteId: string) =>
    request<{ status: string; quote_id: string; quote_status: string }>(`/quotes/${quoteId}/accept`, {
      method: "POST",
    }),

  amendQuoteForGstin: (quoteId: string) =>
    request<any>(`/quotes/${quoteId}/amend-gstin`, {
      method: "POST",
    }),

  downloadQuotePdf: (quoteId: string) => {
    const url = `${API_BASE_URL}/quotes/${quoteId}/pdf`;
    window.open(url, "_blank");
  },

  requestEsign: (quoteId: string, signatoryName?: string, signatoryPhone?: string) =>
    request<{ status: string; esign_id: string; quote_id: string }>(`/quotes/${quoteId}/esign`, {
      method: "POST",
      body: JSON.stringify({ signatory_name: signatoryName, signatory_phone: signatoryPhone }),
    }),

  completeEsign: (esignId: string) =>
    request<{ status: string; esign_id: string }>(`/esign/${esignId}/complete`, {
      method: "POST",
    }),

  createMandate: (quoteId: string, leadId: string, vpa: string, bankName: string = "HDFC Bank") =>
    request<{ status: string; mandate_id: string; vpa: string }>("/quotes/mandate", {
      method: "POST",
      body: JSON.stringify({ quote_id: quoteId, lead_id: leadId, vpa, bank_name: bankName }),
    }),

  // KYC
  recordConsent: (leadId: string, purpose: string = "KYC_VERIFICATION", language: string = "en") =>
    request<KycConsentResponse>("/kyc/consent", {
      method: "POST",
      body: JSON.stringify({ lead_id: leadId, purpose, language }),
    }),

  createKycCase: (leadId: string, quoteId: string, gstin?: string) =>
    request<KycCase>("/kyc/cases", {
      method: "POST",
      body: JSON.stringify({ lead_id: leadId, quote_id: quoteId, gstin }),
    }),

  uploadKycDocument: (caseId: string, slot: string, file: File | Blob) => {
    const formData = new FormData();
    formData.append("case_id", caseId);
    formData.append("slot", slot);
    formData.append("file", file, "doc.png");
    return request<any>("/kyc/upload", {
      method: "POST",
      body: formData,
    });
  },

  verifyKycCase: (caseId: string) =>
    request<KycVerifyResponse>("/kyc/verify", {
      method: "POST",
      body: JSON.stringify({ case_id: caseId }),
    }),

  getKycCase: (caseId: string) => request<KycCase>(`/kyc/cases/${caseId}`),

  // Orders
  createOrder: (quoteId: string, cityTier: number = 1) =>
    request<Order>("/orders", {
      method: "POST",
      body: JSON.stringify({ quote_id: quoteId, city_tier: cityTier }),
    }),

  getOrder: (orderId: string) => request<Order>(`/orders/${orderId}`),

  transitionOrder: (orderId: string, targetStatus: string, reason?: string) =>
    request<Order>(`/orders/${orderId}/transition`, {
      method: "POST",
      body: JSON.stringify({ target_status: targetStatus, reason }),
    }),

  simulateSiteNotFeasible: (orderId: string) =>
    request<any>(`/orders/${orderId}/simulate/site-not-feasible`, { method: "POST" }),

  simulateInstallDelayed: (orderId: string, delayDays: number = 3) =>
    request<any>(`/orders/${orderId}/simulate/install-delayed`, {
      method: "POST",
      body: JSON.stringify({ delay_days: delayDays }),
    }),

  simulatePaymentFailed: (orderId: string) =>
    request<any>(`/orders/${orderId}/simulate/payment-failed`, { method: "POST" }),

  // Ops & Webhooks
  getFunnelMetrics: () => request<FunnelResponse>("/ops/funnel"),

  getAuditEvents: (limit: number = 20) => request<any[]>(`/ops/events?limit=${limit}`),

  overrideKycVerdict: (caseId: string, newVerdict: string, reason: string) =>
    request<any>(`/ops/kyc/${caseId}/override`, {
      method: "POST",
      body: JSON.stringify({ new_verdict: newVerdict, reason }),
    }),
};
