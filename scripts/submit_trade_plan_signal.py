#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path


def load_payload(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


FORBIDDEN_REQUEST_FIELDS = {
    "signal_id",
    "proposal_id",
    "trace_id",
    "status",
    "inserted_at",
    "updated_at",
    "strategy_revision",
    "allowed_order_types",
    "submission_channel",
}


def validate_enum(value: object, allowed: set[str], field: str, issues: list[str]) -> None:
    if value is None:
        return
    if value not in allowed:
        values = ", ".join(sorted(allowed))
        issues.append(f"{field} must be one of: {values}")


def is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_positive_number(value: object) -> bool:
    return is_number(value) and value > 0


def is_non_negative_number(value: object) -> bool:
    return is_number(value) and value >= 0


def is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def is_non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def parse_utc_datetime(value: object, field: str, issues: list[str]) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        issues.append(f"{field} must be an ISO 8601 UTC timestamp")
        return None
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        issues.append(f"{field} must be an ISO 8601 UTC timestamp")
        return None
    if parsed.tzinfo is None:
        issues.append(f"{field} must include timezone, preferably UTC Z")
        return None
    return parsed.astimezone(timezone.utc)


def required_object(parent: dict, key: str, field: str, issues: list[str]) -> dict:
    value = parent.get(key)
    if not isinstance(value, dict):
        issues.append(f"{field} must be an object")
        return {}
    return value


def entry_reference_price(entry: dict) -> float | None:
    price = entry.get("price", {})
    trigger = entry.get("trigger", {})
    if is_positive_number(price.get("limit_price")):
        return float(price["limit_price"])
    if is_positive_number(trigger.get("trigger_price")):
        return float(trigger["trigger_price"])
    acceptable_range = price.get("acceptable_range")
    if (
        isinstance(acceptable_range, dict)
        and is_positive_number(acceptable_range.get("min"))
        and is_positive_number(acceptable_range.get("max"))
    ):
        return (float(acceptable_range["min"]) + float(acceptable_range["max"])) / 2
    trigger_range = trigger.get("trigger_range")
    if (
        isinstance(trigger_range, dict)
        and is_positive_number(trigger_range.get("min"))
        and is_positive_number(trigger_range.get("max"))
    ):
        return (float(trigger_range["min"]) + float(trigger_range["max"])) / 2
    return None


def validate(payload: dict) -> list[str]:
    issues = []
    if not isinstance(payload, dict):
        return ["payload must be a JSON object"]

    for key in sorted(FORBIDDEN_REQUEST_FIELDS):
        if key in payload:
            issues.append(f"{key} is server-owned or unsupported and must not be included")

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
    if not is_number(confidence) or confidence < 0 or confidence > 1:
        issues.append("confidence must be a number between 0 and 1")

    evidence = payload.get("evidence")
    if not isinstance(evidence, list) or not any(is_non_empty_string(item) for item in evidence):
        issues.append("evidence must contain at least one non-empty item")

    if not is_non_empty_string(payload.get("signal_reason")):
        issues.append("signal_reason must be a non-empty string")

    created_at = parse_utc_datetime(payload.get("created_at"), "created_at", issues)
    expires_at = parse_utc_datetime(payload.get("expires_at"), "expires_at", issues)
    if created_at and expires_at:
        if expires_at <= created_at:
            issues.append("expires_at must be after created_at")
        if expires_at <= datetime.now(timezone.utc):
            issues.append("expires_at must be in the future")

    if payload.get("position_intent") == "reverse" and not payload.get("replace_existing_position", False):
        issues.append("replace_existing_position must be true when position_intent is reverse")

    trade_params = payload.get("trade_params")
    if isinstance(trade_params, dict):
        for key in ["entry", "exits", "sizing", "position_management", "execution_constraints"]:
            if key not in trade_params:
                issues.append(f"trade_params.{key} is required")

        entry = required_object(trade_params, "entry", "trade_params.entry", issues)
        exits = required_object(trade_params, "exits", "trade_params.exits", issues)
        sizing = required_object(trade_params, "sizing", "trade_params.sizing", issues)
        position_management = required_object(
            trade_params,
            "position_management",
            "trade_params.position_management",
            issues,
        )
        constraints = required_object(
            trade_params,
            "execution_constraints",
            "trade_params.execution_constraints",
            issues,
        )

        for key in ["trigger", "price", "timing"]:
            if key not in entry:
                issues.append(f"entry.{key} is required")
        trigger = required_object(entry, "trigger", "entry.trigger", issues)
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

        price = required_object(entry, "price", "entry.price", issues)
        validate_enum(price.get("order_type"), {"market", "limit"}, "entry.price.order_type", issues)
        if price.get("order_type") == "limit" and not is_positive_number(price.get("limit_price")):
            issues.append("entry.price.limit_price is required when order_type is limit")

        acceptable_range = price.get("acceptable_range")
        if acceptable_range is not None:
            if not isinstance(acceptable_range, dict):
                issues.append("entry.price.acceptable_range must be an object")
            elif not is_positive_number(acceptable_range.get("min")) or not is_positive_number(acceptable_range.get("max")):
                issues.append("entry.price.acceptable_range.min and max must be greater than 0")
            elif acceptable_range.get("min") >= acceptable_range.get("max"):
                issues.append("entry.price.acceptable_range.min must be less than max")
        timing = required_object(entry, "timing", "entry.timing", issues)
        if not is_positive_int(timing.get("expire_after_seconds")):
            issues.append("entry.timing.expire_after_seconds must be greater than 0")

        for key in ["stop_loss", "take_profit", "trailing_stop", "time_stop"]:
            if key not in exits:
                issues.append(f"exits.{key} is required")
        stop_loss = required_object(exits, "stop_loss", "exits.stop_loss", issues)
        validate_enum(stop_loss.get("mode"), {"price", "percent", "none"}, "exits.stop_loss.mode", issues)
        if stop_loss.get("mode") == "price" and not is_positive_number(stop_loss.get("stop_price")):
            issues.append("exits.stop_loss.stop_price is required when mode is price")
        if stop_loss.get("mode") == "percent" and not is_positive_number(stop_loss.get("loss_pct")):
            issues.append("exits.stop_loss.loss_pct is required when mode is percent")

        take_profit = required_object(exits, "take_profit", "exits.take_profit", issues)
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

        trailing_stop = required_object(exits, "trailing_stop", "exits.trailing_stop", issues)
        if "enabled" not in trailing_stop or not isinstance(trailing_stop.get("enabled"), bool):
            issues.append("exits.trailing_stop.enabled must be true or false")
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

        time_stop = required_object(exits, "time_stop", "exits.time_stop", issues)
        if "enabled" not in time_stop or not isinstance(time_stop.get("enabled"), bool):
            issues.append("exits.time_stop.enabled must be true or false")
        if time_stop.get("enabled") and not is_positive_int(time_stop.get("max_holding_minutes")):
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

        margin = trade_params.get("margin")
        if isinstance(margin, dict):
            if margin.get("mode") not in {None, "", "cross"}:
                issues.append("margin.mode must be cross when provided")
            normalized_intent = payload.get("position_intent") or "open"
            if is_positive_number(margin.get("leverage")) and normalized_intent not in {"open", "reverse"}:
                issues.append("margin.leverage is only supported for open or reverse intents")
        elif margin is not None:
            issues.append("margin must be an object when provided")

        if constraints.get("max_slippage_pct") is not None and not is_non_negative_number(constraints.get("max_slippage_pct")):
            issues.append("execution_constraints.max_slippage_pct must be greater than or equal to 0")
        if constraints.get("min_reward_risk") is not None and not is_non_negative_number(constraints.get("min_reward_risk")):
            issues.append("execution_constraints.min_reward_risk must be greater than or equal to 0")
        if constraints.get("quote_staleness_seconds") is not None and not is_non_negative_int(constraints.get("quote_staleness_seconds")):
            issues.append("execution_constraints.quote_staleness_seconds must be greater than or equal to 0")
        if not is_positive_number(constraints.get("max_slippage_pct")) and acceptable_range is None:
            issues.append("either entry.price.acceptable_range or execution_constraints.max_slippage_pct must be present")
        for key in [
            "allow_add_position",
            "max_add_count",
            "allow_partial_exit",
            "allow_reverse_on_opposite_signal",
            "same_symbol_cooldown_minutes",
        ]:
            if key not in position_management:
                issues.append(f"position_management.{key} is required")
        for key in ["allow_add_position", "allow_partial_exit", "allow_reverse_on_opposite_signal"]:
            if key in position_management and not isinstance(position_management.get(key), bool):
                issues.append(f"position_management.{key} must be true or false")
        if "max_add_count" in position_management and not is_non_negative_int(position_management.get("max_add_count")):
            issues.append("position_management.max_add_count must be greater than or equal to 0")
        if "same_symbol_cooldown_minutes" in position_management and not is_non_negative_int(position_management.get("same_symbol_cooldown_minutes")):
            issues.append("position_management.same_symbol_cooldown_minutes must be greater than or equal to 0")
        if not position_management.get("allow_add_position", False) and position_management.get("max_add_count", 0) != 0:
            issues.append("position_management.max_add_count must be 0 when allow_add_position is false")
        if take_profit.get("mode") == "ladder" and not position_management.get("allow_partial_exit", False):
            issues.append("position_management.allow_partial_exit must be true when take_profit.mode is ladder")

        ref_price = entry_reference_price(entry)
        side = payload.get("side")
        if ref_price and side in {"long", "short"}:
            stop_price = stop_loss.get("stop_price")
            if stop_loss.get("mode") == "price" and is_positive_number(stop_price):
                if side == "long" and float(stop_price) >= ref_price:
                    issues.append("exits.stop_loss.stop_price must be below entry reference price for long positions")
                if side == "short" and float(stop_price) <= ref_price:
                    issues.append("exits.stop_loss.stop_price must be above entry reference price for short positions")
            targets = take_profit.get("targets")
            if isinstance(targets, list):
                previous_price = None
                for idx, target in enumerate(targets):
                    if not isinstance(target, dict) or not is_positive_number(target.get("price")):
                        continue
                    target_price = float(target["price"])
                    if side == "long" and target_price <= ref_price:
                        issues.append(f"exits.take_profit.targets[{idx}].price must be above entry reference price for long positions")
                    if side == "short" and target_price >= ref_price:
                        issues.append(f"exits.take_profit.targets[{idx}].price must be below entry reference price for short positions")
                    if take_profit.get("mode") == "ladder" and previous_price is not None:
                        if side == "long" and target_price < previous_price:
                            issues.append("exits.take_profit.targets must be ascending for long ladder exits")
                            break
                        if side == "short" and target_price > previous_price:
                            issues.append("exits.take_profit.targets must be descending for short ladder exits")
                            break
                    previous_price = target_price

        if price.get("order_type") == "limit" and is_positive_number(price.get("limit_price")) and isinstance(acceptable_range, dict):
            limit_price = float(price["limit_price"])
            if payload.get("side") == "long" and is_positive_number(acceptable_range.get("max")) and limit_price > float(acceptable_range["max"]):
                issues.append("entry.price.limit_price must be less than or equal to acceptable_range.max for long positions")
            if payload.get("side") == "short" and is_positive_number(acceptable_range.get("min")) and limit_price < float(acceptable_range["min"]):
                issues.append("entry.price.limit_price must be greater than or equal to acceptable_range.min for short positions")
    else:
        issues.append("trade_params must be an object")

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
