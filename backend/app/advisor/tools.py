from typing import Any
from app.advisor.state import ConversationContext, AdvisorState, BUSINESS_TYPE_TO_SEGMENT, CITY_TO_TIER
from app.catalogue.loader import load_catalogue
from app.catalogue.rules import Profile, BundleLine, validate, repair, recommend, compute_default_qty
from app.catalogue.pricing import price_bundle

catalogue = load_catalogue()

# OpenAI-compatible tool specifications for Groq
ADVISOR_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "update_profile",
            "description": "Updates customer business profile slots extracted from conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "business_type": {"type": "string", "description": "Type of business (e.g. Salon, CA firm, Dental clinic)"},
                    "city": {"type": "string", "description": "Operating city in India"},
                    "employees": {"type": "integer", "description": "Total employee/staff count"},
                    "sites": {"type": "integer", "description": "Total operating locations/offices/shops"},
                    "has_gstin": {"type": "boolean", "description": "Whether customer has an active GSTIN registration. NEVER ask for the GSTIN number itself in chat."},
                    "current_internet": {"type": "string", "description": "Current broadband/telecom connection type"},
                    "current_provider": {"type": "string", "description": "Current service provider"},
                    "monthly_spend": {"type": "integer", "description": "Current total monthly telecom/IT spend in INR"},
                    "mobile_lines": {"type": "integer", "description": "Number of postpaid mobile SIM lines needed"},
                    "needs": {"type": "array", "items": {"type": "string"}, "description": "Specific business requirements (e.g. CCTV, POS, Wi-Fi)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "classify_segment",
            "description": "Classifies a business type into one of 4 segments: micro, professional_offices, small_multi_site, small_manufacturers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "business_type": {"type": "string", "description": "Customer business type"}
                },
                "required": ["business_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recommendation",
            "description": "Generates a fully compliant, pricing-optimised primary bundle and cheaper alternative.",
            "parameters": {
                "type": "object",
                "properties": {
                    "needs": {"type": "array", "items": {"type": "string"}, "description": "Customer requirements"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "adjust_bundle",
            "description": "Adds or removes products from the customer's current bundle with dependency checks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "add": {"type": "array", "items": {"type": "string"}, "description": "List of product IDs to add (e.g. ['P09', 'P23'])"},
                    "remove": {"type": "array", "items": {"type": "string"}, "description": "List of product IDs to remove"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_rule",
            "description": "Explains why a requested product cannot be added or was removed due to catalogue constraints.",
            "parameters": {
                "type": "object",
                "properties": {
                    "violation_code": {
                        "type": "string",
                        "enum": ["TIER_UNAVAILABLE", "MIN_EMPLOYEES", "MIN_SITES", "GSTIN_REQUIRED", "DEPENDENCY_MISSING"],
                    },
                    "product_id": {"type": "string", "description": "Product ID"},
                },
                "required": ["violation_code", "product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "handoff",
            "description": "Transfers conversation to a human specialist or field partner.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Reason for handoff"}
                },
                "required": ["reason"],
            },
        },
    },
]


class AdvisorToolExecutor:
    """Executes advisor tools deterministically and updates conversation context."""

    def __init__(self, ctx: ConversationContext):
        self.ctx = ctx

    async def __call__(self, fn_name: str, args: dict[str, Any]) -> dict[str, Any]:
        handler = getattr(self, f"tool_{fn_name}", None)
        if not handler:
            return {"status": "error", "message": f"Unknown tool: {fn_name}"}
        return await handler(args)

    async def tool_update_profile(self, args: dict[str, Any]) -> dict[str, Any]:
        self.ctx.update_slots(args)
        if self.ctx.is_profile_complete() and self.ctx.state == AdvisorState.PROFILE_COLLECTION:
            self.ctx.state = AdvisorState.RECOMMEND

        return {
            "status": "success",
            "profile_complete": self.ctx.is_profile_complete(),
            "next_missing_slot": self.ctx.next_missing_required_slot(),
            "inferred_segment": self.ctx.segment,
            "inferred_tier": self.ctx.tier,
        }

    async def tool_classify_segment(self, args: dict[str, Any]) -> dict[str, Any]:
        bt = args.get("business_type", "").strip()
        seg = BUSINESS_TYPE_TO_SEGMENT.get(bt, "micro")
        self.ctx.segment = seg
        return {"business_type": bt, "segment": seg}

    async def tool_get_recommendation(self, args: dict[str, Any]) -> dict[str, Any]:
        needs = args.get("needs") or self.ctx.needs
        profile = Profile(
            tier=self.ctx.tier,
            employees=self.ctx.employees or 1,
            sites=self.ctx.sites or 1,
            has_valid_gstin=bool(self.ctx.has_gstin),
            segment=self.ctx.segment or "micro",
        )

        repair_result = recommend(profile, needs, catalogue)
        primary_lines = repair_result.lines

        # Calculate primary pricing
        primary_pricing = price_bundle(
            lines=primary_lines,
            segment=profile.segment,
            term_months=12,
            current_spend=self.ctx.monthly_spend,
            catalogue=catalogue,
        )

        # Cheaper alternative: replace base link with P01 / P04 if feasible, or drop non-essential add-on
        cheaper_lines = [l for l in primary_lines]
        if any(l.product_id in ("P02", "P03", "P05") for l in cheaper_lines):
            cheaper_lines = [
                BundleLine(product_id="P01", qty=l.qty) if l.product_id in ("P02", "P03", "P05") else l
                for l in cheaper_lines
            ]
            repaired_cheaper = repair(profile, cheaper_lines, catalogue, intent="recommend")
            cheaper_lines = repaired_cheaper.lines

        cheaper_pricing = price_bundle(
            lines=cheaper_lines,
            segment=profile.segment,
            term_months=12,
            current_spend=self.ctx.monthly_spend,
            catalogue=catalogue,
        )

        # Update context allowed products and allowed numbers
        self.ctx.current_bundle = [{"product_id": l.product_id, "qty": l.qty} for l in primary_lines]
        self.ctx.allowed_products = {l.product_id for l in primary_lines} | {l.product_id for l in cheaper_lines}
        self.ctx.allowed_numbers = set(primary_pricing.allowed_numbers) | set(cheaper_pricing.allowed_numbers)
        self.ctx.state = AdvisorState.RECOMMEND

        return {
            "status": "success",
            "primary": {
                "monthly_recurring": primary_pricing.monthly_recurring,
                "one_time": primary_pricing.one_time,
                "first_month_total": primary_pricing.first_month_total,
                "savings_vs_current": primary_pricing.savings_vs_current,
                "annual_savings": primary_pricing.annual_savings,
                "lines": [
                    {
                        "product_id": l.product_id,
                        "name": l.product_name,
                        "qty": l.qty,
                        "unit_price": l.unit_price,
                        "line_monthly": l.line_monthly,
                        "setup": l.line_setup,
                    }
                    for l in primary_pricing.lines
                ],
            },
            "cheaper_alternative": {
                "monthly_recurring": cheaper_pricing.monthly_recurring,
                "first_month_total": cheaper_pricing.first_month_total,
            },
            "allowed_products": sorted(list(self.ctx.allowed_products)),
            "allowed_numbers": sorted(list(self.ctx.allowed_numbers)),
        }

    async def tool_adjust_bundle(self, args: dict[str, Any]) -> dict[str, Any]:
        to_add = args.get("add") or []
        to_remove = set(args.get("remove") or [])

        current_lines = [BundleLine(product_id=b["product_id"], qty=b.get("qty", 1)) for b in self.ctx.current_bundle]
        profile = Profile(
            tier=self.ctx.tier,
            employees=self.ctx.employees or 1,
            sites=self.ctx.sites or 1,
            has_valid_gstin=bool(self.ctx.has_gstin),
            segment=self.ctx.segment or "micro",
        )

        # Remove products
        is_base_removal = any(r in ("P01", "P02", "P03", "P04", "P05", "P06") for r in to_remove)
        current_lines = [l for l in current_lines if l.product_id not in to_remove]

        # Add products
        for pid in to_add:
            if pid in catalogue and not any(l.product_id == pid for l in current_lines):
                qty = compute_default_qty(catalogue[pid], profile)
                current_lines.append(BundleLine(product_id=pid, qty=qty))

        intent = "user_removed_base" if is_base_removal else "recommend"
        repair_result = repair(profile, current_lines, catalogue, intent=intent)

        pricing = price_bundle(
            lines=repair_result.lines,
            segment=profile.segment,
            term_months=12,
            current_spend=self.ctx.monthly_spend,
            catalogue=catalogue,
        )

        self.ctx.current_bundle = [{"product_id": l.product_id, "qty": l.qty} for l in repair_result.lines]
        self.ctx.allowed_products = {l.product_id for l in repair_result.lines}
        self.ctx.allowed_numbers = set(pricing.allowed_numbers)

        return {
            "status": "success",
            "lines": [
                {
                    "product_id": l.product_id,
                    "name": l.product_name,
                    "qty": l.qty,
                    "unit_price": l.unit_price,
                    "line_monthly": l.line_monthly,
                    "setup": l.line_setup,
                }
                for l in pricing.lines
            ],
            "monthly_recurring": pricing.monthly_recurring,
            "one_time": pricing.one_time,
            "first_month_total": pricing.first_month_total,
            "changes_log": repair_result.changes_log,
            "allowed_products": sorted(list(self.ctx.allowed_products)),
            "allowed_numbers": sorted(list(self.ctx.allowed_numbers)),
        }

    async def tool_explain_rule(self, args: dict[str, Any]) -> dict[str, Any]:
        code = args.get("violation_code")
        pid = args.get("product_id")
        prod = catalogue.get(pid)
        pname = prod.name if prod else pid

        explanations = {
            "TIER_UNAVAILABLE": f"{pname} ({pid}) is currently only provisioned in Tier 1 enterprise metropolitan clusters and is not available in Tier {self.ctx.tier}.",
            "MIN_EMPLOYEES": f"{pname} ({pid}) is engineered for enterprise teams of at least {prod.min_employees if prod else 5} employees. Your team currently has {self.ctx.employees or 1}.",
            "MIN_SITES": f"{pname} ({pid}) requires a minimum of {prod.min_sites if prod else 3} interconnected branch locations. Your business currently has {self.ctx.sites or 1} site(s).",
            "GSTIN_REQUIRED": f"{pname} ({pid}) is a statutory business-grade service that requires an active GSTIN registration under telecom regulations.",
            "DEPENDENCY_MISSING": f"{pname} ({pid}) is an enterprise add-on that requires an underlying primary connectivity link (such as {', '.join(prod.requires_one_of) if prod else 'Biz Fibre'}).",
        }
        return {
            "violation_code": code,
            "product_id": pid,
            "explanation": explanations.get(code, f"Product {pid} cannot be added due to policy {code}."),
        }

    async def tool_handoff(self, args: dict[str, Any]) -> dict[str, Any]:
        reason = args.get("reason", "Customer requested human consultation")
        self.ctx.state = AdvisorState.HANDOFF_TO_HUMAN
        return {
            "status": "handed_off",
            "reason": reason,
            "message": "We have assigned your profile to a dedicated enterprise connectivity relationship manager who will contact you shortly.",
        }
