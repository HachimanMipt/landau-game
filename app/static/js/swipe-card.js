(function () {
  "use strict";

  var PHYSICS = {
    startDistance: 3,
    defaultSubmitThreshold: 110,
    flickVelocity: 0.55,
    flickMinDistance: 34,
    maxRotation: 12,
    maxVerticalShift: 30,
    snapDurationMs: 340,
    commitDurationMs: 360,
  };
  var lockedScrollY = null;
  var snapTimers = new WeakMap();

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function directionForVerdict(selectedVerdict) {
    return selectedVerdict === "inaccuracy" ? "left" : "right";
  }

  function isFormControl(target) {
    return Boolean(target && target.closest && target.closest("input, textarea, select, button, label"));
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

  function submitThresholdFor(card) {
    var configured = Number(card.dataset.submitThreshold);
    if (Number.isFinite(configured) && configured > 0) {
      return configured;
    }
    return Math.max(82, Math.min(PHYSICS.defaultSubmitThreshold, card.offsetWidth * 0.3));
  }

  function motionFor(dx, dy, cardWidth, threshold) {
    var progress = clamp(Math.abs(dx) / threshold, 0, 1);
    var rotation = clamp((dx / Math.max(cardWidth, 1)) * 16, -PHYSICS.maxRotation, PHYSICS.maxRotation);

    return {
      direction: dx < 0 ? "left" : "right",
      progress: progress,
      translateX: dx * 0.72,
      translateY: clamp(dy * 0.36, -PHYSICS.maxVerticalShift, PHYSICS.maxVerticalShift) - progress * 5,
      rotation: rotation,
      labelOpacity: clamp((Math.abs(dx) - 8) / Math.max(threshold * 0.72, 1), 0, 1),
      labelScale: progress * 0.18,
    };
  }

  function getSwipeVisualState(dx, options) {
    var resolved = options || {};
    return motionFor(
      dx,
      resolved.dy || 0,
      resolved.cardWidth || 360,
      resolved.submitThreshold || PHYSICS.defaultSubmitThreshold
    );
  }

  function renderDrag(card, state) {
    state.frameId = null;
    var motion = motionFor(state.dx, state.dy, state.cardWidth, state.submitThreshold);

    card.dataset.dragDirection = motion.direction;
    card.style.setProperty("--swipe-progress", String(motion.progress));
    card.style.setProperty("--swipe-visual-opacity", String(motion.labelOpacity));
    card.style.setProperty("--swipe-visual-scale", String(motion.labelScale));
    card.style.transform =
      "translate3d(" +
      motion.translateX +
      "px, " +
      motion.translateY +
      "px, 0) rotate(" +
      motion.rotation +
      "deg)";
  }

  function scheduleRender(card, state) {
    if (state.frameId != null) {
      return;
    }
    state.frameId = window.requestAnimationFrame(function () {
      renderDrag(card, state);
    });
  }

  function clearVisualState(card) {
    card.classList.remove("is-held", "is-dragging", "is-returning");
    card.removeAttribute("data-drag-direction");
    card.style.removeProperty("--swipe-progress");
    card.style.removeProperty("--swipe-visual-opacity");
    card.style.removeProperty("--swipe-visual-scale");
    card.style.removeProperty("transform-origin");
    card.style.removeProperty("transform");
  }

  function animateSnapBack(card) {
    window.clearTimeout(snapTimers.get(card));
    card.classList.remove("is-held", "is-dragging");
    card.classList.add("is-returning");
    card.getBoundingClientRect();

    window.requestAnimationFrame(function () {
      card.style.transform = "translate3d(0, 0, 0) rotate(0deg)";
    });

    snapTimers.set(card, window.setTimeout(function () {
      snapTimers.delete(card);
      clearVisualState(card);
    }, PHYSICS.snapDurationMs));
  }

  function animateCommit(card, direction, releaseVelocity) {
    var flyoutDistance = Math.max(window.innerWidth * 1.25, card.offsetWidth * 2.5);
    var signedDistance = direction === "left" ? -flyoutDistance : flyoutDistance;
    var rotation = direction === "left" ? -16 : 16;
    var velocityLift = clamp(Math.abs(releaseVelocity || 0) * 12, 0, 16);

    card.classList.remove("is-held", "is-dragging", "is-returning");
    card.classList.add("is-committing", "is-submitting");
    card.dataset.dragDirection = direction;
    card.style.setProperty("--swipe-visual-opacity", "1");
    card.style.setProperty("--swipe-visual-scale", "0.18");
    card.style.transformOrigin = "50% 100%";
    card.getBoundingClientRect();

    window.requestAnimationFrame(function () {
      card.style.transform =
        "translate3d(" + signedDistance + "px, " + (-20 - velocityLift) + "px, 0) rotate(" + rotation + "deg)";
    });
  }

  function shouldStartHorizontalDrag(dx, dy) {
    return Math.hypot(dx, dy) >= PHYSICS.startDistance;
  }

  function attachSwipeCard(card) {
    if (card.dataset.swipeWired === "true") {
      return;
    }
    card.dataset.swipeWired = "true";

    var state = {
      pointerId: null,
      startX: 0,
      startY: 0,
      lastX: 0,
      lastTime: 0,
      dx: 0,
      dy: 0,
      velocityX: 0,
      cardWidth: card.offsetWidth || 360,
      submitThreshold: submitThresholdFor(card),
      dragging: false,
      submitting: false,
      frameId: null,
    };

    function updatePointer(event) {
      var now = event.timeStamp || Date.now();
      var elapsed = Math.max(1, now - state.lastTime);
      var instantVelocity = (event.clientX - state.lastX) / elapsed;

      state.velocityX = state.velocityX * 0.65 + instantVelocity * 0.35;
      state.lastX = event.clientX;
      state.lastTime = now;
      state.dx = event.clientX - state.startX;
      state.dy = event.clientY - state.startY;
    }

    function releasePointer() {
      if (state.pointerId != null && card.hasPointerCapture(state.pointerId)) {
        card.releasePointerCapture(state.pointerId);
      }
      state.pointerId = null;
      setInteractionLock(false);
    }

    function onPointerDown(event) {
      if (state.submitting || (event.pointerType === "mouse" && event.button !== 0) || isFormControl(event.target)) {
        return;
      }

      if (event.cancelable) {
        event.preventDefault();
      }

      state.pointerId = event.pointerId;
      state.startX = event.clientX;
      state.startY = event.clientY;
      state.lastX = event.clientX;
      state.lastTime = event.timeStamp || Date.now();
      state.dx = 0;
      state.dy = 0;
      state.velocityX = 0;
      state.dragging = false;
      state.cardWidth = card.getBoundingClientRect().width || card.offsetWidth || 360;
      state.submitThreshold = submitThresholdFor(card);

      window.clearTimeout(snapTimers.get(card));
      snapTimers.delete(card);
      card.classList.remove("is-returning");
      card.classList.add("is-held");
      card.style.transformOrigin = "50% 100%";
      setInteractionLock(true);
      card.setPointerCapture(event.pointerId);
      card.focus({ preventScroll: true });
    }

    function onPointerMove(event) {
      if (event.pointerId !== state.pointerId || state.submitting) {
        return;
      }

      if (event.cancelable) {
        event.preventDefault();
      }
      updatePointer(event);

      if (!state.dragging && !shouldStartHorizontalDrag(state.dx, state.dy)) {
        return;
      }

      if (!state.dragging) {
        state.dragging = true;
        card.classList.add("is-dragging");
      }
      scheduleRender(card, state);
    }

    function onPointerUp(event) {
      if (event.pointerId !== state.pointerId || state.submitting) {
        return;
      }

      updatePointer(event);
      if (state.frameId != null) {
        window.cancelAnimationFrame(state.frameId);
        renderDrag(card, state);
      }
      releasePointer();

      if (!state.dragging) {
        clearVisualState(card);
        return;
      }

      var crossedDistance = Math.abs(state.dx) >= state.submitThreshold;
      var flicked = Math.abs(state.velocityX) >= PHYSICS.flickVelocity && Math.abs(state.dx) >= PHYSICS.flickMinDistance;
      if (!crossedDistance && !flicked) {
        animateSnapBack(card);
        return;
      }

      var direction = state.dx === 0 ? (state.velocityX < 0 ? "left" : "right") : state.dx < 0 ? "left" : "right";
      if (
        typeof window.canSubmitCardDirection === "function" &&
        !window.canSubmitCardDirection(direction)
      ) {
        animateSnapBack(card);
        return;
      }

      state.submitting = true;
      animateCommit(card, direction, state.velocityX);
      if (typeof window.submitCardDirection === "function") {
        window.submitCardDirection(direction, "swipe", { skipAnimation: true });
      }
    }

    function onPointerCancel(event) {
      if (event.pointerId !== state.pointerId || state.submitting) {
        return;
      }
      releasePointer();
      if (state.dragging) {
        animateSnapBack(card);
      } else {
        clearVisualState(card);
      }
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
    commitDurationMs: PHYSICS.commitDurationMs,
  };

  window.initializeSwipePreview = function initializeSwipePreview() {
    document.querySelectorAll("[data-swipe-preview]").forEach(attachSwipeCard);
  };
})();
