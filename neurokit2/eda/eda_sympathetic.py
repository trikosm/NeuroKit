# -*- coding: utf-8 -*-
import pandas as pd
import scipy
import numpy as np
import matplotlib.pyplot as plt

from ..signal.signal_power import _signal_power_instant_get
from ..signal.signal_psd import _signal_psd_welch
from ..signal import signal_filter, signal_resample
from ..stats import standardize


def eda_sympathetic(eda_signal, sampling_rate=1000, frequency_band=[0.045, 0.25], method='posada', show=False):
    """
    Obtain electrodermal activity (EDA) indexes of sympathetic nervous system.

    Derived from Posada-Quintero et al. (2016), who argue that dynamics of the sympathetic component
    of EDA signal is represented in the frequency band of 0.045-0.25Hz.
    See https://biosignal.uconn.edu/wp-content/uploads/sites/2503/2018/09/09_Posada_2016_AnnalsBME.pdf

    Parameters
    ----------
    eda_signal : Union[list, np.array, pd.Series]
        The EDA signal (i.e., a time series) in the form of a vector of values.
    sampling_rate : int
        The sampling frequency of the signal (in Hz, i.e., samples/second).
    frequency_band : list
        List indicating the frequency range to compute the the power spectral density in.
        Defaults to [0.045, 0.25].
    method : str
        Can be one of 'ghiasi' or 'posada'.
    show : bool
        If True, will return a plot.

    See Also
    --------
    signal_filter, signal_power, signal_psd

    Returns
    -------
    dict
        A dictionary containing the EDA symptathetic indexes, accessible by keys 'EDA_Symp' and
        'EDA_SympN' (normalized, obtained by dividing EDA_Symp by total power).
        Plots power spectrum of the EDA signal within the specified frequency band if `show` is True.

    Examples
    --------
    >>> import neurokit2 as nk
    >>>
    >>> eda = nk.data('bio_resting_8min_100hz')['EDA']
    >>> indexes_posada = nk.eda_sympathetic(eda, sampling_rate=100, method='posada', show=True)
    >>> indexes_ghiasi = nk.eda_sympathetic(eda, sampling_rate=100, method='ghiasi', show=True)

    References
    ----------
    - Ghiasi, S., Grecol, A., Nardelli, M., Catrambonel, V., Barbieri, R., Scilingo, E., & Valenza, G. (2018).
    A New Sympathovagal Balance Index from Electrodermal Activity and Instantaneous Vagal Dynamics: A Preliminary
    Cold Pressor Study. 2018 40th Annual International Conference of the IEEE Engineering in Medicine and Biology
    Society (EMBC). doi:10.1109/embc.2018.8512932
    - Posada-Quintero, H. F., Florian, J. P., Orjuela-Cañón, A. D., Aljama-Corrales, T.,
    Charleston-Villalobos, S., & Chon, K. H. (2016). Power spectral density analysis of electrodermal
    activity for sympathetic function assessment. Annals of biomedical engineering, 44(10), 3124-3135.

    """

    out = {}

    if method.lower() in ["ghiasi"]:
        out = _eda_sympathetic_ghiasi(eda_signal, sampling_rate=sampling_rate, frequency_band=frequency_band, show=show)
    elif method.lower() in ["posada", "posada-quintero", "quintero"]:
        out = _eda_sympathetic_posada(eda_signal, frequency_band=frequency_band, show=show)
    else:
        raise ValueError("NeuroKit error: eda_sympathetic(): 'method' should be "
                         "one of 'ghiasi', 'posada'.")

    return out


# =============================================================================
# Methods
# =============================================================================

def _eda_sympathetic_posada(eda_signal, frequency_band=[0.045, 0.25], show=True, out={}):

    # First step of downsampling
    downsampled_1 = scipy.signal.decimate(eda_signal, q=10, n=8)  # Keep every 10th sample
    downsampled_2 = scipy.signal.decimate(downsampled_1, q=20, n=8)  # Keep every 20th sample

    # High pass filter
    eda_filtered = signal_filter(downsampled_2, sampling_rate=2,
                                 lowcut=0.01, method="butterworth", order=8)

    overlap = len(eda_filtered) // 2  # 50 % data overlap

    # Compute psd
    frequency, power = _signal_psd_welch(eda_filtered, sampling_rate=2,
                                         nperseg=128, window_type='blackman', noverlap=overlap, norm=False)
    psd = pd.DataFrame({"Frequency": frequency, "Power": power})

    # Get sympathetic nervous system indexes
    eda_symp = _signal_power_instant_get(psd, frequency_band=[frequency_band[0], frequency_band[1]])
    eda_symp = eda_symp.get('0.04-0.25Hz')

    # Compute normalized psd
    psd['Power'] /= np.max(psd['Power'])
    eda_symp_normalized = _signal_power_instant_get(psd, frequency_band=[frequency_band[0],
                                                                         frequency_band[1]]).get('0.04-0.25Hz')

    psd_plot = psd.loc[np.logical_and(psd["Frequency"] >= frequency_band[0], psd["Frequency"] <= frequency_band[1])]

    if show is True:
        ax = psd_plot.plot(x="Frequency", y="Power", title="EDA Power Spectral Density (ms^2/Hz)")
        ax.set(xlabel="Frequency (Hz)", ylabel="Spectrum")

    out = {'EDA_Symp': eda_symp, 'EDA_SympN': eda_symp_normalized}

    return out


def _eda_sympathetic_ghiasi(eda_signal, sampling_rate=1000, frequency_band=[0.045, 0.25], show=True, out={}):

    min_frequency = frequency_band[0]
    max_frequency = frequency_band[1]

    # Normalize, downsample, filter
    normalized = standardize(eda_signal)
    downsampled = signal_resample(normalized, sampling_rate=sampling_rate, desired_sampling_rate=50)
    filtered = signal_filter(downsampled, sampling_rate=sampling_rate, lowcut=0.01, highcut=0.5, method='butterworth')

    # Divide the signal into segments and obtain the timefrequency representation
    nperseg = int((5 / min_frequency) * sampling_rate)
    overlap = 59 / 50  # overlap of 59s in samples
    frequency, time, bins = scipy.signal.spectrogram(filtered, fs=sampling_rate, window='blackman', nperseg=nperseg,
                                                     noverlap=overlap)

    lower_bound = len(frequency) - len(frequency[frequency > min_frequency])
    f = frequency[(frequency > min_frequency) & (frequency < max_frequency)]
    z = bins[lower_bound:lower_bound + len(f)]

    # Visualization
    if show is True:
        fig = plt.figure()
        spec = plt.pcolormesh(time, f, np.abs(z),
                              cmap=plt.get_cmap("viridis"))
        plt.colorbar(spec)
        plt.title('STFT Magnitude')
        plt.ylabel('Frequency (Hz)')
        plt.xlabel('Time (sec)')

        fig, ax = plt.subplots()
        for i in range(len(time)):
            ax.plot(f, np.abs(z[:, i]), label="Segment" + str(np.arange(len(time))[i] + 1))
        ax.legend()
        ax.set_title('Power Spectrum Density (PSD)')
        ax.set_ylabel('PSD (ms^2/Hz)')
        ax.set_xlabel('Frequency (Hz)')

    eda_symp = np.mean(z)
    eda_symp_normalized = eda_symp / np.max(bins)

    out = {'EDA_Symp': eda_symp, 'EDA_SympN': eda_symp_normalized}

    return out
