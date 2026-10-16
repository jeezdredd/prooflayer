#!/usr/bin/env python3
import argparse
import json
import random
import re
import time
from pathlib import Path

from mlx_lm import batch_generate, load
from mlx_lm.sample_utils import make_sampler

MODELS = {
    "qwen3-4b": "mlx-community/Qwen3-4B-Instruct-2507-4bit",
    "llama3.2-3b": "mlx-community/Llama-3.2-3B-Instruct-4bit",
    "mistral-7b": "mlx-community/Mistral-7B-Instruct-v0.3-4bit",
    "gemma3-4b": "mlx-community/gemma-3-4b-it-4bit",
    "qwen2.5-7b": "mlx-community/Qwen2.5-7B-Instruct-4bit",
    "gemma3-12b": "mlx-community/gemma-3-12b-it-4bit",
}

GRADES = ("7th-grade", "9th-grade", "11th-grade", "first-year university")

GENERATE = {
    "en": (
        "Write an essay of about {words} words in response to this assignment: \"{hint}\". "
        "Write it the way a {grade} student would hand it in. No title, no notes, only the essay text."
    ),
    "ru": (
        "Напиши связный текст примерно на {words} слов в том жанре и стиле, которые подсказывает это начало: "
        "«{hint}». Начни своими словами. Без заголовка, без пояснений, только сам текст."
    ),
    "fr": (
        "Rédige un article de presse d'environ {words} mots sur le sujet suggéré par cette phrase : « {hint} ». "
        "Sans titre, sans commentaire, uniquement le texte de l'article."
    ),
}

GENERATE_ACADEMIC = {
    "academic-abstract": {
        "en": (
            "Write the abstract of a research paper on this topic: \"{hint}\". About {words} words, in the style of a "
            "peer-reviewed journal. No title, no headings, no keywords line, only the abstract text."
        ),
        "ru": (
            "Напиши аннотацию научной статьи на тему «{hint}» объёмом примерно {words} слов в стиле российского "
            "рецензируемого журнала. Без заголовка, без ключевых слов, только текст аннотации."
        ),
    },
    "academic-body": {
        "en": (
            "Write a passage of about {words} words from the main body of a research paper on this topic: \"{hint}\", "
            "as it would appear in the middle of the paper (methods, results or discussion). No headings, no lists, "
            "only the prose."
        ),
        "ru": (
            "Напиши фрагмент основной части научной статьи на тему «{hint}» объёмом примерно {words} слов, как он "
            "выглядел бы в середине статьи (методы, результаты или обсуждение). Без заголовков и списков, только текст."
        ),
    },
}
GENERATE_WIKI = {
    "en": (
        "Write a passage of about {words} words for the Wikipedia article \"{hint}\", in the neutral encyclopedic "
        "style of Wikipedia. No title, no headings, no lists, no notes, only the prose."
    ),
    "ru": (
        "Напиши фрагмент статьи Википедии «{hint}» объёмом примерно {words} слов в нейтральном энциклопедическом "
        "стиле. Без заголовков, без списков, без пояснений, только сам текст."
    ),
    "fr": (
        "Rédige un passage d'environ {words} mots de l'article Wikipédia « {hint} », dans le style encyclopédique "
        "neutre de Wikipédia. Sans titre, sans intertitres, sans listes, sans commentaire, uniquement le texte."
    ),
}

HUMANIZE = {
    "en": (
        "Rewrite the text below so it reads like a real person wrote it, not an AI: vary sentence length, use plain "
        "everyday words, drop stock phrases, let the flow be a little uneven. Keep the meaning and the language. "
        "Output only the rewritten text.\n\n{text}"
    ),
    "ru": (
        "Перепиши текст ниже так, чтобы он звучал как написанный живым человеком, а не ИИ: меняй длину предложений, "
        "используй простые повседневные слова, убери шаблонные обороты, пусть изложение будет чуть неровным. "
        "Сохрани смысл и язык. Выведи только переписанный текст.\n\n{text}"
    ),
    "fr": (
        "Réécris le texte ci-dessous pour qu'il semble écrit par une vraie personne et non par une IA : varie la "
        "longueur des phrases, emploie des mots simples du quotidien, supprime les formules toutes faites, laisse le "
        "fil un peu irrégulier. Garde le sens et la langue. Donne uniquement le texte réécrit.\n\n{text}"
    ),
}

ATTACKS = {
    "paraphrase": {
        "en": (
            "Paraphrase the text below sentence by sentence. Replace words with synonyms and restructure every "
            "sentence, but keep the same number of sentences, the same meaning and the same language. Output only the "
            "paraphrased text.\n\n{text}"
        ),
        "ru": (
            "Перефразируй текст ниже предложение за предложением. Замени слова синонимами и перестрой каждое "
            "предложение, но сохрани число предложений, смысл и язык. Выведи только перефразированный текст.\n\n{text}"
        ),
        "fr": (
            "Paraphrase le texte ci-dessous phrase par phrase. Remplace les mots par des synonymes et restructure chaque "
            "phrase, mais garde le même nombre de phrases, le même sens et la même langue. Donne uniquement le texte "
            "paraphrasé.\n\n{text}"
        ),
    },
    "bypass": {
        "en": (
            "Rewrite the text below so that AI detectors such as GPTZero and Turnitin classify it as human-written. "
            "Raise perplexity and burstiness: mix very short and very long sentences, pick less predictable but "
            "correct words, use contractions, an idiom or two, a rhetorical question and an occasional informal aside. "
            "Keep the meaning and the language. Output only the rewritten text.\n\n{text}"
        ),
        "ru": (
            "Перепиши текст ниже так, чтобы детекторы ИИ вроде GPTZero и Антиплагиата признали его написанным "
            "человеком. Повысь perplexity и burstiness: чередуй очень короткие и очень длинные предложения, выбирай "
            "менее предсказуемые, но верные слова, добавь разговорный оборот, риторический вопрос и неформальное "
            "отступление. Сохрани смысл и язык. Выведи только переписанный текст.\n\n{text}"
        ),
        "fr": (
            "Réécris le texte ci-dessous pour que les détecteurs d'IA comme GPTZero et Compilatio le classent comme "
            "écrit par un humain. Augmente la perplexité et la variabilité : alterne phrases très courtes et très "
            "longues, choisis des mots moins prévisibles mais justes, ajoute une expression familière, une question "
            "rhétorique et une remarque informelle. Garde le sens et la langue. Donne uniquement le texte réécrit."
            "\n\n{text}"
        ),
    },
    "student": {
        "en": (
            "Rewrite the text below the way a {grade} student would really write it for homework: simpler words, "
            "some repetition, a personal remark, one or two small grammar slips. Keep the meaning and the language. "
            "Output only the rewritten text.\n\n{text}"
        ),
        "ru": (
            "Перепиши текст ниже так, как его на самом деле написал бы ученик ({grade}) в домашней работе: слова "
            "попроще, немного повторов, личное замечание, одна-две мелкие ошибки. Сохрани смысл и язык. Выведи только "
            "переписанный текст.\n\n{text}"
        ),
        "fr": (
            "Réécris le texte ci-dessous comme un élève ({grade}) l'écrirait vraiment pour un devoir : mots plus "
            "simples, quelques répétitions, une remarque personnelle, une ou deux petites fautes. Garde le sens et la "
            "langue. Donne uniquement le texte réécrit.\n\n{text}"
        ),
    },
    "recursive": {
        "en": (
            "Make the text below sound even more natural and human, as if typed quickly by a real person. Keep the "
            "meaning and the language. Output only the text.\n\n{text}"
        ),
        "ru": (
            "Сделай текст ниже ещё естественнее и человечнее, как будто его быстро набрал живой человек. Сохрани смысл "
            "и язык. Выведи только текст.\n\n{text}"
        ),
        "fr": (
            "Rends le texte ci-dessous encore plus naturel et humain, comme tapé rapidement par une vraie personne. "
            "Garde le sens et la langue. Donne uniquement le texte.\n\n{text}"
        ),
    },
}

TRANSLATE = {
    "en": "Translate the text below into English so it reads naturally. Output only the translation.\n\n{text}",
    "ru": "Переведи текст ниже на русский язык так, чтобы он читался естественно. Выведи только перевод.\n\n{text}",
    "fr": "Traduis le texte ci-dessous en français pour qu'il se lise naturellement. Donne uniquement la traduction.\n\n{text}",
}

TRANSLATE_TO = {"en": ("ru", "fr"), "ru": ("en",), "fr": ("en",)}

TOKENS_PER_WORD = {"en": 1.6, "ru": 2.6, "fr": 2.0}
PREAMBLE = re.compile(r"^(here is|here's|voici|вот )", re.IGNORECASE)


def clean(text: str) -> str:
    lines = [ln.strip() for ln in text.replace("**", "").split("\n")]
    lines = [ln for ln in lines if ln and not ln.startswith("#") and ln != "---"]
    if lines and (PREAMBLE.match(lines[0]) or (lines[0].endswith(":") and len(lines[0].split()) < 14)):
        lines = lines[1:]
    if lines and len(lines[0].split()) <= 12 and not lines[0].endswith((".", "!", "?", "»", '"')):
        lines = lines[1:]
    return "\n\n".join(lines).strip()


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in open(path) if line.strip()]


def jobs_for(args, rng: random.Random) -> list[dict]:
    done = {r["id"] for r in read_jsonl(Path(args.out))}
    jobs = []
    if args.mode == "generate":
        for seed in read_jsonl(Path(args.seeds)):
            if args.splits and seed["split"] not in args.splits:
                continue
            if args.langs and seed["lang"] not in args.langs:
                continue
            if args.share < 1 and rng.random() >= args.share:
                continue
            grade = rng.choice(GRADES)
            rid = f'{seed["id"]}-{args.model}'
            if rid in done:
                continue
            genre = seed.get("genre", "")
            templates = GENERATE_ACADEMIC[genre] if genre in GENERATE_ACADEMIC else GENERATE_WIKI if genre == "wiki" else GENERATE
            prompt = templates[seed["lang"]].format(words=seed["words"], hint=seed["hint"], grade=grade)
            budget = int(seed["words"] * TOKENS_PER_WORD[seed["lang"]] * 1.3) + 64
            jobs.append(
                {"id": rid, "seed_id": seed["id"], "lang": seed["lang"], "split": seed["split"], "prompt": prompt, "budget": budget, "genre": genre}
            )
    elif args.mode == "attack":
        for row in read_jsonl(Path(args.source)):
            recursive = args.attacks == ["recursive"]
            base_ok = row.get("mode") in ("humanize", "attack:bypass", "attack:student") if recursive else row.get("mode") == "generate"
            if not base_ok or row["generator"] == args.model:
                continue
            if args.splits and row["split"] not in args.splits:
                continue
            if args.share < 1 and rng.random() >= args.share:
                continue
            attack = rng.choice(args.attacks)
            lang = rng.choice(TRANSLATE_TO[row["lang"]]) if attack == "translate" else row["lang"]
            grade = rng.choice(GRADES)
            rid = f'{row["id"]}-{attack}-{args.model}'
            if rid in done:
                continue
            template = TRANSLATE[lang] if attack == "translate" else ATTACKS[attack][lang]
            words = len(row["text"].split())
            budget = int(words * max(TOKENS_PER_WORD[lang], TOKENS_PER_WORD[row["lang"]]) * 1.4) + 64
            jobs.append(
                {
                    "id": rid,
                    "seed_id": row["seed_id"],
                    "lang": lang,
                    "split": row["split"],
                    "prompt": template.format(text=row["text"], grade=grade),
                    "budget": budget,
                    "base_generator": row.get("base_generator") or row["generator"],
                    "genre": row.get("genre", ""),
                    "mode": f"attack:{attack}",
                }
            )
    else:
        for row in read_jsonl(Path(args.source)):
            if row.get("mode") != "generate" or row["generator"] == args.model:
                continue
            if args.splits and row["split"] not in args.splits:
                continue
            if args.share < 1 and rng.random() >= args.share:
                continue
            rid = f'{row["id"]}-hum-{args.model}'
            if rid in done:
                continue
            budget = int(len(row["text"].split()) * TOKENS_PER_WORD[row["lang"]] * 1.3) + 64
            jobs.append(
                {
                    "id": rid,
                    "seed_id": row["seed_id"],
                    "lang": row["lang"],
                    "split": row["split"],
                    "prompt": HUMANIZE[row["lang"]].format(text=row["text"]),
                    "budget": budget,
                    "base_generator": row["generator"],
                    "genre": row.get("genre", ""),
                }
            )
    return jobs[: args.limit] if args.limit else jobs


def main():
    parser = argparse.ArgumentParser(description="Generate or humanize AI texts from topic seeds with a local MLX model")
    parser.add_argument("--model", required=True, choices=sorted(MODELS))
    parser.add_argument("--mode", choices=("generate", "humanize", "attack"), default="generate")
    parser.add_argument("--attacks", nargs="*", default=["paraphrase", "bypass", "student", "translate"], choices=[*ATTACKS, "translate"])
    parser.add_argument("--seeds", default="dataset/text_gen/seeds.jsonl")
    parser.add_argument("--source", default="dataset/text_gen/ai.jsonl", help="generated texts to humanize")
    parser.add_argument("--out", default="dataset/text_gen/ai.jsonl")
    parser.add_argument("--splits", nargs="*", default=[])
    parser.add_argument("--langs", nargs="*", default=[])
    parser.add_argument("--share", type=float, default=1.0, help="random share of seeds or source rows to use")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch", type=int, default=12)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    rng = random.Random(f"{args.seed}:{args.model}:{args.mode}")
    jobs = jobs_for(args, rng)
    print(f"{len(jobs)} jobs for {args.model} ({args.mode})", flush=True)
    if not jobs:
        return
    model, tokenizer = load(MODELS[args.model])
    jobs.sort(key=lambda j: j["budget"])
    started, written = time.time(), 0
    with open(args.out, "a") as fh:
        for start in range(0, len(jobs), args.batch):
            chunk = jobs[start : start + args.batch]
            prompts = [
                tokenizer.apply_chat_template([{"role": "user", "content": j["prompt"]}], add_generation_prompt=True)
                for j in chunk
            ]
            temp = rng.choice((0.7, 0.85, 1.0))
            result = batch_generate(
                model,
                tokenizer,
                prompts,
                max_tokens=[j["budget"] for j in chunk],
                sampler=make_sampler(temp=temp, top_p=0.95),
            )
            for job, text in zip(chunk, result.texts):
                body = clean(text)
                if len(body.split()) < 60:
                    continue
                row = {
                    "id": job["id"],
                    "seed_id": job["seed_id"],
                    "lang": job["lang"],
                    "split": job["split"],
                    "generator": args.model,
                    "mode": job.get("mode", args.mode),
                    "temperature": temp,
                    "text": body,
                }
                if "base_generator" in job:
                    row["base_generator"] = job["base_generator"]
                if job.get("genre"):
                    row["genre"] = job["genre"]
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                written += 1
            fh.flush()
            rate = (start + len(chunk)) / (time.time() - started)
            print(f"{start + len(chunk)}/{len(jobs)} written={written} {rate:.2f}/s", flush=True)


if __name__ == "__main__":
    main()
