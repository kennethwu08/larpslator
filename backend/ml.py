"""Local, free ML: everything except the actual translation runs on the laptop.

- field:   sentence embedding (all-MiniLM-L6-v2, ONNX) -> LogisticRegression, limited to the checked
           contexts and smoothed over the conversation
- tone:    punctuation rules, then nearest tone prototype by embedding
- terms:   glossary lookup for the detected field
- choice:  which translation to use per term, learned from thumbs up/down (Beta posterior per option)
- context: only the context-pack lines relevant to this sentence go to the LLM
- larp:    drops filler words and upgrades weak phrases before translation
"""
import json
import logging
import re
import threading
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding
from sklearn.linear_model import LogisticRegression

HERE = Path(__file__).parent
DATA = HERE.parent / "data"            # owned by Role D; read-only here
STATE_FILE = HERE / "state" / "term_stats.json"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_DIR = HERE / ".models"           # downloaded once, then works offline

# The contexts shown as checkboxes. Fields are subjects with jargon; LARP is a speaking style.
FIELDS = {"pickleball": "Pickleball", "tennis": "Tennis", "cs": "Computer science", "math": "Math"}
STYLES = {"larp": "LARP mode"}
GENERAL = "general"                    # fallback class for everyday sentences; not a checkbox
DOMAINS = [*FIELDS, GENERAL]

SMOOTHING = 0.5                        # weight of the previous sentences in the field estimate
TONE_MIN_SIM = 0.35                    # below this, tone stays neutral
CONTEXT_FULL_CHARS = 400               # context packs shorter than this are sent whole
CONTEXT_MAX_LINES = 5

log = logging.getLogger("larpslator.ml")


def _norm_options(value, target: str) -> list[str]:
    """Glossary values are either a list (one target language) or {language: list}."""
    if isinstance(value, list):
        return value
    return value.get(target, []) if isinstance(value, dict) else []


def _read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        log.warning("skipping %s: %s", path, e)
        return None


class LocalML:
    def __init__(self):
        seeds = json.loads((HERE / "seeds.json").read_text())
        self.source = {}                                  # context -> "data" or "built-in"
        self.glossary, sentences = self._load(seeds)
        self.larp = self._load_larp(seeds)

        log.info("loading %s (first run downloads ~90 MB)", EMBED_MODEL)
        # ONNX instead of PyTorch: same model, ~3 ms per sentence, and small enough for Render's 512 MB tier.
        self.model = TextEmbedding(EMBED_MODEL, cache_dir=str(MODEL_DIR))

        # Field classifier over all fields; unchecked ones are masked out at prediction time.
        # Glossary terms count as short training examples too.
        texts = [(t, d) for d in DOMAINS for t in sentences[d]]
        texts += [(term, d) for d in DOMAINS for term in self.glossary[d]]
        self.clf = LogisticRegression(max_iter=2000, C=4.0)
        self.clf.fit(self.embed([t for t, _ in texts]), [d for _, d in texts])
        self.classes = [str(c) for c in self.clf.classes_]
        self.domain_ema: np.ndarray | None = None

        self.tone_names = list(seeds["tones"])
        self.tone_protos = np.stack([self.embed(seeds["tones"][t]).mean(axis=0) for t in self.tone_names])
        self.tone_protos /= np.linalg.norm(self.tone_protos, axis=1, keepdims=True)

        self._context_cache: tuple[str, list[str], np.ndarray] | None = None
        self.lock = threading.Lock()
        self.stats = {"terms": {}, "history": []}
        if STATE_FILE.exists():
            self.stats = _read_json(STATE_FILE) or self.stats
        log.info("ML ready: %d training examples, %d glossary terms, sources %s",
                 len(texts), sum(len(g) for g in self.glossary.values()), self.source)

    def _load(self, seeds: dict) -> tuple[dict, dict]:
        """data/ wins per context; the built-in seeds fill in whatever data/ doesn't have yet."""
        rows = []
        if (DATA / "train.jsonl").exists():
            for line in (DATA / "train.jsonl").read_text().splitlines():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("domain") in DOMAINS and row.get("text"):
                    rows.append((row["text"], row["domain"]))

        glossary, sentences = {}, {}
        for d in DOMAINS:
            from_data = _read_json(DATA / "glossaries" / f"{d}.json") if (DATA / "glossaries" / f"{d}.json").exists() else None
            glossary[d] = from_data if isinstance(from_data, dict) else dict(seeds["glossary"].get(d, {}))
            sentences[d] = [t for t, dd in rows if dd == d] or seeds["domains"].get(d, [])
            if d in FIELDS:
                self.source[d] = "data" if from_data is not None or any(dd == d for _, dd in rows) else "built-in"
        return glossary, sentences

    def _load_larp(self, seeds: dict) -> dict:
        larp = _read_json(DATA / "larp.json") if (DATA / "larp.json").exists() else None
        self.source["larp"] = "data" if isinstance(larp, dict) else "built-in"
        larp = {**seeds["larp"], **(larp if isinstance(larp, dict) else {})}
        # Longest phrases first so "pretty good" is upgraded before "good".
        larp["_upgrades"] = [(re.compile(rf"\b{re.escape(k)}\b", re.IGNORECASE), v)
                             for k, v in sorted(larp["upgrades"].items(), key=lambda kv: -len(kv[0]))]
        # A filler written with a trailing comma ("like,") only matches when followed by one, so
        # "I like tennis" is left alone. The comma before a filler goes with it: "was, like, good" -> "was good".
        larp["_fillers"] = [
            re.compile(rf"(?:,\s*)?\b{re.escape(f.rstrip(','))}" + (r",\s*" if f.endswith(",") else r"\b,?\s*"),
                       re.IGNORECASE)
            for f in sorted(larp["fillers"], key=len, reverse=True)]
        return larp

    # ------------------------------------------------------------ analysis
    def embed(self, texts: list[str]) -> np.ndarray:
        e = np.array(list(self.model.embed(texts)))
        return e / np.linalg.norm(e, axis=1, keepdims=True)

    def _masked(self, probs: np.ndarray, active: set[str]) -> dict[str, float]:
        """Field probabilities limited to the checked fields (+ general), renormalized."""
        keep = {d for d in active if d in FIELDS} | {GENERAL}
        p = {c: float(v) for c, v in zip(self.classes, probs) if c in keep}
        total = sum(p.values()) or 1.0
        return {c: round(v / total, 3) for c, v in p.items()}

    def current_domain(self, active: set[str]) -> str:
        fields = [d for d in active if d in FIELDS]
        if len(fields) == 1:
            return fields[0]            # one box checked = that field, no guessing
        if not fields or self.domain_ema is None:
            return GENERAL
        probs = self._masked(self.domain_ema, active)
        return max(probs, key=probs.get)

    def whisper_prompt(self, active: set[str]) -> str:
        """Jargon of the checked fields, so Whisper spells it right (free: same API call)."""
        terms = [t for d in FIELDS if d in active for t in self.glossary[d]]
        return ", ".join(dict.fromkeys(terms))[:600]

    def analyze(self, text: str, target: str, context: str, active: set[str]) -> dict:
        emb = self.embed([text])[0]

        probs = self.clf.predict_proba([emb])[0]
        self.domain_ema = probs if self.domain_ema is None else SMOOTHING * self.domain_ema + (1 - SMOOTHING) * probs
        domain = self.current_domain(active)

        larp_on = "larp" in active
        tone = self._tone(text, emb)
        if larp_on and tone in ("neutral", "calm"):
            tone = "confident"
        return {
            "domain": domain,
            "domain_probs": self._masked(self.domain_ema, active),
            "tone": tone,
            "terms": self.find_terms(text, domain, target),
            "context_lines": self._relevant_context(context, text, emb),
            "larp": self.enhance(text) if larp_on else None,
        }

    def enhance(self, text: str) -> dict:
        """LARP, local part: drop filler words, upgrade weak phrases. the LLM polishes the rest."""
        out, changes = text, []
        for rx in self.larp["_fillers"]:
            for m in rx.finditer(out):
                changes.append({"from": m.group(0).strip(" ,"), "to": ""})
            out = rx.sub(" ", out)
        for rx, better in self.larp["_upgrades"]:
            def swap(m):
                changes.append({"from": m.group(0), "to": better})
                return better[0].upper() + better[1:] if m.group(0)[0].isupper() else better
            out = rx.sub(swap, out)
        out = re.sub(r"\s+([,.!?])", r"\1", re.sub(r"\s{2,}", " ", out)).strip(" ,")
        out = out[:1].upper() + out[1:]
        return {"text": out, "changes": changes}

    def larp_instruction(self, domain: str) -> str:
        field = FIELDS.get(domain, "").lower() or "subject-matter"
        return self.larp["style"].format(field=field)

    def _tone(self, text: str, emb: np.ndarray) -> str:
        s = text.strip()
        if s.endswith("?"):
            return "question"
        if s.endswith("!"):
            return "excited"
        sims = self.tone_protos @ emb
        best = int(np.argmax(sims))
        return self.tone_names[best] if sims[best] >= TONE_MIN_SIM else "neutral"

    def find_terms(self, text: str, domain: str, target: str, exclude: dict | None = None) -> list[dict]:
        """Glossary terms in the sentence (detected domain + general), in sentence order.

        Longer terms are matched first so "pull request" wins over "request"."""
        found, taken = [], []
        candidates = {**self.glossary["general"], **self.glossary[domain]}
        for term in sorted(candidates, key=len, reverse=True):
            options = _norm_options(candidates[term], target)
            if not options:
                continue
            m = re.search(rf"\b{re.escape(term)}(s|es|ed|ing)?\b", text, re.IGNORECASE)
            if not m or any(a < m.end() and m.start() < b for a, b in taken):
                continue
            taken.append(m.span())
            gdomain = domain if term in self.glossary[domain] else "general"
            rejected = (exclude or {}).get(term, [])
            found.append({"term": term, "match": m.group(0), "pos": m.start(), "domain": gdomain,
                          "options": options, "choice": self.pick(gdomain, term, target, options, rejected)})
        return sorted(found, key=lambda t: t["pos"])

    def _relevant_context(self, context: str, text: str, emb: np.ndarray) -> list[str]:
        lines = [l.strip() for l in re.split(r"[\n;]+", context) if l.strip()]
        if len(context) <= CONTEXT_FULL_CHARS:
            return lines
        if not self._context_cache or self._context_cache[0] != context:
            self._context_cache = (context, lines, self.embed(lines))
        _, lines, line_embs = self._context_cache
        words = set(re.findall(r"\w{3,}", text.lower()))
        overlap = np.array([len(words & set(re.findall(r"\w{3,}", l.lower()))) for l in lines])
        score = line_embs @ emb + 0.3 * overlap
        keep = sorted(np.argsort(-score)[:CONTEXT_MAX_LINES])
        return [lines[i] for i in keep]

    # ------------------------------------------------------------ learning from feedback
    def _key(self, domain, term, target, option):
        return f"{domain}|{term}|{target}|{option}"

    def _score(self, domain, term, target, options, opt) -> float:
        """Beta posterior mean for one option. Beta(1.5,1) prior for the glossary's first option,
        Beta(1,1) for the rest, so a single 👎 is enough to switch."""
        rank = options.index(opt)
        s, f = self.stats["terms"].get(self._key(domain, term, target, opt), [0, 0])
        prior_s = 1.5 if rank == 0 else 1
        return (prior_s + s) / (prior_s + 1 + s + f) - rank * 1e-3   # glossary order breaks ties

    def pick(self, domain: str, term: str, target: str, options: list[str], rejected=()) -> str | None:
        """Option with the best posterior mean.

        Greedy rather than Thompson sampling so the live demo is predictable;
        exploration comes from thumbs down, which moves to the next-best option.
        """
        left = [o for o in options if o not in rejected]
        return max(left, key=lambda o: self._score(domain, term, target, options, o)) if left else None

    def weakest(self, terms: list[dict], target: str) -> dict | None:
        """The term we're least sure about: what a 👎 without a named term is blamed on."""
        rated = [t for t in terms if t["choice"] and len(t["options"]) > 1]
        if not rated:
            return None
        return min(rated, key=lambda t: self._score(t["domain"], t["term"], target, t["options"], t["choice"]))

    def feedback(self, terms: list[dict], val: int, target: str):
        """👍 credits every term's choice; for 👎 pass only the term that was wrong."""
        if not terms:
            return
        with self.lock:
            for t in terms:
                k = self._key(t["domain"], t["term"], target, t["choice"])
                s, f = self.stats["terms"].get(k, [0, 0])
                self.stats["terms"][k] = [s + 1, f] if val > 0 else [s, f + 1]
            self.stats["history"].append(1 if val > 0 else 0)
            self._save()

    def metrics(self) -> dict:
        h = self.stats["history"]
        window = 5
        curve = [round(sum(h[max(0, i - window + 1):i + 1]) / len(h[max(0, i - window + 1):i + 1]), 2)
                 for i in range(len(h))]
        return {"t": "metrics", "n": len(h), "accuracy": round(sum(h) / len(h), 2) if h else None,
                "curve": curve, "window": window}

    def reset(self):
        with self.lock:
            self.stats = {"terms": {}, "history": []}
            self.domain_ema = None
            self._save()

    def _save(self):
        STATE_FILE.parent.mkdir(exist_ok=True)
        STATE_FILE.write_text(json.dumps(self.stats, indent=1, ensure_ascii=False))
