# Human-like jitter for keystroke playback
# ---------------------------------------
# Suggested defaults: min_hold_s=0.030, min_repeat_same_key_s=0.060
# Recommended ranges: factor_time 0.02–0.10, factor_hold 0.05–0.15

from __future__ import annotations
import random
from collections import defaultdict
from typing import DefaultDict

class HumanJitter:
    def __init__(
        self,
        *,
        factor_time: float = 0.0,     # fraction of anchor for press-time jitter
        factor_hold: float = 0.0,     # fraction of hold for hold jitter (unchanged)
        drift_strength: float = 0.80, # AR(1) rho
        drift_ratio: float = 0.35,    # portion of factor reserved for drift
        clip_sigma: float = 3.0,      # truncate normal at ±clip_sigma·sigma
        # New knobs for more subtle time jitter
        time_floor_s: float = 0.040,  # below this anchor, strongly attenuate
        time_soft_s: float  = 0.200,  # reach full effect around this anchor
        abs_cap_time_s: float = 0.012,# hard absolute cap for timing jitter
        seed: int | None = None,
    ) -> None:
        self.ft = max(0.0, float(factor_time))
        self.fh = max(0.0, float(factor_hold))
        self.rho = max(0.0, min(0.999, float(drift_strength)))
        self.dratio = max(0.0, min(0.95, float(drift_ratio)))
        self.clip = max(1.0, float(clip_sigma))
        self.floor = max(0.0, float(time_floor_s))
        self.soft  = max(self.floor + 1e-6, float(time_soft_s))
        self.abs_cap = max(0.0, float(abs_cap_time_s))
        self.rng = random.Random(seed)
        self._drift_time: DefaultDict[int, float] = defaultdict(float)
        self._drift_hold: DefaultDict[int, float] = defaultdict(float)

    # ---- internals ----
    def _trunc_norm(self, sigma: float) -> float:
        if sigma <= 0.0:
            return 0.0
        x = self.rng.gauss(0.0, sigma)
        lim = self.clip * sigma
        if x >  lim: x =  lim
        if x < -lim: x = -lim
        return x

    def _smoothstep01(self, x: float) -> float:
        # map x in [0,1] -> smooth 0..1 curve
        x = 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)
        return x * x * (3.0 - 2.0 * x)

    def _atten_from_anchor(self, anchor_s: float) -> float:
        # 0 near floor (fast taps), approaching 1 near/after soft (slow taps)
        if anchor_s <= self.floor:
            return 0.20  # leave a tiny residual so repeats don't become perfectly rigid
        if anchor_s >= self.soft:
            return 1.0
        x = (anchor_s - self.floor) / (self.soft - self.floor)
        return 0.20 + 0.80 * self._smoothstep01(x)  # 0.2 .. 1.0

    def _jitter_frac(self, key: int, factor: float, drift_store: DefaultDict[int, float], *, atten: float = 1.0) -> float:
        # dimensionless fraction in [-factor, +factor], scaled by atten
        if factor <= 0.0 or atten <= 0.0:
            return 0.0
        eff = factor * atten
        micro_sigma = (eff * (1.0 - self.dratio)) / self.clip
        drift_sigma = (eff * self.dratio * atten) / self.clip  # attenuate drift too
        d_prev = drift_store[key]
        d_new  = self.rho * d_prev + self._trunc_norm(drift_sigma)
        drift_store[key] = d_new
        micro = self._trunc_norm(micro_sigma)
        frac = d_new + micro
        # hard-cap within ±eff
        if frac >  eff: frac =  eff
        if frac < -eff: frac = -eff
        return frac

    # ---- public API ----
    def time_jitter(self, usage: int, base_anchor_s: float) -> float:
        """Additive jitter (seconds) for press time of a key.
        Scales with inter-press anchor and is attenuated for fast repeats.
        """
        if base_anchor_s <= 0.0 or self.ft <= 0.0:
            return 0.0
        atten = self._atten_from_anchor(base_anchor_s)
        frac = self._jitter_frac(usage, self.ft, self._drift_time, atten=atten)
        delta = base_anchor_s * frac
        # absolute cap to keep it subtle in all regimes
        cap = min(self.abs_cap, abs(self.ft) * base_anchor_s * 1.25)
        if   delta >  cap: delta =  cap
        elif delta < -cap: delta = -cap
        return delta

    def hold_jitter(self, usage: int, base_hold_s: float) -> float:
        if base_hold_s <= 0.0 or self.fh <= 0.0:
            return 0.0
        # keep hold behaviour same (no cadence attenuation needed)
        frac = self._jitter_frac(usage ^ 0x9E3779B9, self.fh, self._drift_hold, atten=1.0)
        delta = base_hold_s * frac
        return delta

