/** TypeScript interfaces strictly matching FastAPI Pydantic v2 schemas and models */

export type UserRole = "customer" | "partner" | "ops_admin" | "owner" | "sales" | "reviewer";

export interface ApiError {
  code?: string;
  message_key: string;
  detail?: string | Record<string, any>;
}

export interface BackendHealthResponse {
  status: "healthy" | "degraded";
  clock: {
    fixed_date: string;
    fixed_datetime: string;
    status: string;
  };
  services: {
    postgres: string;
    redis: string;
    minio: string;
  };
}

export interface OtpSendResponse {
  status: string;
  phone_masked: string;
  message: string;
}

export interface AuthResponse {
  status: string;
  access_token: string;
  token_type: string;
  role: UserRole;
  phone_masked: string;
}

export interface PropensityScore {
  score: number;
  score_int: number;
  decile: number;
  band: "HIGH" | "MEDIUM" | "LOW";
  model_version: string;
  top_factors: string[];
}

export interface Lead {
  lead_id: string;
  status: string;
  language: string;
  phone_masked: string;
  created_at?: string;
  profile?: BusinessProfile;
  score?: {
    score: number;
    model_version: string;
    top_factors: string[];
  };
  propensity?: PropensityScore;
  assigned_partner?: {
    partner_id: string | null;
    name: string | null;
  } | null;
}

export interface BusinessProfile {
  business_type?: string | null;
  segment?: string | null;
  city?: string | null;
  tier?: number | null;
  employees?: number;
  sites?: number;
  has_gstin?: boolean;
  monthly_spend?: number | null;
  current_internet?: string | null;
  current_provider?: string | null;
}

export interface CreateLeadRequest {
  phone: string;
  language?: string;
  source?: string;
  business_type?: string;
  city?: string;
  employees?: number;
  sites?: number;
  has_gstin?: boolean;
  monthly_spend?: number;
  current_internet?: string;
  current_provider?: string;
}

export interface AdvisorChatRequest {
  lead_id: string;
  conversation_id?: string | null;
  message: string;
  language?: string;
}

export interface AdvisorChatResponse {
  conversation_id: string;
  state: string;
  reply: string;
  tool_executions: Array<{
    name: string;
    args?: Record<string, any>;
    result?: Record<string, any>;
  }>;
  profile_complete: boolean;
  current_bundle: Array<{
    product_id: string;
    qty: number;
  }>;
}

export interface QuoteLine {
  product_id: string;
  qty: number;
  name?: string;
  unit_price?: number;
  discounted_price?: number;
  setup_fee?: number;
}

export interface Quote {
  quote_id: string;
  lead_id: string;
  version: number;
  term_months: number;
  monthly_recurring: number;
  one_time: number;
  first_month_total: number;
  savings_vs_current: number | null;
  status: string;
  lines?: QuoteLine[];
}

export interface KycConsentResponse {
  status: string;
  consent_id: string;
  lead_id: string;
  accepted_at: string;
  notice_version: string;
}

export interface KycCase {
  case_id: string;
  lead_id: string;
  quote_id: string;
  verdict: "PENDING" | "PASS" | "NEEDS_FIX" | "MANUAL_REVIEW";
  gstin_masked?: string | null;
  documents?: Array<{
    slot: string;
    quality: Record<string, any>;
    extracted: Record<string, any>;
    view_url?: string;
  }>;
  checks?: Array<{
    check_code: string;
    outcome: "PASS" | "FAIL" | "REVIEW" | "WARN";
    detail: Record<string, any>;
  }>;
}

export interface KycVerifyResponse {
  case_id: string;
  verdict: "PENDING" | "PASS" | "NEEDS_FIX" | "MANUAL_REVIEW";
  checks_passed: number;
  total_checks: number;
  fix_messages: string[];
}

export interface OrderItem {
  product_id: string;
  qty: number;
  status: string;
  eta: string | null;
  installed_at?: string | null;
}

export interface Order {
  order_id: string;
  lead_id: string;
  quote_id: string;
  status: string;
  eta: string | null;
  kyc_approved_at?: string | null;
  items: OrderItem[];
}

export interface FunnelStage {
  stage: string;
  count: number;
  overall_conversion_pct: number;
  stage_drop_off_pct: number;
}

export interface FunnelResponse {
  funnel_summary: {
    total_leads: number;
    active_orders: number;
    overall_conversion_pct: number;
  };
  stages: FunnelStage[];
}
