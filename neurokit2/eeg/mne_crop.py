import numpy as np


def mne_crop(raw, tmin=0.0, tmax=None, include_tmax=True, smin=None, smax=None):
    """Crop mne.Raw objects.
    Similar to `raw.crop()` but with a few critical differences:
    - It recreates a whole new Raw object, and as such drops all information pertaining to the original data (https://github.com/mne-tools/mne-python/issues/9759).
    - There is the possibility of specifying directly the first and last samples.
    """
    # Try loading mne
    try:
        import mne
    except ImportError:
        raise ImportError(
            "NeuroKit error: eeg_channel_add(): the 'mne' module is required for this function to run. ",
            "Please install it first (`pip install mne`).",
        )

    # Convert time to samples
    if smin is None or smax is None:
        max_time = (raw.n_times - 1) / raw.info["sfreq"]
        if tmax is None:
            tmax = max_time

        if tmin > tmax:
            raise ValueError("tmin (%s) must be less than tmax (%s)" % (tmin, tmax))
        if tmin < 0.0:
            raise ValueError("tmin (%s) must be >= 0" % (tmin,))
        elif tmax > max_time:
            raise ValueError(
                "tmax (%s) must be less than or equal to the max "
                "time (%0.4f sec)" % (tmax, max_time)
            )

        # Convert time to first and last samples
        new_smin, new_smax = np.where(
            _time_mask(raw.times, tmin, tmax, sfreq=raw.info["sfreq"], include_tmax=include_tmax)
        )[0][[0, -1]]

    if smin is None:
        smin = new_smin
    if smax is None:
        smax = new_smax
    if include_tmax:
        smax += 1

    # Re-create the Raw object (note that mne does smin : smin + 1)
    raw = mne.io.RawArray(
        raw._data[:, int(smin) : int(smax)].copy(), raw.info, verbose="WARNING"
    )

    return raw


def _time_mask(times, tmin=None, tmax=None, sfreq=None, raise_error=True, include_tmax=True):
    """Copied from https://github.com/mne-tools/mne-python/mne/utils/numerics.py#L466."""
    orig_tmin = tmin
    orig_tmax = tmax
    tmin = -np.inf if tmin is None else tmin
    tmax = np.inf if tmax is None else tmax
    if not np.isfinite(tmin):
        tmin = times[0]
    if not np.isfinite(tmax):
        tmax = times[-1]
        include_tmax = True  # ignore this param when tmax is infinite
    if sfreq is not None:
        # Push to a bit past the nearest sample boundary first
        sfreq = float(sfreq)
        tmin = int(round(tmin * sfreq)) / sfreq - 0.5 / sfreq
        tmax = int(round(tmax * sfreq)) / sfreq
        tmax += (0.5 if include_tmax else -0.5) / sfreq
    else:
        assert include_tmax  # can only be used when sfreq is known
    if raise_error and tmin > tmax:
        raise ValueError(
            "tmin (%s) must be less than or equal to tmax (%s)" % (orig_tmin, orig_tmax)
        )
    mask = times >= tmin
    mask &= times <= tmax
    if raise_error and not mask.any():
        extra = "" if include_tmax else "when include_tmax=False "
        raise ValueError(
            "No samples remain when using tmin=%s and tmax=%s %s"
            "(original time bounds are [%s, %s])"
            % (orig_tmin, orig_tmax, extra, times[0], times[-1])
        )
    return mask
