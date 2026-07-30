"""Unit tests for page cleanup: artifacts, running headers, intro filtering."""

from app.pipeline import cleanup


class TestStripPageArtifacts:
    def test_removes_top_page_number(self) -> None:
        text = "12\n\nBu bir paragraftır ve devam eder."
        assert cleanup.strip_page_artifacts(text) == "Bu bir paragraftır ve devam eder."

    def test_removes_bottom_page_number(self) -> None:
        text = "Bu bir paragraftır ve devam eder.\n\n- 47 -"
        assert cleanup.strip_page_artifacts(text) == "Bu bir paragraftır ve devam eder."

    def test_removes_decorated_and_labeled_numbers(self) -> None:
        for artifact in ["— 12 —", "[12]", "(12)", "Sayfa 12", "12 / 348", "* 7 *"]:
            text = f"{artifact}\nGerçek metin burada."
            assert cleanup.strip_page_artifacts(text) == "Gerçek metin burada.", artifact

    def test_removes_roman_numerals(self) -> None:
        text = "vii\nÖnsöz metni burada başlar."
        assert cleanup.strip_page_artifacts(text) == "Önsöz metni burada başlar."

    def test_keeps_short_turkish_word_that_looks_roman(self) -> None:
        # "dil" consists only of roman-numeral letters but is not a numeral.
        text = "dil\nBir sonraki satır."
        assert "dil" in cleanup.strip_page_artifacts(text)

    def test_keeps_number_inside_body(self) -> None:
        lines = ["Başlangıç paragrafı."] * 4 + ["1923", "Cumhuriyet ilan edildi."] + ["Kapanış."] * 4
        text = "\n".join(lines)
        assert "1923" in cleanup.strip_page_artifacts(text)

    def test_plain_text_untouched(self) -> None:
        text = "Sadece düz metin.\nİkinci satır."
        assert cleanup.strip_page_artifacts(text) == text


class TestRunningHeaders:
    def test_detects_and_strips_repeated_header(self) -> None:
        pages = [
            f"SEFİLLER\nSayfa içeriği {i} burada devam ediyor.\nSon satır {i}."
            for i in range(10)
        ]
        headers = cleanup.detect_running_headers(pages)
        assert headers  # "sefiller" detected
        cleaned = cleanup.strip_running_headers(pages[0], headers)
        assert "SEFİLLER" not in cleaned
        assert "Sayfa içeriği 0" in cleaned

    def test_no_false_positive_on_unique_first_lines(self) -> None:
        pages = [f"Benzersiz açılış cümlesi {i}.\nDevam metni {i} farklı biter." for i in range(10)]
        assert cleanup.detect_running_headers(pages) == set()

    def test_few_pages_returns_empty(self) -> None:
        pages = ["BAŞLIK\ncontent"] * 3
        assert cleanup.detect_running_headers(pages) == set()


class TestCleanPages:
    def test_full_pass_strips_numbers_and_headers(self) -> None:
        pages = [
            f"{i + 1}\nROMAN ADI\nGerçek içerik satırı {i} uzun bir cümledir.\n{i + 1}"
            for i in range(10)
        ]
        cleaned = cleanup.clean_pages(pages)
        assert all("ROMAN ADI" not in page for page in cleaned)
        assert "Gerçek içerik satırı 3" in cleaned[3]
        assert not cleaned[3].startswith("4")


class TestIntroFiltering:
    def test_copyright_page_detected(self) -> None:
        text = "ISBN 975-123-456-7\nCopyright 2003\nHer hakkı saklıdır. " + "x" * 50
        assert cleanup.is_intro_page(text)

    def test_content_page_kept(self) -> None:
        text = (
            "Uzun bir kış gecesiydi. Kar, bütün şehri örtmüştü ve sokaklarda "
            "kimsecikler yoktu. Ahmet pencereden dışarıyı seyrediyordu."
        )
        assert not cleanup.is_intro_page(text)

    def test_filter_pages_returns_removed_indices(self) -> None:
        intro = "ISBN 975-1-2\ncopyright telif " + "a" * 60
        content = "Normal bir sayfa metni burada uzun uzun devam eder. " * 3
        filtered, removed = cleanup.filter_pages([intro, content])
        assert removed == [1]
        assert filtered == [content]
