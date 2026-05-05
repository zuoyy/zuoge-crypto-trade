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


def is_positive_number(value: object) -> bool:
    return isinstance(value, (int, float)) and value > 0


def is_non_negative_number(value: object) -> bool:
    return isinstance(value, (int, float)) and value >= 0


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
        position_management = trade_params.get("position_management", {})
        constraints = trade_params.get("execution_constraints", {})

        trigger = entry.get("trigger", {})
        validate_enum(
            trigger.get("type"),
            {"immediate", "touch_price", "breakout", "pullback_into_range"},
            "entry.trigger.type",
            issues,
        )
        if trigger.get("type") in {"touch_price", "breakout"} and not is_positive_number(trigger.get("trigger_price")):
            issues.append("entry.trigger.trigger_price is required for touch_price or breakout")
        if trigger.get("type") == "pullback_into_range":
            trigger_range = trigger.get("trigger_range")
            if not isinstance(trigger_range, dict) or not is_positive_number(trigger_range.get("min")) or not is_positive_number(trigger_range.get("max")):
                issues.append("entry.trigger.trigger_range is required for pullback_into_range")
            elif trigger_range.get("min") >= trigger_range.get("max"):
                issues.append("entry.trigger.trigger_range.min must be less than max")

        price = entry.get("price", {})
        validate_enum(price.get("order_type"), {"market", "limit"}, "entry.price.order_type", issues)
        if price.get("order_type") == "limit" and not is_positive_number(price.get("limit_price")):
            issues.append("entry.price.limit_price is required when order_type is limit")

        acceptable_range = price.get("acceptable_range")
        if acceptable_range is not None:
            if not is_positive_number(acceptable_range.get("min")) or not is_positive_number(acceptable_range.get("max")):
                issues.append("entry.price.acceptable_range.min and max must be greater than 0")
            elif acceptable_range.get("min") >= acceptable_range.get("max"):
                issues.append("entry.price.acceptable_range.min must be less than max")
        timing = entry.get("timing", {})
        if not isinstance(timing.get("expire_after_seconds"), int) or timing.get("expire_after_seconds") <= 0:
            issues.append("entry.timing.expire_after_seconds must be greater than 0")

        stop_loss = exits.get("stop_loss", {})
        validate_enum(stop_loss.get("mode"), {"price", "percent", "none"}, "exits.stop_loss.mode", issues)
        if stop_loss.get("mode") == "price" and not is_positive_number(stop_loss.get("stop_price")):
            issues.append("exits.stop_loss.stop_price is required when mode is price")
        if stop_loss.get("mode") == "percent" and not is_positive_number(stop_loss.get("loss_pct")):
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
            else:
                total_close_ratio = 0.0
                for idx, target in enumerate(targets):
                    if not isinstance(target, dict):
                        issues.append(f"exits.take_profit.targets[{idx}] must be an object")
                        continue
                    if not is_positive_number(target.get("price")):
                        issues.append(f"exits.take_profit.targets[{idx}].price must be greater than 0")
                    if not is_positive_number(target.get("close_ratio")):
                        issues.append(f"exits.take_profit.targets[{idx}].close_ratio must be greater than 0")
                    else:
                        total_close_ratio += float(target.get("close_ratio"))
                if take_profit.get("mode") == "fixed_price":
                    if len(targets) != 1:
                        issues.append("exits.take_profit.targets must contain exactly one item when mode is fixed_price")
                    elif isinstance(targets[0], dict) and targets[0].get("close_ratio") != 1:
                        issues.append("exits.take_profit.targets[0].close_ratio must be 1 when mode is fixed_price")
                if take_profit.get("mode") == "ladder" and total_close_ratio > 1.0000001:
                    issues.append("exits.take_profit.targets close_ratio sum must be less than or equal to 1")

        trailing_stop = exits.get("trailing_stop", {})
        if trailing_stop.get("enabled"):
            validate_enum(
                trailing_stop.get("activation_mode"),
                {"immediate", "after_profit_pct", "after_tp_hit"},
                "exits.trailing_stop.activation_mode",
                issues,
            )
            validate_enum(
                trailing_stop.get("trail_mode"),
                {"percent", "price_delta"},
                "exits.trailing_stop.trail_mode",
                issues,
            )
            validate_enum(
                trailing_stop.get("step_mode"),
                {"continuous", "step"},
                "exits.trailing_stop.step_mode",
                issues,
            )
            if not is_positive_number(trailing_stop.get("trail_value")):
                issues.append("exits.trailing_stop.trail_value must be greater than 0 when trailing_stop is enabled")
            if trailing_stop.get("activation_mode") == "after_profit_pct" and not is_positive_number(trailing_stop.get("activation_profit_pct")):
                issues.append("exits.trailing_stop.activation_profit_pct must be greater than 0 when activation_mode is after_profit_pct")
            if trailing_stop.get("step_mode") == "step" and not is_positive_number(trailing_stop.get("step_value")):
                issues.append("exits.trailing_stop.step_value must be greater than 0 when step_mode is step")

        if exits.get("time_stop", {}).get("enabled") and not exits.get("time_stop", {}).get("max_holding_minutes"):
            issues.append("exits.time_stop.max_holding_minutes is required when time_stop is enabled")

        validate_enum(
            sizing.get("mode"),
            {"target_notional", "risk_budget", "fixed_quantity"},
            "sizing.mode",
            issues,
        )
        if sizing.get("mode") == "target_notional" and not is_positive_number(sizing.get("target_notional")):
            issues.append("sizing.target_notional is required when mode is target_notional")
        if sizing.get("mode") == "risk_budget" and not is_positive_number(sizing.get("target_risk_amount")):
            issues.append("sizing.target_risk_amount is required when mode is risk_budget")
        if sizing.get("mode") == "risk_budget" and stop_loss.get("mode") == "none":
            issues.append("sizing.target_risk_amount requires a stop loss when mode is risk_budget")
        if sizing.get("mode") == "fixed_quantity" and not is_positive_number(sizing.get("target_quantity")):
            issues.append("sizing.target_quantity is required when mode is fixed_quantity")
        if is_positive_number(sizing.get("min_notional")) and is_positive_number(sizing.get("max_notional")) and sizing.get("min_notional") > sizing.get("max_notional"):
            issues.append("sizing.min_notional must be less than or equal to max_notional")
        if is_positive_number(sizing.get("min_notional")) and is_positive_number(sizing.get("target_notional")) and sizing.get("min_notional") > sizing.get("target_notional"):
            issues.append("sizing.min_notional must be less than or equal to target_notional")
        if is_positive_number(sizing.get("min_quantity")) and is_positive_number(sizing.get("max_quantity")) and sizing.get("min_quantity") > sizing.get("max_quantity"):
            issues.append("sizing.min_quantity must be less than or equal to max_quantity")
        if is_positive_number(sizing.get("min_quantity")) and is_positive_number(sizing.get("target_quantity")) and sizing.get("min_quantity") > sizing.get("target_quantity"):
            issues.append("sizing.min_quantity must be less than or equal to target_quantity")
        if is_positive_number(sizing.get("target_notional")) and is_positive_number(sizing.get("max_notional")) and sizing.get("target_notional") > sizing.get("max_notional"):
            issues.append("sizing.target_notional must be less than or equal to max_notional")
        if is_positive_number(sizing.get("target_quantity")) and is_positive_number(sizing.get("max_quantity")) and sizing.get("target_quantity") > sizing.get("max_quantity"):
            issues.append("sizing.target_quantity must be less than or equal to max_quantity")

        if constraints.get("max_slippage_pct") is not None and not is_non_negative_number(constraints.get("max_slippage_pct")):
            issues.append("execution_constraints.max_slippage_pct must be greater than or equal to 0")
        if constraints.get("min_reward_risk") is not None and not is_non_negative_number(constraints.get("min_reward_risk")):
            issues.append("execution_constraints.min_reward_risk must be greater than or equal to 0")
        if constraints.get("quote_staleness_seconds") is not None and (not isinstance(constraints.get("quote_staleness_seconds"), int) or constraints.get("quote_staleness_seconds") < 0):
            issues.append("execution_constraints.quote_staleness_seconds must be greater than or equal to 0")
        if not is_positive_number(constraints.get("max_slippage_pct")) and acceptable_range is None:
            issues.append("either entry.price.acceptable_range or execution_constraints.max_slippage_pct must be present")
        if not position_management.get("allow_add_position", False) and position_management.get("max_add_count", 0) != 0:
            issues.append("position_management.max_add_count must be 0 when allow_add_position is false")
        if position_management.get("max_add_count", 0) < 0:
            issues.append("position_management.max_add_count must be greater than or equal to 0")
        if position_management.get("same_symbol_cooldown_minutes", 0) < 0:
            issues.append("position_management.same_symbol_cooldown_minutes must be greater than or equal to 0")
        if take_profit.get("mode") == "ladder" and not position_management.get("allow_partial_exit", False):
            issues.append("position_management.allow_partial_exit must be true when take_profit.mode is ladder")

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
