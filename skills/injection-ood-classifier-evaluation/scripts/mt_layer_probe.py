"""Probe a translation layer on its own, before blaming the combine rule.

Run INSIDE the service image, so the MT checkpoint and library versions are the
deployed ones and the container's own memory limit applies:

    docker run --rm -m 1300m --cpus 2 -v "$PWD/mt_layer_probe.py":/p.py \
        -e MT_MODEL_PATH=/app/mt_model <image> python /p.py \
        -- "hai" "halo" "hai apa kabar"

What the two passes tell you:
  * bare vs `>>xx<< `-prefixed translation — if the prefixed run returns the
    same text, or the prefix decodes to filler/`<unk>`, the checkpoint carries
    NO language-token vocab and the caller must gate on its own detection.
  * which source language codes are actually honoured, so you can tell a
    missing-token checkpoint from a wrong-code call.

Kept dependency-light on purpose: reads MT_MODEL_PATH, prints one line per case,
exits non-zero only if the model cannot load at all.
"""

import argparse
import os
import sys

MODEL_PATH = os.getenv("MT_MODEL_PATH", "/app/mt_model")
MAX_INPUT = int(os.getenv("MT_MAX_INPUT_TOKENS", "192"))
MAX_NEW = int(os.getenv("MT_MAX_NEW_TOKENS", "64"))
# Codes worth probing on a many-to-one checkpoint: pick the one the traffic uses
# plus one that should obviously work (English as the identity check).
CODES = os.getenv("MT_PROBE_CODES", "ind,jav,sun,tha,rus,eng")


def load():
    try:
        import torch  # noqa: F401
        from transformers import MarianMTModel, MarianTokenizer
    except ImportError as exc:
        sys.exit(f"[ERROR] transformers/torch tidak tersedia: {exc}")
    try:
        tok = MarianTokenizer.from_pretrained(MODEL_PATH)
        model = MarianMTModel.from_pretrained(MODEL_PATH)
        model.eval()
        return torch, tok, model
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"[ERROR] gagal memuat MT dari '{MODEL_PATH}': {type(exc).__name__}: {exc}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("texts", nargs="*", default=["hai", "halo", "hai apa kabar"])
    args = ap.parse_args()

    torch, tok, model = load()

    def translate(s):
        batch = tok([s], return_tensors="pt", padding=True,
                    truncation=True, max_length=MAX_INPUT)
        with torch.inference_mode():
            gen = model.generate(**batch, max_new_tokens=MAX_NEW, num_beams=6)
        return tok.batch_decode(gen, skip_special_tokens=True)[0].strip()

    for text in args.texts:
        bare = translate(text)
        print(f"{text!r:50} -> bare {bare!r}", flush=True)
        for code in CODES.split(","):
            tagged = translate(f">>{code}<< {text}")
            mark = "" if tagged.strip().lower() == bare.strip().lower() else "   <-- honored"
            print(f"{'':50}    >>{code}<<  -> {tagged!r}{mark}", flush=True)


if __name__ == "__main__":
    main()