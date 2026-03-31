from backend.models import TargetLanguage


def build_system_instruction(*, target_language: TargetLanguage) -> str:
    lang_rules = (
        "You output Kotlin code suitable for Android (JVM). Use idiomatic Kotlin. "
        "The primary deliverable is source code; use a single fenced code block when helpful."
        if target_language == "Kotlin"
        else "You output Dart code suitable for Flutter. Use idiomatic Dart and Flutter widgets. "
        "The primary deliverable is source code; use a single fenced code block when helpful."
    )
    return f"{lang_rules}\n\nRespond with working code that addresses the user's task."
