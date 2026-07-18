(function () {
  var DEFAULTS = {
    horizontalStartThreshold: 12,
    verticalGuardThreshold: 8,
    submitThreshold: 96,
    maxRotation: 18,
    maxVerticalShift: 12,
    commitDurationMs: 340,
  };
  var lockedScrollY = null;

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function shouldStartHorizontalDrag(dx, dy, options) {
    return Math.abs(dx) >= options.horizontalStartThreshold && Math.abs(dx) > Math.abs(dy) + options.verticalGuardThreshold;
  }

  function getSwipeVisualState(dx, options) {
    var absoluteDx = Math.abs(dx);
    var progress = clamp(absoluteDx / options.submitThreshold, 0, 1);
    return {
      direction: dx < 0 ? "left" : "right",
      progress: progress,
      opacity: 0.32 + progress * 0.58,
      scaleBoost: 0.06 + progress * 0.32,
      rotation: clamp(dx / 18, -options.maxRotation, options.maxRotation),
      liftPx: progress * 14,
      scale: 1.0 - progress * 0.035,
    };
  }

  function setInteractionLock(locked) {
    if (locked && lockedScrollY == null) {
      lockedScrollY = window.scrollY;
      document.body.style.setProperty("--card-lock-top", -lockedScrollY + "px");
      document.body.classList.add("is-card-interacting");
      return;
    }

    if (!locked && lockedScrollY != null) {
      var scrollY = lockedScrollY;
      lockedScrollY = null;
      document.body.classList.remove("is-card-interacting");
      document.body.style.removeProperty("--card-lock-top");
      window.scrollTo(0, scrollY);
    }
  }

  document.addEventListener(
    "touchmove",
    function (event) {
      if (lockedScrollY != null && event.cancelable) {
        event.preventDefault();
      }
    },
    { passive: false }
  );

  function parseThreshold(card) {
    var rawValue = Number(card.dataset.submitThreshold);
    if (Number.isFinite(rawValue) && rawValue > 0) {
      return rawValue;
    }
    return DEFAULTS.submitThreshold;
  }

  function applySwipeVisuals(card, dx, dy, options) {
    var visual = getSwipeVisualState(dx, options);
    var verticalShift = clamp(dy / 8, -options.maxVerticalShift, options.maxVerticalShift);
    var anchorX = Number(card.dataset.swipeAnchorX || 50);
    var anchorY = Number(card.dataset.swipeAnchorY || 72);
    var topFreedom = clamp((90 - anchorY) / 62, 0.18, 1.18);
    var tiltX = clamp(((-dy / 18) * topFreedom) + ((anchorY - 56) / 22), -11, 11);
    var tiltY = clamp(((dx / 24) * topFreedom) + ((anchorX - 50) / 11), -15, 15);
    var translateX = dx * (0.76 + topFreedom * 0.2);
    var translateY = verticalShift - visual.liftPx * (0.72 + topFreedom * 0.28);
    var scale = 1.0 - visual.progress * (0.02 + topFreedom * 0.02);

    card.dataset.dragDirection = visual.direction;
    card.style.setProperty("--swipe-progress", String(visual.progress));
    card.style.setProperty("--swipe-visual-opacity", String(visual.opacity));
    card.style.setProperty("--swipe-visual-scale", String(visual.scaleBoost));
    card.style.setProperty("--swipe-lift", String(visual.liftPx) + "px");
    card.style.setProperty("--swipe-card-scale", String(scale));
    card.style.setProperty("--swipe-tilt-x", String(tiltX) + "deg");
    card.style.setProperty("--swipe-tilt-y", String(tiltY) + "deg");
    card.style.transform =
      "translate3d(" + translateX + "px, " + translateY + "px, 0) rotateZ(" + visual.rotation + "deg) rotateX(" + tiltX + "deg) rotateY(" + tiltY + "deg) scale(" + scale + ")";
  }

  function clearSwipeVisuals(card) {
    card.classList.remove("is-dragging", "is-returning");
    card.removeAttribute("data-drag-direction");
    card.style.removeProperty("--swipe-progress");
    card.style.removeProperty("--swipe-visual-opacity");
    card.style.removeProperty("--swipe-visual-scale");
    card.style.removeProperty("--swipe-lift");
    card.style.removeProperty("--swipe-card-scale");
    card.style.removeProperty("--swipe-tilt-x");
    card.style.removeProperty("--swipe-tilt-y");
    card.style.removeProperty("transform-origin");
    delete card.dataset.swipeAnchorX;
    delete card.dataset.swipeAnchorY;
    card.style.transform = "";
  }

  function animateSnapBack(card) {
    card.classList.add("is-returning");
    card.style.transform = "";
    window.setTimeout(function () {
      clearSwipeVisuals(card);
    }, 190);
  }

  function animateCommit(card, direction) {
    var flyoutDistance = Math.max(window.innerWidth * 1.15, card.offsetWidth * 2.3);
    var signedDistance = direction === "left" ? -flyoutDistance : flyoutDistance;
    var rotation = direction === "left" ? -24 : 24;

    card.classList.remove("is-dragging", "is-returning");
    card.classList.add("is-committing", "is-submitting");
    card.dataset.dragDirection = direction;
    card.style.setProperty("--swipe-visual-opacity", "0.9");
    card.style.setProperty("--swipe-visual-scale", "0.24");
    card.style.transform =
      "translate3d(" + signedDistance + "px, -26px, 0) rotate(" + rotation + "deg) scale(0.94)";
  }

  function directionForVerdict(selectedVerdict) {
    return selectedVerdict === "inaccuracy" ? "left" : "right";
  }

  function isFormControl(target) {
    return Boolean(target && target.closest && target.closest("input, textarea, select, button, label"));
  }

  function attachSwipePreview(card) {
    var options = {
      horizontalStartThreshold: DEFAULTS.horizontalStartThreshold,
      verticalGuardThreshold: DEFAULTS.verticalGuardThreshold,
      submitThreshold: parseThreshold(card),
      maxRotation: DEFAULTS.maxRotation,
      maxVerticalShift: DEFAULTS.maxVerticalShift,
    };

    var state = {
      activePointerId: null,
      startX: 0,
      startY: 0,
      dragging: false,
      dx: 0,
      dy: 0,
      submitting: false,
    };

    function releasePointer(event) {
      if (state.activePointerId != null && card.hasPointerCapture(state.activePointerId)) {
        card.releasePointerCapture(state.activePointerId);
      }
      state.activePointerId = null;
      if (event) {
        state.dx = event.clientX - state.startX;
        state.dy = event.clientY - state.startY;
      }
      setInteractionLock(false);
    }

    function onPointerDown(event) {
      if (state.submitting) {
        return;
      }
      if (event.pointerType === "mouse" && event.button !== 0) {
        return;
      }
      if (isFormControl(event.target)) {
        return;
      }

      if (event.pointerType !== "mouse") {
        event.preventDefault();
      }

      state.activePointerId = event.pointerId;
      state.startX = event.clientX;
      state.startY = event.clientY;
      state.dragging = false;
      state.dx = 0;
      state.dy = 0;
      var rect = card.getBoundingClientRect();
      var anchorXPercent = clamp(((event.clientX - rect.left) / rect.width) * 100, 18, 82);
      var anchorYPercent = clamp(((event.clientY - rect.top) / rect.height) * 100, 12, 86);
      card.dataset.swipeAnchorX = String(anchorXPercent);
      card.dataset.swipeAnchorY = String(anchorYPercent);
      card.style.transformOrigin = anchorXPercent + "% 88%";
      setInteractionLock(true);
      card.setPointerCapture(event.pointerId);
      card.focus({ preventScroll: true });
    }

    function onPointerMove(event) {
      if (event.pointerId !== state.activePointerId || state.submitting) {
        return;
      }

      state.dx = event.clientX - state.startX;
      state.dy = event.clientY - state.startY;

      event.preventDefault();

      if (!state.dragging) {
        if (!shouldStartHorizontalDrag(state.dx, state.dy, options)) {
          return;
        }

        state.dragging = true;
        card.classList.add("is-dragging");
      }

      applySwipeVisuals(card, state.dx, state.dy, options);
    }

    function onPointerUp(event) {
      if (event.pointerId !== state.activePointerId || state.submitting) {
        return;
      }

      releasePointer(event);

      if (!state.dragging) {
        clearSwipeVisuals(card);
        return;
      }

      if (
        Math.abs(state.dx) >= options.submitThreshold &&
        typeof window.submitCardDirection === "function"
      ) {
        var direction = state.dx < 0 ? "left" : "right";

        if (
          typeof window.canSubmitCardDirection === "function" &&
          !window.canSubmitCardDirection(direction)
        ) {
          animateSnapBack(card);
          return;
        }

        state.submitting = true;
        animateCommit(card, direction);
        window.submitCardDirection(direction, "swipe", { skipAnimation: true });
        return;
      }

      animateSnapBack(card);
    }

    function onPointerCancel(event) {
      if (event.pointerId !== state.activePointerId || state.submitting) {
        return;
      }
      releasePointer(event);
      clearSwipeVisuals(card);
    }

    card.addEventListener("pointerdown", onPointerDown);
    card.addEventListener("pointermove", onPointerMove);
    card.addEventListener("pointerup", onPointerUp);
    card.addEventListener("pointercancel", onPointerCancel);
    card.addEventListener("dragstart", function (event) {
      event.preventDefault();
    });
  }

  window.landauSwipeUtils = {
    shouldStartHorizontalDrag: shouldStartHorizontalDrag,
    getSwipeVisualState: getSwipeVisualState,
    animateCommit: animateCommit,
    directionForVerdict: directionForVerdict,
    commitDurationMs: DEFAULTS.commitDurationMs,
  };

  window.initializeSwipePreview = function initializeSwipePreview() {
    document.querySelectorAll("[data-swipe-preview]").forEach(attachSwipePreview);
  };
})();
