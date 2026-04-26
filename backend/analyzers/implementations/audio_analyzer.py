import logging

import numpy as np

from analyzers.base import AnalysisOutput, BaseAnalyzer

logger = logging.getLogger(__name__)


class AudioSpectrogramAnalyzer(BaseAnalyzer):
    name = "audio_spectrogram"
    version = "1.1.0"

    def supported_mime_types(self) -> list[str]:
        return ["audio/mpeg", "audio/wav", "audio/x-wav", "audio/ogg", "audio/flac", "audio/mp4"]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        try:
            import librosa
        except ImportError:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": "librosa not installed"})

        try:
            y, sr = librosa.load(file_path, sr=22050, mono=True, duration=60.0)
        except Exception as exc:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": str(exc)})

        if len(y) < sr * 2:
            return AnalysisOutput(confidence=0.5, verdict="inconclusive", evidence={"reason": "audio too short"})

        flags = []
        evidence = {}

        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        mfcc_std = float(np.mean(np.std(mfcc, axis=1)))
        evidence["mfcc_variation"] = round(mfcc_std, 4)
        if mfcc_std < 8.0:
            flags.append("low_mfcc_variation")

        flatness = librosa.feature.spectral_flatness(y=y)
        mean_flatness = float(np.mean(flatness))
        evidence["spectral_flatness"] = round(mean_flatness, 6)
        if mean_flatness > 0.15:
            flags.append("high_spectral_flatness")

        zcr = librosa.feature.zero_crossing_rate(y)
        zcr_std = float(np.std(zcr))
        evidence["zcr_std"] = round(zcr_std, 6)
        if zcr_std < 0.02:
            flags.append("low_zcr_variation")

        try:
            f0, voiced_flag, _ = librosa.pyin(y, fmin=50, fmax=500, sr=sr)
            voiced_f0 = f0[voiced_flag]
            if len(voiced_f0) > 10:
                pitch_std = float(np.std(voiced_f0))
                evidence["pitch_std"] = round(pitch_std, 2)
                if pitch_std < 10.0:
                    flags.append("low_pitch_variation")
            else:
                evidence["pitch_std"] = None
        except Exception:
            evidence["pitch_std"] = None

        rms = librosa.feature.rms(y=y)
        rms_std = float(np.std(rms))
        evidence["rms_std"] = round(rms_std, 6)
        if rms_std < 0.005:
            flags.append("unnatural_volume_consistency")

        stft = np.abs(librosa.stft(y))
        stft_norm = stft / (stft.sum(axis=0, keepdims=True) + 1e-9)
        spectral_entropy = float(np.mean(-np.sum(stft_norm * np.log2(stft_norm + 1e-9), axis=0)))
        evidence["spectral_entropy"] = round(spectral_entropy, 4)
        if spectral_entropy > 9.5:
            flags.append("unnaturally_high_spectral_entropy")

        noise_floor = float(np.percentile(np.abs(y), 5))
        evidence["noise_floor"] = round(noise_floor, 8)
        if noise_floor < 1e-5:
            flags.append("near_zero_noise_floor")

        evidence["flags"] = flags
        flag_count = len(flags)

        if flag_count >= 4:
            verdict = "fake"
            confidence = 0.85
        elif flag_count == 3:
            verdict = "suspicious"
            confidence = 0.70
        elif flag_count == 2:
            verdict = "suspicious"
            confidence = 0.60
        elif flag_count == 1:
            verdict = "inconclusive"
            confidence = 0.45
        else:
            verdict = "inconclusive"
            confidence = 0.35

        return AnalysisOutput(confidence=confidence, verdict=verdict, evidence=evidence)
