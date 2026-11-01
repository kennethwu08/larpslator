"""Local, free ML: everything except the actual translation runs on the laptop.

- domain:  sentence embedding (all-MiniLM-L6-v2) -> LogisticRegression, smoothed over the conversation
- tone:    punctuation rules, then nearest tone prototype by embedding
- terms:   glossary lookup for the detected domain
- choice:  which translation to use per term, learned from thumbs up/down (Beta posterior per option)
- context: only the context-pack lines relevant to this sentence go to Gemini
"""
import json
import logging
import re
import threading
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression

HERE = Path(__file__).parent
DATA = HERE.parent / "data"            # owned by Role D; read-only here
STATE_FILE = HERE / "state" / "term_stats.json"
EMBED_MODEL = "all-MiniLM-L6-v2"
DOMAINS = ["academia", "cs", "med", "general"]
SMOOTHING = 0.5                        # weight of the previous sentences in the domain estimate
TONE_MIN_SIM = 0.35                    # below this, tone stays neutral
CONTEXT_FULL_CHARS = 400               # context packs shorter than this are sent whole
CONTEXT_MAX_LINES = 5

log = logging.getLogger("larpslator.ml")


def _norm_options(value, target: str) -> list[str]:
    """Glossary values are either a list (one target language) or {language: list}."""
    if isinstance(value, list):
        return value
    return value.get(target, []) if isinstance(value, dict) else []


class LocalML:
    def __init__(self):
        seeds = json.loads((HERE / "seeds.json").read_text())
        self.glossary: dict[str, dict] = {d: dict(seeds["glossary"].get(d, {})) for d in DOMAINS}
        texts = [(t, d) for d, ts in seeds["domains"].items() for t in ts]
        self._load_data_folder(texts)

        log.info("loading %s (first run downloads ~90 MB)", EMBED_MODEL)
        # CPU on purpose: the Apple GPU (MPS) backend crashes on macOS 14, and MiniLM takes ~15 ms on CPU anyway.
        self.model = SentenceTransformer(EMBED_MODEL, device="cpu")

        # Domain classifier. Glossary terms count as short training examples too.
        texts += [(term, d) for d in DOMAINS for term in self.glossary[d]]
        self.clf = LogisticRegression(max_iter=2000, C=4.0)
        self.clf.fit(self.embed([t for t, _ in texts]), [d for _, d in texts])
        self.domain_ema: np.ndarray | None = None

        self.tone_names = list(seeds["tones"])
        self.tone_protos = np.stack([self.embed(seeds["tones"][t]).mean(axis=0) for t in self.tone_names])
        self.tone_protos /= np.linalg.norm(self.tone_protos, axis=1, keepdims=True)

        self._context_cache: tuple[str, list[str], np.ndarray] | None = None
        self.lock = threading.Lock()
        self.stats = {"terms": {}, "history": []}
        if STATE_FILE.exists():
            self.stats = json.loads(STATE_FILE.read_text())
        log.info("ML ready: %d training sentences, %d glossary terms",
                 len(texts), sum(len(g) for g in self.glossary.values()))

    def _load_data_folder(self, texts: list):
        for d in DOMAINS:
            p = DATA / "glossaries" / f"{d}.json"
            if p.exists():
                try:
                    self.glossary[d].update(json.loads(p.read_text()))
                    log.info("glossary: loaded %s", p.relative_to(HERE.parent))
                except (OSError, json.JSONDecodeError) as e:
                    log.warning("glossary: skipping %s: %s", p.name, e)
        p = DATA / "train.jsonl"
        if p.exists():
            for line in p.read_text().splitlines():
                try:
                    row = json.loads(line)
                    if row.get("domain") in DOMAINS and row.get("text"):
                        texts.append((row["text"], row["domain"]))
                except json.JSONDecodeError:
                    continue

    # ------------------------------------------------------------ analysis
    def embed(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

    def current_domain(self, override: str = "auto") -> str:
        if override in DOMAINS:
            return override
        if self.domain_ema is None:
            return "general"
        return str(self.clf.classes_[int(np.argmax(self.domain_ema))])

    def whisper_prompt(self, override: str = "auto") -> str:
        """Jargon of the current domain, so Whisper spells it right (free: same API call)."""
        terms = list(self.glossary[self.current_domain(override)])[:40]
        return ", ".join(terms)

    def analyze(self, text: str, target: str, context: str, override: str = "auto") -> dict:
        emb = self.embed([text])[0]

        probs = self.clf.predict_proba([emb])[0]
        self.domain_ema = probs if self.domain_ema is None else SMOOTHING * self.domain_ema + (1 - SMOOTHING) * probs
        domain = self.current_domain(override)

        return {
            "domain": domain,
            "domain_probs": {str(c): round(float(p), 3) for c, p in zip(self.clf.classes_, self.domain_ema)},
            "tone": self._tone(text, emb),
            "terms": self.find_terms(text, domain, target),
            "context_lines": self._relevant_context(context, text, emb),
        }

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
