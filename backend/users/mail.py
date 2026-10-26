from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from common.names import display_name

from .emails import deliver
from .models import User

LANGS = ("en", "ru")
UNSUBSCRIBE_SALT = "product-updates-unsubscribe"

ACCENTS = {
    "amber": ("#f5b042", "rgba(245,176,66,0.35)"),
    "violet": ("#a78bfa", "rgba(167,139,250,0.35)"),
    "sage": ("#4ade80", "rgba(74,222,128,0.35)"),
    "blood": ("#ff5773", "rgba(255,87,115,0.35)"),
    "cyan": ("#22d3ee", "rgba(34,211,238,0.35)"),
}

COMMON = {
    "en": {
        "tagline": "Automated AI systems under human supervision",
        "privacy": "Privacy",
        "terms": "Terms",
        "support": "Support",
        "link_hint": "Button not working? Paste this link into your browser:",
        "unsubscribe": "Unsubscribe from product updates",
        "signoff": "The ProofLayer team",
    },
    "ru": {
        "tagline": "Автоматические ИИ-системы под надзором человека",
        "privacy": "Конфиденциальность",
        "terms": "Условия",
        "support": "Поддержка",
        "link_hint": "Кнопка не работает? Вставьте ссылку в браузер:",
        "unsubscribe": "Отписаться от новостей",
        "signoff": "Команда ProofLayer",
    },
}

COPY = {
    "verify": {
        "en": {
            "subject": "Confirm your email for ProofLayer",
            "preheader": "One click and your account is ready. The link works for 48 hours.",
            "badge": "Account",
            "heading": "Confirm your",
            "accent_word": "email",
            "paragraphs": [
                "Hi {name}, thanks for joining ProofLayer.",
                "Confirm this address so we can keep your account safe and send you results, receipts and security notices.",
            ],
            "cta": "Confirm email",
            "footnote": "The link works for 48 hours. If you did not create an account, ignore this email and nothing will happen.",
            "reason": "You get this email because this address was used to sign up for ProofLayer.",
        },
        "ru": {
            "subject": "Подтвердите почту для ProofLayer",
            "preheader": "Один клик, и аккаунт готов. Ссылка действует 48 часов.",
            "badge": "Аккаунт",
            "heading": "Подтвердите",
            "accent_word": "почту",
            "paragraphs": [
                "Здравствуйте, {name}! Спасибо, что присоединились к ProofLayer.",
                "Подтвердите адрес, чтобы мы могли защитить ваш аккаунт и присылать результаты, чеки и уведомления о безопасности.",
            ],
            "cta": "Подтвердить почту",
            "footnote": "Ссылка действует 48 часов. Если вы не создавали аккаунт, просто проигнорируйте это письмо.",
            "reason": "Вы получили это письмо, потому что этот адрес указали при регистрации в ProofLayer.",
        },
    },
    "password_reset": {
        "en": {
            "subject": "Reset your ProofLayer password",
            "preheader": "Choose a new password. The link works for one hour.",
            "badge": "Security",
            "heading": "Set a new",
            "accent_word": "password",
            "paragraphs": [
                "We got a request to reset the password for {email}.",
                "Choose a new one with the button below. After that, sign in again on your other devices.",
            ],
            "cta": "Choose a new password",
            "footnote": "The link works for one hour and only once. If you did not ask for this, ignore the email: your password stays the same.",
            "reason": "You get this email because a password reset was requested for your ProofLayer account.",
        },
        "ru": {
            "subject": "Сброс пароля ProofLayer",
            "preheader": "Задайте новый пароль. Ссылка действует один час.",
            "badge": "Безопасность",
            "heading": "Задайте новый",
            "accent_word": "пароль",
            "paragraphs": [
                "Мы получили запрос на сброс пароля для {email}.",
                "Задайте новый пароль кнопкой ниже. На других устройствах после этого нужно будет войти заново.",
            ],
            "cta": "Задать новый пароль",
            "footnote": "Ссылка действует один час и срабатывает один раз. Если вы не запрашивали сброс, проигнорируйте письмо: пароль останется прежним.",
            "reason": "Вы получили это письмо, потому что для вашего аккаунта ProofLayer запросили сброс пароля.",
        },
    },
    "email_change_confirm": {
        "en": {
            "subject": "Confirm your new email for ProofLayer",
            "preheader": "Open the link to finish the change. It works for 24 hours.",
            "badge": "Account",
            "heading": "Confirm your new",
            "accent_word": "email",
            "paragraphs": [
                "Hi {name}, you asked to use this address for your ProofLayer account.",
                "The address changes only after you press the button below. Until then, sign in with your old address.",
            ],
            "cta": "Confirm new email",
            "footnote": "The link works for 24 hours and only once. If you did not ask for this, ignore this email and nothing will change.",
            "reason": "You get this email because this address was entered as the new email of a ProofLayer account.",
        },
        "ru": {
            "subject": "Подтвердите новую почту для ProofLayer",
            "preheader": "Откройте ссылку, чтобы закончить смену почты. Ссылка действует 24 часа.",
            "badge": "Аккаунт",
            "heading": "Подтвердите новую",
            "accent_word": "почту",
            "paragraphs": [
                "Здравствуйте, {name}! Вы попросили привязать этот адрес к аккаунту ProofLayer.",
                "Адрес сменится, только когда вы нажмёте кнопку ниже. До этого входите со старым адресом.",
            ],
            "cta": "Подтвердить новую почту",
            "footnote": "Ссылка действует 24 часа и срабатывает один раз. Если вы ничего не меняли, просто проигнорируйте письмо: ничего не изменится.",
            "reason": "Вы получили это письмо, потому что этот адрес указали как новую почту аккаунта ProofLayer.",
        },
    },
    "email_change_notice": {
        "en": {
            "subject": "Email change requested for your ProofLayer account",
            "preheader": "New address: {masked}. Nothing changes until it is confirmed.",
            "badge": "Security",
            "heading": "Email change",
            "accent_word": "requested",
            "paragraphs": [
                "Someone asked to change the email of your ProofLayer account to {masked}.",
                "Nothing changes until the new address is confirmed. If it was you, there is nothing else to do.",
                "If it was not you, reset your password with the button below. That also stops the change.",
            ],
            "labels": {"new": "New address", "account": "Account"},
            "cta": "Reset password",
            "footnote": "Questions? Write to support@prooflayer.cloud.",
            "reason": "You get this email because this is the current address of a ProofLayer account.",
        },
        "ru": {
            "subject": "Запрос на смену почты в ProofLayer",
            "preheader": "Новый адрес: {masked}. Пока его не подтвердят, ничего не изменится.",
            "badge": "Безопасность",
            "heading": "Запрошена смена",
            "accent_word": "почты",
            "paragraphs": [
                "Для вашего аккаунта ProofLayer запросили смену почты на {masked}.",
                "Пока новый адрес не подтвердят, ничего не изменится. Если это были вы, больше ничего делать не нужно.",
                "Если это были не вы, сбросьте пароль кнопкой ниже. Смена почты при этом отменится.",
            ],
            "labels": {"new": "Новый адрес", "account": "Аккаунт"},
            "cta": "Сбросить пароль",
            "footnote": "Вопросы? Пишите на support@prooflayer.cloud.",
            "reason": "Вы получили это письмо, потому что это текущий адрес аккаунта ProofLayer.",
        },
    },
    "email_changed": {
        "en": {
            "subject": "Your ProofLayer email was changed",
            "preheader": "Your account now uses {masked}.",
            "badge": "Security",
            "heading": "Your email was",
            "accent_word": "changed",
            "paragraphs": [
                "Your ProofLayer account now uses {masked}. Sign in with the new address from now on.",
                "Account emails no longer come to this address.",
                "If you did not do this, write to support@prooflayer.cloud right away and we will help you get the account back.",
            ],
            "labels": {"new": "New address", "account": "Account"},
            "cta": "Write to support",
            "footnote": "We write to your old address so you know about every change to your account.",
            "reason": "You get this email because this was the address of a ProofLayer account until now.",
        },
        "ru": {
            "subject": "Почта в ProofLayer изменена",
            "preheader": "Теперь аккаунт привязан к {masked}.",
            "badge": "Безопасность",
            "heading": "Почта",
            "accent_word": "изменена",
            "paragraphs": [
                "Ваш аккаунт ProofLayer теперь привязан к адресу {masked}. Входите с новым адресом.",
                "Письма об аккаунте на этот адрес больше не придут.",
                "Если это сделали не вы, сразу напишите на support@prooflayer.cloud, и мы поможем вернуть аккаунт.",
            ],
            "labels": {"new": "Новый адрес", "account": "Аккаунт"},
            "cta": "Написать в поддержку",
            "footnote": "Мы пишем на старый адрес, чтобы вы знали о каждом изменении в аккаунте.",
            "reason": "Вы получили это письмо, потому что до сих пор это был адрес аккаунта ProofLayer.",
        },
    },
    "objection": {
        "en": {
            "subject": "Objection to a verdict: {title}",
            "preheader": "{student} asked for a human review. Please answer by {due}.",
            "badge": "Objection",
            "heading": "A student asked for",
            "accent_word": "a review",
            "paragraphs": [
                "{student} disagrees with the automated verdict on “{title}”.",
                "ProofLayer verdicts are probabilistic. Please look at the work yourself and answer the objection before the deadline.",
            ],
            "quote_label": "Their reason",
            "labels": {"student": "Student", "class": "Class", "due": "Answer by"},
            "cta": "Open the result",
            "footnote": "A person, not the model, makes the final decision. Your answer is shown to the student.",
            "reason": "You get this email because the work was handed in to a class you teach on ProofLayer.",
        },
        "ru": {
            "subject": "Возражение на вердикт: {title}",
            "preheader": "{student} просит пересмотра человеком. Ответьте до {due}.",
            "badge": "Возражение",
            "heading": "Ученик просит",
            "accent_word": "пересмотра",
            "paragraphs": [
                "{student} просит пересмотреть вердикт по работе «{title}».",
                "Вердикты ProofLayer вероятностные. Посмотрите работу сами и ответьте на возражение до срока.",
            ],
            "quote_label": "Причина",
            "labels": {"student": "Ученик", "class": "Класс", "due": "Ответить до"},
            "cta": "Открыть результат",
            "footnote": "Окончательное решение принимает человек, а не модель. Ваш ответ увидит ученик.",
            "reason": "Вы получили это письмо, потому что работа сдана в класс, который вы ведёте в ProofLayer.",
        },
    },
    "objection_answer": {
        "en": {
            "subject": "Your objection has an answer: {title}",
            "preheader": "{outcome}",
            "badge": "Objection",
            "heading": "Your objection has",
            "accent_word": "an answer",
            "paragraphs": [
                "Your objection to the verdict on “{title}” has an answer.",
                "{outcome}",
            ],
            "outcomes": {
                "changed": "The verdict was changed: the work counts as your own.",
                "upheld": "The verdict stays as it was. Read the answer below. If you still disagree, talk to your teacher.",
            },
            "quote_label": "The answer",
            "labels": {"teacher": "Teacher", "class": "Class", "answered": "Answered"},
            "cta": "Open the work",
            "footnote": "A person, not the model, made this decision.",
            "reason": "You get this email because you objected to a verdict on ProofLayer.",
        },
        "ru": {
            "subject": "Ответ на возражение: {title}",
            "preheader": "{outcome}",
            "badge": "Возражение",
            "heading": "На возражение",
            "accent_word": "ответили",
            "paragraphs": [
                "Пришёл ответ на ваше возражение по работе «{title}».",
                "{outcome}",
            ],
            "outcomes": {
                "changed": "Вердикт изменён: работа признана самостоятельной.",
                "upheld": "Вердикт оставлен без изменений. Прочитайте ответ ниже. Если всё ещё не согласны, поговорите с учителем.",
            },
            "quote_label": "Ответ",
            "labels": {"teacher": "Учитель", "class": "Класс", "answered": "Ответ дан"},
            "cta": "Открыть работу",
            "footnote": "Решение принял человек, а не модель.",
            "reason": "Вы получили это письмо, потому что оспорили вердикт в ProofLayer.",
        },
    },
    "update": {
        "en": {
            "badge": "What's new",
            "reason": "You get product updates because they are on in your ProofLayer account. You can turn them off there at any time.",
        },
        "ru": {
            "badge": "Что нового",
            "reason": "Вы получаете новости, потому что они включены в вашем аккаунте ProofLayer. Выключить их можно там в любой момент.",
        },
    },
}


def lang_of(user) -> str:
    lang = getattr(user, "language", "") or "en"
    return lang if lang in LANGS else "en"


def unsubscribe_token(user) -> str:
    return signing.dumps({"u": user.pk}, salt=UNSUBSCRIBE_SALT, compress=True)


def user_from_unsubscribe_token(token: str):
    try:
        data = signing.loads(token or "", salt=UNSUBSCRIBE_SALT)
    except signing.BadSignature:
        return None
    return User.objects.filter(pk=data.get("u")).first()


def split_body(body: str) -> list[dict]:
    blocks = []
    for chunk in [c.strip() for c in (body or "").replace("\r\n", "\n").split("\n\n") if c.strip()]:
        lines = [line.strip() for line in chunk.split("\n") if line.strip()]
        if all(line.startswith("- ") for line in lines):
            blocks.append({"list": [line[2:].strip() for line in lines]})
        else:
            blocks.append({"text": " ".join(lines)})
    return blocks


def _fill(value, values: dict):
    if isinstance(value, str):
        return value.format(**values)
    if isinstance(value, list):
        return [_fill(v, values) for v in value]
    if isinstance(value, dict):
        return {k: _fill(v, values) for k, v in value.items()}
    return value


def build(kind: str, lang: str, values: dict | None = None) -> dict:
    lang = lang if lang in LANGS else "en"
    copy = _fill(COPY[kind][lang], values or {})
    return {**COMMON[lang], **copy, "lang": lang}


def render(context: dict) -> tuple[str, str]:
    accent, accent_border = ACCENTS.get(context.get("tone", "violet"), ACCENTS["violet"])
    blocks = context.get("blocks")
    if blocks is None:
        blocks = [{"text": p} for p in context.get("paragraphs", [])]
    now = timezone.now()
    full = {
        "case_ref": f"CASE/{now:%Y-%m%d} · {now:%H:%M} UTC",
        "site_url": settings.FRONTEND_URL,
        "asset_base": settings.FRONTEND_URL,
        "accent": accent,
        "accent_border": accent_border,
        **context,
        "blocks": blocks,
    }
    return render_to_string("email/message.txt", full), render_to_string("email/message.html", full)


def send(*, kind: str, to: list[str], context: dict, user=None, headers: dict | None = None) -> str:
    text_body, html_body = render(context)
    msg = EmailMultiAlternatives(
        subject=context["subject"],
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
        headers=headers or {},
    )
    msg.attach_alternative(html_body, "text/html")
    return deliver(msg, kind=kind, user=user)


def unsubscribe_page_url(user) -> str:
    return f"{settings.FRONTEND_URL}/unsubscribe?token={unsubscribe_token(user)}"


def unsubscribe_headers(user) -> dict:
    one_click = f"{settings.PUBLIC_API_URL}/auth/unsubscribe/?token={unsubscribe_token(user)}"
    return {
        "List-Unsubscribe": f"<{one_click}>, <mailto:support@prooflayer.cloud?subject=unsubscribe>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }


def verification_context(user, link: str) -> dict:
    context = build("verify", lang_of(user), {"name": user.username or user.email})
    context.update(tone="violet", cta_url=link, show_link=True)
    return context


def password_reset_context(user, link: str) -> dict:
    context = build("password_reset", lang_of(user), {"email": user.email})
    context.update(tone="amber", cta_url=link, show_link=True)
    return context


SUPPORT_EMAIL = "support@prooflayer.cloud"


def mask_email(email: str) -> str:
    local, _, domain = (email or "").partition("@")
    if not domain:
        return f"{local[:1]}***"
    return f"{local[:1]}***@{domain}"


def email_change_confirm_context(user, link: str) -> dict:
    context = build("email_change_confirm", lang_of(user), {"name": display_name(user) or user.email})
    context.update(tone="violet", cta_url=link, show_link=True)
    return context


def email_change_notice_context(user, old_email: str, new_email: str) -> dict:
    masked = mask_email(new_email)
    context = build("email_change_notice", lang_of(user), {"masked": masked})
    labels = context.pop("labels")
    context.update(
        tone="amber",
        details=[(labels["account"], old_email), (labels["new"], masked)],
        cta_url=f"{settings.FRONTEND_URL}/forgot-password",
    )
    return context


def email_changed_context(user, old_email: str) -> dict:
    masked = mask_email(user.email)
    context = build("email_changed", lang_of(user), {"masked": masked})
    labels = context.pop("labels")
    context.update(
        tone="amber",
        details=[(labels["account"], old_email), (labels["new"], masked)],
        cta_url=f"mailto:{SUPPORT_EMAIL}",
    )
    return context


def objection_context(*, lang: str, student: str, title: str, classroom: str, reason: str, due: str, link: str) -> dict:
    context = build("objection", lang, {"student": student, "title": title, "due": due})
    labels = context.pop("labels")
    details = [(labels["student"], student)]
    if classroom:
        details.append((labels["class"], classroom))
    details.append((labels["due"], due))
    context.update(tone="amber", quote=reason, details=details, cta_url=link)
    return context


def objection_answer_context(
    *, lang: str, teacher: str, title: str, classroom: str, changed: bool, response: str, answered: str, link: str,
) -> dict:
    lang = lang if lang in LANGS else "en"
    outcome = COPY["objection_answer"][lang]["outcomes"]["changed" if changed else "upheld"]
    context = build("objection_answer", lang, {"title": title, "outcome": outcome})
    context.pop("outcomes")
    labels = context.pop("labels")
    details = []
    if teacher:
        details.append((labels["teacher"], teacher))
    if classroom:
        details.append((labels["class"], classroom))
    details.append((labels["answered"], answered))
    context.update(tone="sage" if changed else "amber", quote=response, details=details, cta_url=link)
    return context


def update_context(update, user) -> dict:
    lang = lang_of(user)
    local = update.localized(lang)
    blocks = split_body(local["body"])
    first_text = next((b["text"] for b in blocks if "text" in b), "")
    context = build("update", lang)
    context.update(
        tone="violet",
        subject=local["title"],
        preheader=local["summary"] or first_text[:140],
        heading=local["title"],
        blocks=blocks,
        cta=local["cta_label"],
        cta_url=update.cta_url if local["cta_label"] else "",
        unsubscribe_url=unsubscribe_page_url(user),
    )
    return context
