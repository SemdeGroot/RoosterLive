// haptic_feedback.js
// - Mobile only
// - 1 tick per tap
// - iOS fallback uses the SAME switch/label hack as your refresh.js
// - Prevents the synthetic label.click() from bubbling to document (so it won't close menus)

(function () {
  const isMobileDevice =
    (window.matchMedia && window.matchMedia("(pointer: coarse)").matches) ||
    "ontouchstart" in window ||
    (navigator.maxTouchPoints && navigator.maxTouchPoints > 0);

  if (!isMobileDevice) return;

  window.HapticFeedback = {
    tick: hapticTick,
    bind: bindHaptics,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => bindHaptics());
  } else {
    bindHaptics();
  }

  // EXACT same haptic logic as refresh.js, but with one crucial addition:
  // stop propagation of the synthetic click so it doesn't trigger "click outside" handlers.
  function hapticTick() {
    if (navigator.vibrate) {
      navigator.vibrate(40);
      return;
    }

    const el = document.createElement("div");
    const id = "haptic-" + Math.random().toString(36).slice(2);

    el.innerHTML =
      '<input type="checkbox" id="' + id + '" switch />' +
      '<label for="' + id + '"></label>';

    el.style.cssText =
      "position:fixed;left:-9999px;top:auto;width:1px;height:1px;" +
      "overflow:hidden;opacity:0;pointer-events:none;";

    // ✅ Key fix: absorb synthetic events inside this temp node
    // Use capture so it catches the click early and stops it reaching document.
    el.addEventListener(
      "click",
      (ev) => {
        ev.stopPropagation();
        ev.stopImmediatePropagation();
      },
      true
    );

    document.body.appendChild(el);

    const label = el.querySelector("label");
    if (label) {
      label.click(); // same as your refresh.js, but now it won't bubble out
    }

    setTimeout(() => {
      el.remove();
    }, 500);
  }

  function bindHaptics(selector = "[data-haptic]") {
    const nodes = Array.from(document.querySelectorAll(selector));

    nodes.forEach((node) => {
      if (node.__hapticBound) return;
      node.__hapticBound = true;

      let lastTouchTs = 0;

      const shouldSkip = () => {
        const attr = node.getAttribute("data-haptic");
        if (attr && attr.toLowerCase() === "off") return true;
        if (node.matches("button:disabled, [aria-disabled='true']")) return true;
        return false;
      };

      // Trigger on touchstart for instant feedback
      node.addEventListener(
        "touchstart",
        () => {
          if (shouldSkip()) return;
          lastTouchTs = Date.now();
          hapticTick();
        },
        { passive: true }
      );

      // Fallback click (ignore synthetic click that follows touch)
      node.addEventListener(
        "click",
        () => {
          if (shouldSkip()) return;
          if (Date.now() - lastTouchTs < 700) return;
          hapticTick();
        },
        { passive: true }
      );
    });
  }
})();