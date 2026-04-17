import factory

from analyzers.models import AnalyzerConfig, AnalysisResult
from content.tests.factories import SubmissionFactory


class AnalyzerConfigFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AnalyzerConfig

    name = factory.Sequence(lambda n: f"analyzer_{n}")
    analyzer_class = "analyzers.implementations.metadata_analyzer.MetadataAnalyzer"
    version = "1.0.0"
    is_active = True
    weight = 1.0
    queue = "default"
    timeout = 120


class AnalysisResultFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AnalysisResult

    submission = factory.SubFactory(SubmissionFactory)
    analyzer = factory.SubFactory(AnalyzerConfigFactory)
    confidence = 0.8
    verdict = AnalysisResult.Verdict.AUTHENTIC
    evidence = factory.LazyFunction(dict)
    execution_time = 0.5
