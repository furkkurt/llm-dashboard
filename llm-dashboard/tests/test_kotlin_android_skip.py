from backend.analyzer import _kotlin_snippet_needs_android_sdk


def test_detects_android_import() -> None:
    code = "import android.content.Context\nfun x() {}\n"
    assert _kotlin_snippet_needs_android_sdk(code) is True


def test_detects_androidx_import() -> None:
    code = "import androidx.compose.runtime.Composable\n"
    assert _kotlin_snippet_needs_android_sdk(code) is True


def test_plain_kotlin_not_flagged() -> None:
    code = "import kotlin.collections.List\nfun main() {}\n"
    assert _kotlin_snippet_needs_android_sdk(code) is False
