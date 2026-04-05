from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from math import sqrt
from statistics import mean, stdev
from typing import Iterable, Sequence


TRADING_DAYS_PER_YEAR = 252
MIN_EQUITY_OBSERVATIONS = 2
MIN_SHARPE_OBSERVATIONS = 3
MIN_CAGR_OBSERVATIONS = 2


@dataclass(frozen=True)
class RunMetrics:
    sharpe_ratio: float | None
    max_drawdown: float
    cagr: float | None
    total_return: float
    starting_equity: float
    ending_equity: float
    observations: int
    caveats: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, float | int | list[str] | None]:
        payload = asdict(self)
        payload["caveats"] = list(self.caveats)
        return payload


def _coerce_equity_values(
    equity_values: Iterable[float],
    *,
    minimum_observations: int = MIN_EQUITY_OBSERVATIONS,
) -> list[float]:
    values = [float(value) for value in equity_values]
    if len(values) < minimum_observations:
        raise ValueError(f"At least {minimum_observations} equity observations are required.")
    if any(value <= 0 for value in values):
        raise ValueError("Equity values must be positive.")
    return values


def _coerce_dates(dates: Sequence[str]) -> list[str]:
    normalized_dates: list[str] = []
    parsed_dates: list[date] = []
    seen_dates: set[date] = set()

    for raw_date in dates:
        if not isinstance(raw_date, str):
            raise ValueError("Dates must be ISO-8601 strings.")
        try:
            parsed_date = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise ValueError(f"Invalid ISO-8601 date: {raw_date}") from exc
        if parsed_date in seen_dates:
            raise ValueError(f"Duplicate date detected: {raw_date}")
        if parsed_dates and parsed_date <= parsed_dates[-1]:
            raise ValueError("Dates must be strictly increasing.")
        normalized_dates.append(raw_date)
        parsed_dates.append(parsed_date)
        seen_dates.add(parsed_date)

    if len(normalized_dates) < MIN_EQUITY_OBSERVATIONS:
        raise ValueError(f"At least {MIN_EQUITY_OBSERVATIONS} dates are required.")
    return normalized_dates


def validate_equity_curve(
    equity_curve: Sequence[dict[str, float | str]],
    *,
    minimum_observations: int = MIN_EQUITY_OBSERVATIONS,
) -> list[dict[str, float | str]]:
    if len(equity_curve) < minimum_observations:
        raise ValueError(f"At least {minimum_observations} equity observations are required.")

    dates = [str(point["date"]) for point in equity_curve]
    _coerce_dates(dates)
    equity_values = _coerce_equity_values(
        [float(point["equity"]) for point in equity_curve],
        minimum_observations=minimum_observations,
    )
    return [
        {"date": curve_date, "equity": equity_value}
        for curve_date, equity_value in zip(dates, equity_values)
    ]


def daily_returns_from_equity(equity_values: Iterable[float]) -> list[float]:
    values = _coerce_equity_values(equity_values)
    returns: list[float] = []
    for previous, current in zip(values, values[1:]):
        returns.append((current / previous) - 1.0)
    return returns


def calculate_total_return(equity_values: Iterable[float]) -> float:
    values = _coerce_equity_values(equity_values)
    return (values[-1] / values[0]) - 1.0


def calculate_cagr(
    equity_values: Iterable[float],
    trading_days_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    values = _coerce_equity_values(
        equity_values,
        minimum_observations=MIN_CAGR_OBSERVATIONS,
    )
    elapsed_days = len(values) - 1
    if elapsed_days <= 0:
        raise ValueError("CAGR requires at least two equity observations.")
    annualization_years = elapsed_days / trading_days_per_year
    return (values[-1] / values[0]) ** (1 / annualization_years) - 1.0


def calculate_sharpe_ratio(
    equity_values: Iterable[float],
    risk_free_rate: float = 0.0,
    trading_days_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    values = _coerce_equity_values(
        equity_values,
        minimum_observations=MIN_SHARPE_OBSERVATIONS,
    )
    returns = daily_returns_from_equity(values)
    daily_risk_free_rate = risk_free_rate / trading_days_per_year
    excess_returns = [daily_return - daily_risk_free_rate for daily_return in returns]
    volatility = stdev(excess_returns)
    if volatility == 0:
        return 0.0
    return (mean(excess_returns) / volatility) * sqrt(trading_days_per_year)


def calculate_max_drawdown(equity_values: Iterable[float]) -> float:
    values = _coerce_equity_values(equity_values)
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        drawdown = (value / peak) - 1.0
        max_drawdown = min(max_drawdown, drawdown)
    return max_drawdown


def build_equity_curve(
    dates: Sequence[str],
    equity_values: Sequence[float],
) -> list[dict[str, float | str]]:
    if len(dates) != len(equity_values):
        raise ValueError("Dates and equity values must have the same length.")
    normalized_dates = _coerce_dates(dates)
    values = _coerce_equity_values(equity_values)
    return [
        {"date": curve_date, "equity": equity_value}
        for curve_date, equity_value in zip(normalized_dates, values)
    ]


def build_metrics_summary(
    equity_curve: Sequence[dict[str, float | str]],
    risk_free_rate: float = 0.0,
    trading_days_per_year: int = TRADING_DAYS_PER_YEAR,
) -> RunMetrics:
    validated_curve = validate_equity_curve(equity_curve)
    equity_values = [float(point["equity"]) for point in validated_curve]
    caveats: list[str] = []

    sharpe_ratio: float | None = None
    if len(equity_values) >= MIN_SHARPE_OBSERVATIONS:
        sharpe_ratio = calculate_sharpe_ratio(
            equity_values,
            risk_free_rate=risk_free_rate,
            trading_days_per_year=trading_days_per_year,
        )
    else:
        caveats.append(
            "Sharpe ratio omitted: requires at least 3 equity observations (2 daily returns)."
        )

    cagr: float | None = None
    if len(equity_values) >= MIN_CAGR_OBSERVATIONS:
        cagr = calculate_cagr(equity_values, trading_days_per_year=trading_days_per_year)
        if len(equity_values) < TRADING_DAYS_PER_YEAR + 1:
            caveats.append(
                "CAGR is annualized from fewer than 252 trading days, so short samples can look extreme."
            )
    else:
        caveats.append("CAGR omitted: requires at least 2 equity observations.")

    return RunMetrics(
        sharpe_ratio=sharpe_ratio,
        max_drawdown=calculate_max_drawdown(equity_values),
        cagr=cagr,
        total_return=calculate_total_return(equity_values),
        starting_equity=equity_values[0],
        ending_equity=equity_values[-1],
        observations=len(equity_values),
        caveats=tuple(caveats),
    )
