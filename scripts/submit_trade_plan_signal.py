#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import urllib.parse
from pathlib import Path


def load_payload(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_enum(value: object, allowed: set[str], field: str, issues: list[str]) -> None:
    if value is None:
        return
    if value not in allowed:
        values = ", ".join(sorted(allowed))
        issues.append(f"{field} must be one of: {values}")


def validate(payload: dict) -> list[str]:
    issues = []
    required = [
        "source",
        "skill_name",
        "skill_version",
        "symbol",
        "side",
        "confidence",
        "signal_reason",
        "evidence",
        "created_at",
        "expires_at",
        "trade_params",
    ]
    for key in required:
        if key not in payload:
            issues.append(f"missing required field: {key}")

    if payload.get("source") != "Hermes":
        issues.append("source must be Hermes")
    if payload.get("skill_name") != "zuoge-crypto-trade":
        issues.append("skill_name must be zuoge-crypto-trade")
    validate_enum(payload.get("side"), {"long", "short"}, "side", issues)
    validate_enum(
        payload.get("position_intent"),
        {"open", "takeover", "reverse", "close"},
        "position_intent",
        issues,
    )

    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
        issues.append("confidence must be a number between 0 and 1")

    evidence = payload.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        issues.append("evidence must contain at least one item")

    if payload.get("position_intent") == "reverse" and not payload.get("replace_existing_position", False):
        issues.append("replace_existing_position must be true when position_intent is reverse")

    trade_params = payload.get("trade_params")
    if isinstance(trade_params, dict):
        entry = trade_params.get("entry", {})
        exits = trade_params.get("exits", {})
        sizing = trade_params.get("sizing", {})
        constraints = trade_params.get("execution_constraints", {})

        trigger = entry.get("trigger", {})
        validate_enum(
            trigger.get("type"),
            {"immediate", "touch_price", "breakout", "pullback_into_range"},
            "entry.trigger.type",
            issues,
        )
        if trigger.get("type") in {"touch_price", "breakout"} and trigger.get("trigger_price") is None:
            issues.append("entry.trigger.trigger_price is required for touch_price or breakout")
        if trigger.get("type") == "pullback_into_range":
            trigger_range = trigger.get("trigger_range")
            if not isinstance(trigger_range, dict) or trigger_range.get("min") is None or trigger_range.get("max") is None:
                issues.append("entry.trigger.trigger_range is required for pullback_into_range")

        price = entry.get("price", {})
        validate_enum(price.get("order_type"), {"market", "limit"}, "entry.price.order_type", issues)
        if price.get("order_type") == "limit" and price.get("limit_price") is None:
            issues.append("entry.price.limit_price is required when order_type is limit")

        acceptable_range = price.get("acceptable_range")
        if acceptable_range is not None:
            if acceptable_range.get("min") is None or acceptable_range.get("max") is None:
                issues.append("entry.price.acceptable_range.min and max are required when acceptable_range is present")

        stop_loss = exits.get("stop_loss", {})
        validate_enum(stop_loss.get("mode"), {"price", "percent", "none"}, "exits.stop_loss.mode", issues)
        if stop_loss.get("mode") == "price" and stop_loss.get("stop_price") is None:
            issues.append("exits.stop_loss.stop_price is required when mode is price")
        if stop_loss.get("mode") == "percent" and stop_loss.get("loss_pct") is None:
            issues.append("exits.stop_loss.loss_pct is required when mode is percent")

        take_profit = exits.get("take_profit", {})
        validate_enum(
            take_profit.get("mode"),
            {"fixed_price", "ladder", "none"},
            "exits.take_profit.mode",
            issues,
        )
        if take_profit.get("mode") in {"fixed_price", "ladder"}:
            targets = take_profit.get("targets")
            if not isinstance(targets, list) or not targets:
                issues.append("exits.take_profit.targets must contain at least one item when mode is fixed_price or ladder")

        if exits.get("time_stop", {}).get("enabled") and not exits.get("time_stop", {}).get("max_holding_minutes"):
            issues.append("exits.time_stop.max_holding_minutes is required when time_stop is enabled")

        validate_enum(
            sizing.get("mode"),
            {"target_notional", "risk_budget", "fixed_quantity"},
            "sizing.mode",
            issues,
        )
        if sizing.get("mode") == "target_notional" and sizing.get("target_notional") is None:
            issues.append("sizing.target_notional is required when mode is target_notional")
        if sizing.get("mode") == "risk_budget" and sizing.get("target_risk_amount") is None:
            issues.append("sizing.target_risk_amount is required when mode is risk_budget")
        if sizing.get("mode") == "fixed_quantity" and sizing.get("target_quantity") is None:
            issues.append("sizing.target_quantity is required when mode is fixed_quantity")

        if constraints.get("max_slippage_pct") is None and acceptable_range is None:
            issues.append("either entry.price.acceptable_range or execution_constraints.max_slippage_pct must be present")

    return issues


def apply_auth_headers(req: urllib.request.Request, api_key: str | None) -> None:
    if api_key:
        req.add_header("X-API-Key", api_key)


def submit(base_url: str, payload: dict, trace_id: str | None, api_key: str | None) -> dict:
    url = base_url.rstrip("/") + "/api/v1/agent/proposals/signals"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if trace_id:
        req.add_header("X-Trace-Id", trace_id)
    apply_auth_headers(req, api_key)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_trading_context(base_url: str, symbol: str, side: str, trace_id: str | None, api_key: str | None) -> dict:
    query = urllib.parse.urlencode({"symbol": symbol, "side": side})
    url = base_url.rstrip("/") + "/api/v1/agent/trading-context?" + query
    req = urllib.request.Request(url, method="GET")
    if trace_id:
        req.add_header("X-Trace-ID", trace_id)
    apply_auth_headers(req, api_key)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch trading context and submit a TradePlanSignal payload."
    )
    parser.add_argument("payload", help="Path to the TradePlanSignal JSON payload file.")
    parser.add_argument(
        "--base-url",
        dest="base_url",
        default=None,
        help="Agent API base URL. Overrides CRYPTO_TRADER_BASE_URL when provided.",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        default=None,
        help="Agent API key. Overrides CRYPTO_TRADER_AGENT_API_KEY when provided.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    payload = load_payload(args.payload)
    issues = validate(payload)
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1

    base_url = args.base_url or os.environ.get("CRYPTO_TRADER_BASE_URL", "http://127.0.0.1:8080")
    api_key = args.api_key or os.environ.get("CRYPTO_TRADER_AGENT_API_KEY")
    trace_id = os.environ.get("TRACE_ID")
    try:
        if "context_version" not in payload:
            symbol = str(payload.get("symbol", "")).strip()
            side = str(payload.get("side", "")).strip()
            if symbol and side:
                trading_context = fetch_trading_context(base_url, symbol, side, trace_id, api_key)
                context_version = trading_context.get("context_version")
                if isinstance(context_version, str) and context_version.strip():
                    payload["context_version"] = context_version.strip()
        response = submit(base_url, payload, trace_id, api_key)
    except urllib.error.HTTPError as e:
        print(e.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return e.code or 1
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1

    print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
