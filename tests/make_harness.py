#!/usr/bin/env python3
"""Create a browser harness that exercises the review note modal.

Usage: python tests/make_harness.py <Prototype.html> <harness.html>
Then open harness.html headless and inspect the dumped DOM for `harness note`.
"""
from __future__ import annotations

import sys
from pathlib import Path

INJECT = r"""
<script>
(function () {
  function finish(message) {
    document.body.setAttribute("data-harness", message);
  }
  setTimeout(function () {
    var noteButton = document.getElementById("wc-review-note");
    if (!noteButton) { finish("missing-note-button"); return; }
    noteButton.click();
    setTimeout(function () {
      var textarea = document.querySelector("#wc-modal textarea");
      var save = document.querySelector("#wc-modal-actions .primary");
      if (!textarea || !save) { finish("missing-modal-controls"); return; }
      textarea.value = "harness note";
      save.click();
      setTimeout(function () {
        var key = Object.keys(localStorage).filter(function (k) { return k.indexOf("wc-review:prototype:") === 0; })[0];
        finish(key ? localStorage.getItem(key) : "missing-storage");
      }, 250);
    }, 250);
  }, 250);
})();
</script>
"""


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    source = Path(argv[0])
    target = Path(argv[1])
    text = source.read_text(encoding="utf-8")
    if "</body>" not in text:
        raise SystemExit("no </body>")
    target.write_text(text.replace("</body>", INJECT + "\n</body>"), encoding="utf-8")
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
