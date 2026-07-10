"""
Pure-Python pitch detector using the YIN algorithm (cumulative mean
normalized difference function, de Cheveigne & Kawahara 2002).

v2.5.1: switched from plain normalized autocorrelation to YIN following
a user-requested accuracy review. Motivation: this add-on has to work
across a wide range of microphone quality (built-in laptop mics,
cheap USB mics, headsets), so the fix had to be purely algorithmic
rather than raising confidence/stability thresholds - tightening
thresholds would only have made low-quality mics report "no reading"
more often, without making anyone's readings more accurate. YIN's
normalization (dividing by the running mean of the difference function
rather than by signal energy) makes its absolute threshold behave more
consistently across different input levels/noise floors than raw
normalized autocorrelation, and it is the standard reference algorithm
for monophonic pitch tracking specifically because of that robustness.
A Hann window was tried as an additional polish (tapering the edges of
each analysis frame to reduce edge artefacts) but was measured out in
v2.5.1's own accuracy testing: on synthetic reference tones it added a
consistent sharp bias on the low strings that matter most for guitar
tuning (E2/A2, roughly +2-3 cents extra vs. no window) with no
measurable noise-robustness benefit in the same tests, so it was not
kept. See _difference_function - it now operates directly on the
centered samples, unwindowed.

The octave-error fix from the previous implementation (prefer the
FIRST strong candidate scanning from the shortest lag/highest frequency
upward, rather than the single strongest one) carries over unchanged -
it's actually the core idea of YIN's own "absolute threshold" step, so
this rewrite keeps that behaviour rather than replacing it.

No numpy / external deps - must run inside NVDA's bundled Python with
only the standard library available (matches the existing add-on's
dependency style: stdlib + wx + winsound only). Computational cost
stays O(n * max_lag), same as the autocorrelation it replaces - the
difference function is computed via the same energy/cross-correlation
running-sum trick as before, so this is not a slower detector.
"""
import math


def _difference_function(samples, min_lag, max_lag):
    """YIN step 1: raw difference function d(lag) = sum((x[i]-x[i+lag])^2)
    over the overlapping window, for lag in [min_lag, max_lag]. Expanded
    algebraically to energy_a + energy_b - 2*cross so it can reuse a
    prefix-sum-of-squares table, same O(n) per lag as the normalized
    autocorrelation this replaces (no slowdown from the algorithm
    switch)."""
    n = len(samples)
    prefix_sq = [0.0] * (n + 1)
    for i in range(n):
        prefix_sq[i + 1] = prefix_sq[i] + samples[i] * samples[i]

    results = []
    for lag in range(min_lag, max_lag + 1):
        if lag >= n:
            break
        limit = n - lag
        cross = 0.0
        for i in range(limit):
            cross += samples[i] * samples[i + lag]
        energy_a = prefix_sq[limit]
        energy_b = prefix_sq[n] - prefix_sq[lag]
        d = energy_a + energy_b - 2.0 * cross
        results.append((lag, d))
    return results


def _cumulative_mean_normalized(diffs):
    """YIN step 2: cumulative mean normalized difference function
    (CMNDF). d(0) is defined as 1 by convention; for lag k (1-indexed
    within the scanned band here since we only ever compute a
    band-limited range around the target/expected frequency, same
    band-limiting the previous autocorrelation implementation already
    did for speed), cmndf(k) = d(k) / (running_mean_of_d_so_far). This
    normalization is what lets a single absolute threshold work
    consistently regardless of signal level or microphone gain -
    unlike a raw difference or raw correlation value, CMNDF is already
    scaled relative to how "generally different" nearby lags are."""
    running = 0.0
    out = []
    for k, (lag, d) in enumerate(diffs):
        running += d
        mean_so_far = running / (k + 1)
        cmndf = 1.0 if mean_so_far <= 1e-12 else (d / mean_so_far)
        out.append((lag, cmndf))
    return out


def _pick_best_lag(cmndf, threshold):
    """YIN steps 3-4 (absolute threshold + local minimum). Scan from the
    shortest lag (highest frequency) upward for the first dip below
    `threshold`, then descend to the bottom of that dip. This is what
    makes YIN resistant to octave errors: the true fundamental's dip is
    encountered before any subharmonic dip at 2x/3x the period, so the
    search accepts it first instead of continuing on to a lower,
    possibly deeper, subharmonic minimum."""
    n = len(cmndf)
    for i in range(n):
        lag, val = cmndf[i]
        if val < threshold:
            j = i
            while j + 1 < n and cmndf[j + 1][1] <= cmndf[j][1]:
                j += 1
            return cmndf[j][0], cmndf[j][1], j
    # Nothing cleared the threshold - fall back to the global minimum so
    # the caller still gets *something*, but the caller should treat a
    # high cmndf value (=low confidence) here as an unreliable reading.
    idx = min(range(n), key=lambda k: cmndf[k][1])
    return cmndf[idx][0], cmndf[idx][1], idx


def detect_pitch(samples, sample_rate, fmin=35.0, fmax=1500.0, confidence_threshold=0.35):
    """
    samples: list/sequence of floats, roughly in range [-1, 1], mono.
    sample_rate: int Hz.
    confidence_threshold: 0..1 scale where 1.0 means a perfectly
    periodic signal, kept on the same higher-is-better scale as the
    previous autocorrelation-based detector (computed here as
    1 - CMNDF) so existing callers and their tuned threshold constants
    do not need to change.
    Returns detected frequency in Hz, or None if no reliable pitch found.
    """
    n = len(samples)
    if n < 32:
        return None

    mean = sum(samples) / n
    centered = [s - mean for s in samples]

    energy = sum(s * s for s in centered) / n
    if energy < 1e-7:
        return None  # silence / near-silence

    min_lag = max(1, int(sample_rate / fmax))
    max_lag = min(n - 2, int(sample_rate / fmin))
    if max_lag <= min_lag:
        return None

    diffs = _difference_function(centered, min_lag, max_lag)
    if not diffs:
        return None

    cmndf = _cumulative_mean_normalized(diffs)

    # Convert the caller's higher-is-better confidence_threshold to
    # YIN's own lower-is-better CMNDF scale.
    yin_threshold = 1.0 - confidence_threshold

    best_lag, best_val, idx = _pick_best_lag(cmndf, yin_threshold)
    confidence = 1.0 - best_val
    if confidence < confidence_threshold:
        return None

    # Parabolic interpolation using neighbours for sub-sample lag precision
    if 0 < idx < len(cmndf) - 1:
        _, y0 = cmndf[idx - 1]
        _, y1 = cmndf[idx]
        _, y2 = cmndf[idx + 1]
        denom = (y0 - 2 * y1 + y2)
        if denom != 0:
            shift = 0.5 * (y0 - y2) / denom
            if -1.0 < shift < 1.0:
                best_lag = best_lag + shift

    if best_lag <= 0:
        return None

    freq = sample_rate / best_lag
    return freq


def decimate(samples, factor):
    """Very simple box-filter decimation: average every `factor` samples
    into one, then subsample. Cheap anti-aliasing adequate for pitch
    detection purposes (we only care about low-frequency fundamentals, not
    audio fidelity) - keeps the O(n * max_lag) analysis affordable
    on modest hardware by shrinking both n and max_lag for a given
    frequency range."""
    if factor <= 1:
        return list(samples)
    n = len(samples)
    out_len = n // factor
    out = [0.0] * out_len
    for i in range(out_len):
        start = i * factor
        acc = 0.0
        for j in range(factor):
            acc += samples[start + j]
        out[i] = acc / factor
    return out
