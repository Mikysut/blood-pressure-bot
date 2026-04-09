import io
from datetime import datetime, timedelta
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


PERIODS = {
    "week": 7,
    "month": 30,
    "3months": 90,
}

PERIOD_LABELS = {
    "week": "7 дней",
    "month": "30 дней",
    "3months": "90 дней",
}


def build_chart(measurements: list[dict], period: str) -> io.BytesIO:
    dates = []
    systolic_vals = []
    diastolic_vals = []
    pulse_vals = []

    for m in measurements:
        dt = datetime.fromisoformat(m["measured_at"])
        dates.append(dt)
        systolic_vals.append(m["systolic"])
        diastolic_vals.append(m["diastolic"])
        if m["pulse"] is not None:
            pulse_vals.append((dt, m["pulse"]))

    fig, ax1 = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#f8f9fa")
    ax1.set_facecolor("#ffffff")

    ax1.plot(dates, systolic_vals, color="#e74c3c", linewidth=2, marker="o", markersize=4, label="Систолическое")
    ax1.plot(dates, diastolic_vals, color="#3498db", linewidth=2, marker="o", markersize=4, label="Диастолическое")

    ax1.set_ylabel("Давление (мм рт. ст.)", color="#333333")
    ax1.tick_params(axis="y", labelcolor="#333333")
    ax1.set_ylim(40, 220)

    ax1.axhspan(60, 80, alpha=0.07, color="#3498db")
    ax1.axhspan(90, 120, alpha=0.07, color="#e74c3c")

    if pulse_vals:
        ax2 = ax1.twinx()
        p_dates, p_vals = zip(*pulse_vals)
        ax2.plot(p_dates, p_vals, color="#2ecc71", linewidth=1.5, marker="s", markersize=3,
                 linestyle="--", label="Пульс")
        ax2.set_ylabel("Пульс (уд/мин)", color="#2ecc71")
        ax2.tick_params(axis="y", labelcolor="#2ecc71")
        ax2.set_ylim(30, 160)
        ax2.legend(loc="upper right")

    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    fig.autofmt_xdate()

    ax1.set_title(f"Давление за {PERIOD_LABELS.get(period, period)} (МСК)", fontsize=14, pad=12)
    ax1.legend(loc="upper left")
    ax1.grid(True, linestyle="--", alpha=0.4)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120)
    buf.seek(0)
    plt.close(fig)
    return buf
