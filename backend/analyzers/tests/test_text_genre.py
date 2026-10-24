import pytest

from analyzers.aggregator import aggregate
from analyzers.implementations.text_signals import TextGenreAnalyzer
from analyzers.models import AnalysisResult
from analyzers.text.genre import detect_genre
from analyzers.text.language import detect_language
from content.tests.factories import SubmissionFactory

from .factories import AnalysisResultFactory, AnalyzerConfigFactory

SAMPLES = {
    "argument": (
        "Нужно ли читать книги в эпоху интернета? Я считаю, что нужно. Во-первых, книги развивают воображение и учат "
        "думать. Во-вторых, чтение расширяет словарный запас. Например, мой друг стал лучше писать сочинения, когда начал "
        "читать каждый день. Кроме того, книги помогают понять других людей. Таким образом, чтение остаётся важным и сегодня."
    ),
    "retelling": (
        "В рассказе «Муму» Тургенев описывает жизнь глухонемого дворника Герасима. Однажды Герасим спас из реки маленькую "
        "собачку и назвал её Муму. Потом барыня узнала о собаке и приказала от неё избавиться. Главный герой долго не мог "
        "решиться, но затем выполнил приказ. После этого Герасим ушёл пешком в свою деревню."
    ),
    "description": (
        "На картине Левитана «Золотая осень» изображена берёзовая роща. На переднем плане течёт узкая речка, вдали видны "
        "поля и деревня. Слева стоят золотые берёзы, справа зеленеет поле. Художник использует яркие жёлтые и голубые "
        "краски, и осень кажется праздничной."
    ),
    "narrative": (
        "Last summer I went to my grandma house in the village. One day me and my brother went to the river and suddenly "
        "we saw a huge fish. Then we ran home to get a net. The next day we caught it and grandma cooked it for dinner. "
        "That day was the best day of my summer."
    ),
    "letter": (
        "Chère Marie,\nJe t'écris de Lyon où je passe mes vacances. Il fait très beau et nous visitons beaucoup de musées. "
        "Hier, nous avons mangé dans un petit restaurant près du fleuve. J'espère que tu vas bien et que tes vacances sont "
        "agréables.\nJe t'embrasse,\nLéa"
    ),
    "report": (
        "Introduction\nClimate change affects agriculture in many ways. In 2020, yields fell by 12% in southern regions.\n"
        "Methods\nWe compared data from 1990 to 2020 for 40 farms across the country and measured rainfall.\n"
        "Results\nRainfall dropped by 18% and yields by 9% on average.\nConclusion\nAdaptation is needed.\n"
        "References\nSmith, J. (2019). Crops and climate in a warming world. Oxford University Press."
    ),
    "analysis": (
        "В стихотворении Лермонтова «Парус» автор использует образ одинокого паруса как символ мятежной души. Тема "
        "одиночества и поиска раскрывается через метафоры моря и бури. Композиция строится на контрасте спокойствия и "
        "тревоги. Автор показывает, что герой ищет бури, потому что покой ему чужд."
    ),
    "poem": (
        "The night is quiet and the moon is high\nI walk alone beneath the silver sky\nThe trees are whispering a gentle "
        "song\nI feel the wind and know where I belong\nThe river sleeps beside the sleeping town\nThe stars like candles "
        "slowly drifting down\nI close my eyes and let the darkness stay\nAnd wait in silence for another day"
    ),
}


class TestDetectGenre:
    @pytest.mark.parametrize("genre", sorted(SAMPLES))
    def test_recognises_school_genres(self, genre):
        text = SAMPLES[genre]
        assert detect_genre(text, detect_language(text)).key == genre

    def test_cue_inside_another_word_does_not_count(self):
        text = SAMPLES["analysis"]
        assert "потом" not in detect_genre(text, detect_language(text)).cues

    def test_cues_belong_to_the_recognised_genre(self):
        text = (
            "This week's lab on the Stroop task was more fun than I expected. I honestly thought I would be fast at naming "
            "ink colours, but my times were awful. My partner was even slower. What surprised me is how hard it is to ignore "
            "reading. I have been reading for fifteen years, so my brain does it whether I want it to or not. I think that is "
            "the whole point of the effect."
        )
        genre = detect_genre(text, detect_language(text))
        assert genre.key == "narrative"
        assert "i think" not in genre.cues
        assert genre.cues == ["first-person account"]

    def test_argument_cues_stay_with_argument(self):
        text = SAMPLES["argument"]
        cues = detect_genre(text, detect_language(text)).cues
        assert "я считаю" in cues and "во-первых" in cues

    def test_short_answer_with_one_date_is_not_a_report(self):
        text = "Война 1812 года началась летом. Наполеон дошёл до Москвы, но русская армия его остановила."
        assert detect_genre(text, detect_language(text)).key != "report"

    def test_report_explains_itself(self):
        text = SAMPLES["report"]
        cues = detect_genre(text, detect_language(text)).cues
        assert cues[0].startswith("headings: Introduction, Methods")
        assert "reference list" in cues and "many dates and figures" in cues

    def test_cues_show_the_whole_word(self):
        text = SAMPLES["analysis"]
        cues = detect_genre(text, detect_language(text)).cues
        assert "композиция" in cues and "композиц" not in cues

    def test_plain_text_without_cues_is_general(self):
        text = "The weather was warm. The shop sold bread, milk and apples. The street was long and quiet."
        genre = detect_genre(text, detect_language(text))
        assert genre.key == "other" and genre.confidence == 0.0

    def test_local_labels(self):
        text = SAMPLES["retelling"]
        genre = detect_genre(text, detect_language(text))
        assert genre.local_label == "пересказ / изложение" and genre.label == "retelling of a story"
        assert not genre.expects_sources
        report = SAMPLES["report"]
        assert detect_genre(report, detect_language(report)).expects_sources


@pytest.mark.django_db
class TestGenreAnalyzer:
    def test_reports_genre_without_voting(self, tmp_path):
        path = tmp_path / "essay.txt"
        path.write_text(SAMPLES["argument"])
        out = TextGenreAnalyzer().analyze(str(path), {"mime_type": "text/plain"})
        assert out.verdict == "inconclusive"
        assert out.evidence["genre"] == "argument" and out.evidence["local_label"] == "сочинение-рассуждение"

    def test_genre_never_changes_the_verdict(self):
        sub = SubmissionFactory()
        results = [
            AnalysisResultFactory(
                submission=sub,
                analyzer=AnalyzerConfigFactory(name="text_classifier", weight=2.5),
                verdict=AnalysisResult.Verdict.AUTHENTIC,
                confidence=0.8,
                evidence={"ai_probability": 0.1},
            ),
            AnalysisResultFactory(
                submission=sub,
                analyzer=AnalyzerConfigFactory(name="text_genre", weight=1.0),
                verdict=AnalysisResult.Verdict.INCONCLUSIVE,
                confidence=0.9,
                evidence={"genre": "report"},
            ),
        ]
        assert aggregate(results)[1] == "authentic"
