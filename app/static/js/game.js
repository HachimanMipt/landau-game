(function () {
  var MIN_COMMIT_VISIBILITY_MS = 210;
  var isSubmitting = false;
  var liveRegion = null;

  function getInteractiveCard() {
    return document.querySelector("[data-swipe-preview]");
  }

  function getAnswerForms() {
    return document.querySelectorAll("[data-answer-form]");
  }

  function announce(message) {
    if (!liveRegion || !message) {
      return;
    }

    liveRegion.textContent = "";
    window.requestAnimationFrame(function () {
      liveRegion.textContent = message;
    });
  }

  function setAnswerControlsDisabled(disabled) {
    getAnswerForms().forEach(function (form) {
      form.querySelectorAll("button").forEach(function (button) {
        button.disabled = disabled;
      });
    });

    var card = getInteractiveCard();
    if (card) {
      card.classList.toggle("is-submitting", disabled);
      card.setAttribute("aria-disabled", disabled ? "true" : "false");
    }
  }

  function showCardError(card, message) {
    if (!card) {
      return;
    }

    var error = card.querySelector("[data-card-error]");
    if (!error) {
      return;
    }

    error.textContent = message;
    error.hidden = false;
  }

  function clearCardError(card) {
    if (!card) {
      return;
    }

    var error = card.querySelector("[data-card-error]");
    if (!error) {
      return;
    }

    error.textContent = "";
    error.hidden = true;
  }

  function verdictLabel(selectedVerdict) {
    return selectedVerdict === "inaccuracy" ? "Есть неточность" : "Ответ верный";
  }

  function progressLabel(direction, card) {
    if (card) {
      var cardLabel = direction === "left" ? card.dataset.leftLabel : card.dataset.rightLabel;
      if (cardLabel) {
        return cardLabel;
      }
    }
    return direction === "left" ? "Понятно" : "Интересно";
  }

  function getCardMode(card) {
    if (!card || !card.dataset.cardMode) {
      return "answer";
    }
    return card.dataset.cardMode;
  }

  function playCommitAnimation(card, direction, options) {
    if (!card) {
      return 0;
    }

    if (options && options.skipAnimation) {
      if (window.landauSwipeUtils && window.landauSwipeUtils.commitDurationMs) {
        return window.landauSwipeUtils.commitDurationMs;
      }
      return MIN_COMMIT_VISIBILITY_MS;
    }

    if (
      window.landauSwipeUtils &&
      typeof window.landauSwipeUtils.animateCommit === "function" &&
      typeof direction === "string"
    ) {
      window.landauSwipeUtils.animateCommit(card, direction);
      return window.landauSwipeUtils.commitDurationMs || MIN_COMMIT_VISIBILITY_MS;
    }

    card.classList.add("is-submitting");
    return 0;
  }

  function submitJsonAction(card, url, body, announceMessage, direction, options) {
    if (isSubmitting) {
      return;
    }

    isSubmitting = true;
    var animationDelayMs = playCommitAnimation(card, direction, options);
    var startedAt = Date.now();
    setAnswerControlsDisabled(true);
    announce(announceMessage);

    window.fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
      body: body ? JSON.stringify(body) : null,
    })
      .then(function (response) {
        return response.json().then(function (data) {
          return {
            ok: response.ok,
            data: data,
          };
        });
      })
      .then(function (payload) {
        var elapsedMs = Date.now() - startedAt;
        var remainingDelayMs = Math.max(0, animationDelayMs - elapsedMs);

        window.setTimeout(function () {
          window.location.assign(payload.data.redirect_url || "/play");
        }, remainingDelayMs);
      })
      .catch(function () {
        window.location.reload();
      });
  }

  function submitCurrentAnswer(selectedVerdict, inputMethod, options) {
    var card = getInteractiveCard();
    var apiUrl = card ? card.dataset.answerApiUrl : "/api/answers/current";
    var direction = selectedVerdict === "inaccuracy" ? "left" : "right";

    submitJsonAction(
      card,
      apiUrl,
      {
        selected_verdict: selectedVerdict,
        input_method: inputMethod,
      },
      "Выбран вердикт: " + verdictLabel(selectedVerdict) + ". Ответ отправляется.",
      direction,
      options
    );
  }

  function advanceFromResultCard(direction, inputMethod, options) {
    var card = getInteractiveCard();
    var apiUrl = card ? card.dataset.nextApiUrl : "/api/play/next";

    submitJsonAction(
      card,
      apiUrl,
      {
        input_method: inputMethod,
        swipe_direction: direction,
      },
      "Карточка закрыта: " + progressLabel(direction, card) + ". Открывается следующая.",
      direction,
      options
    );
  }

  function validateOnboardingRegistration(card) {
    var nameInput = card ? card.querySelector("[data-participant-name]") : null;
    var participantName = nameInput ? nameInput.value.trim() : "";

    if (!participantName) {
      showCardError(card, "Введите имя или псевдоним, чтобы продолжить.");
      if (nameInput) {
        nameInput.focus();
      }
      return false;
    }

    if (participantName.length > 40) {
      showCardError(card, "Имя или псевдоним должны содержать не более 40 символов.");
      if (nameInput) {
        nameInput.focus();
      }
      return false;
    }

    clearCardError(card);
    return true;
  }

  function completeOnboardingRegistration(direction, inputMethod, options) {
    var card = getInteractiveCard();
    var nameInput = card ? card.querySelector("[data-participant-name]") : null;
    var apiUrl = card ? card.dataset.registerApiUrl : null;

    if (!validateOnboardingRegistration(card)) {
      return;
    }

    submitJsonAction(
      card,
      apiUrl || "/api/onboarding/register",
      {
        participant_name: nameInput.value.trim(),
        input_method: inputMethod,
        swipe_direction: direction,
      },
      "Помощник представлен. Открывается первая работа.",
      direction,
      options
    );
  }

  function submitCardDirection(direction, inputMethod, options) {
    var card = getInteractiveCard();
    if (!card) {
      return;
    }

    if (getCardMode(card) === "registration") {
      completeOnboardingRegistration(direction, inputMethod, options);
      return;
    }

    if (getCardMode(card) === "advance") {
      advanceFromResultCard(direction, inputMethod, options);
      return;
    }

    submitCurrentAnswer(direction === "left" ? "inaccuracy" : "correct", inputMethod, options);
  }

  function shouldIgnoreKeyboardEvent(event) {
    if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) {
      return true;
    }

    var target = event.target;
    if (!target || !target.tagName) {
      return false;
    }

    return ["INPUT", "TEXTAREA", "SELECT"].indexOf(target.tagName) !== -1;
  }

  function handleKeyboardAnswer(event) {
    if (isSubmitting || shouldIgnoreKeyboardEvent(event) || !getInteractiveCard()) {
      return;
    }

    if (event.key === "ArrowLeft") {
      event.preventDefault();
      submitCardDirection("left", "keyboard");
    }

    if (event.key === "ArrowRight") {
      event.preventDefault();
      submitCardDirection("right", "keyboard");
    }
  }

  function wireFormSubmissions() {
    getAnswerForms().forEach(function (form) {
      form.addEventListener("submit", function (event) {
        if (isSubmitting) {
          event.preventDefault();
          return;
        }

        if (window.fetch && event.submitter && event.submitter.value && getInteractiveCard()) {
          event.preventDefault();
          submitCurrentAnswer(event.submitter.value, "button");
          return;
        }

        isSubmitting = true;
        setAnswerControlsDisabled(true);

        if (event.submitter && event.submitter.value) {
          announce("Выбран вердикт: " + verdictLabel(event.submitter.value) + ". Ответ отправляется.");
        }
      });
    });
  }

  function wireRegistrationCard() {
    document.querySelectorAll("[data-registration-form]").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        submitCardDirection("right", "keyboard");
      });
    });

    document.querySelectorAll("[data-participant-name]").forEach(function (input) {
      input.addEventListener("input", function () {
        clearCardError(getInteractiveCard());
      });
    });
  }

  window.submitCardDirection = submitCardDirection;
  window.submitCurrentAnswer = submitCurrentAnswer;
  window.canSubmitCardDirection = function canSubmitCardDirection() {
    var card = getInteractiveCard();
    return !card || getCardMode(card) !== "registration" || validateOnboardingRegistration(card);
  };

  window.addEventListener("DOMContentLoaded", function () {
    liveRegion = document.querySelector("[data-live-region]");

    if (typeof window.initializeSwipePreview === "function") {
      window.initializeSwipePreview();
    }

    wireFormSubmissions();
    wireRegistrationCard();
    document.addEventListener("keydown", handleKeyboardAnswer);
  });
})();
