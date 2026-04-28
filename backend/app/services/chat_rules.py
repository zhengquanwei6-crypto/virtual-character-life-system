from __future__ import annotations


IMAGE_TRIGGER_WORDS = [
    "\u753b",
    "\u770b\u770b",
    "\u751f\u6210",
    "\u7167\u7247",
    "\u6837\u5b50",
    "draw",
    "generate",
    "photo",
    "picture",
    "image",
    "show me",
]


def should_generate_image(content: str) -> bool:
    normalized = content.lower()
    return any(word in normalized for word in IMAGE_TRIGGER_WORDS)


def mock_llm_decision(content: str) -> dict:
    wants_image = should_generate_image(content)
    return {
        "replyText": (
            "\u6211\u5df2\u7ecf\u60f3\u8c61\u51fa\u8fd9\u4e2a\u753b\u9762\u4e86\uff0c"
            "\u6b63\u5728\u4e3a\u4f60\u751f\u6210\u56fe\u7247\u3002"
            if wants_image
            else "I heard you. Let's keep talking about it."
        ),
        "shouldGenerateImage": wants_image,
        "imagePrompt": content if wants_image else None,
    }
