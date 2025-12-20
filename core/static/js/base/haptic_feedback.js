// haptic_feedback.js
// Mobile-only haptic feedback that triggers ONLY on a real tap/click (not on scroll).
// Uses the same hapticTick logic as refresh.js (vibrate + iOS switch/label hack).
// Also blocks the synthetic label.click() from bubbling to document (prevents menu close interference).

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

  // EXACT same haptic logic as your refresh.js (+ stop propagation of synthetic click)
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

    // Prevent the synthetic label click from reaching document click handlers
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
    if (label) label.click();

    setTimeout(() => el.remove(), 500);
  }

  function bindHaptics(selector = "[data-haptic]") {
    const nodes = Array.from(document.querySelectorAll(selector));

    nodes.forEach((node) => {
      if (node.__hapticBound) return;
      node.__hapticBound = true;

      const TAP_MOVE_THRESHOLD = 10; // px; above this we treat as scroll/drag
      let startX = 0;
      let startY = 0;
      let moved = false;
      let pointerId = null;

      // Gate click after we already handled tap on pointerup
      let lastTapTs = 0;

      const shouldSkip = () => {
        const attr = node.getAttribute("data-haptic");
        if (attr && attr.toLowerCase() === "off") return true;
        if (node.matches("button:disabled, [aria-disabled='true']")) return true;
        return false;
      };

      const onDown = (x, y, id) => {
        if (shouldSkip()) return;
        startX = x;
        startY = y;
        moved = false;
        pointerId = id ?? null;
      };

      const onMove = (x, y) => {
        if (pointerId === null) return;
        if (Math.abs(x - startX) > TAP_MOVE_THRESHOLD || Math.abs(y - startY) > TAP_MOVE_THRESHOLD) {
          moved = true;
        }
      };

      const onUp = () => {
        if (pointerId === null) return;
        const wasMoved = moved;
        pointerId = null;

        // Only tick if it was a real tap (not a scroll)
        if (!wasMoved && !shouldSkip()) {
          lastTapTs = Date.now();
          hapticTick();
        }
      };

      // Pointer Events (best on modern mobile)
      if (window.PointerEvent) {
        node.addEventListener(
          "pointerdown",
          (e) => {
            if (e.pointerType !== "touch" && e.pointerType !== "pen") return;
            onDown(e.clientX, e.clientY, e.pointerId);
          },
          { passive: true }
        );

        node.addEventListener(
          "pointermove",
          (e) => {
            if (e.pointerId !== pointerId) return;
            onMove(e.clientX, e.clientY);
          },
          { passive: true }
        );

        node.addEventListener(
          "pointerup",
          (e) => {
            if (e.pointerId !== pointerId) return;
            onUp();
          },
          { passive: true }
        );

        node.addEventListener(
          "pointercancel",
          () => {
            pointerId = null;
          },
          { passive: true }
        );
      } else {
        // Fallback for older Safari: touch events
        node.addEventListener(
          "touchstart",
          (e) => {
            if (e.touches.length !== 1) return;
            const t = e.touches[0];
            onDown(t.clientX, t.clientY, 1);
          },
          { passive: true }
        );

        node.addEventListener(
          "touchmove",
          (e) => {
            if (!pointerId) return;
            const t = e.touches[0];
            onMove(t.clientX, t.clientY);
          },
          { passive: true }
        );

        node.addEventListener(
          "touchend",
          () => onUp(),
          { passive: true }
        );

        node.addEventListener(
          "touchcancel",
          () => {
            pointerId = null;
          },
          { passive: true }
        );
      }

      // Click fallback (keyboard / non-touch / odd cases). Ignore if we just handled a tap.
      node.addEventListener(
        "click",
        () => {
          if (shouldSkip()) return;
          if (Date.now() - lastTapTs < 700) return; // avoid double tick
          hapticTick();
        },
        { passive: true }
      );
    });
  }
})();