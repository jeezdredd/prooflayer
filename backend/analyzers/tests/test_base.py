import pytest

from analyzers.base import BaseAnalyzer, AnalysisOutput


class TestBaseAnalyzer:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BaseAnalyzer()

    def test_concrete_implementation(self):
        class DummyAnalyzer(BaseAnalyzer):
            name = "dummy"
            version = "0.1"

            def analyze(self, file_path, metadata):
                return AnalysisOutput(confidence=0.5, verdict="authentic", evidence={})

            def supported_mime_types(self):
                return ["image/jpeg"]

        analyzer = DummyAnalyzer()
        result = analyzer.analyze("/fake/path", {})
        assert isinstance(result, AnalysisOutput)
        assert result.confidence == 0.5
        assert result.verdict == "authentic"


class TestAnalysisOutput:
    def test_dataclass_fields(self):
        output = AnalysisOutput(confidence=0.9, verdict="fake", evidence={"key": "val"})
        assert output.confidence == 0.9
        assert output.verdict == "fake"
        assert output.evidence == {"key": "val"}
