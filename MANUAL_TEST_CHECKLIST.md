# Manual Test Checklist

Use this after starting the app locally with:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Registration

- Open `/register`.
- Submit a valid name and optional team.
- Confirm the app redirects to the first work.
- Submit an empty or whitespace-only name and confirm the form shows a validation error.

## Question Card

- Confirm the card fits on a narrow mobile viewport around `320px`.
- Confirm the progress bar and work number match the current question.
- Confirm long text scrolls inside the card without hiding the action buttons.
- Confirm left and right labels remain visible while reading the question.

## Swipe

- Drag slightly left or right and release before the threshold.
- Confirm the card returns smoothly to the center.
- Drag far enough left and release.
- Confirm the card animates away and the result card loads.
- Repeat for a right swipe on another question.
- Confirm vertical scrolling inside long content does not accidentally trigger a horizontal swipe.

## Keyboard And Buttons

- On desktop, use `ArrowLeft` and confirm it submits “Есть неточность”.
- Use `ArrowRight` and confirm it submits “Ответ верный”.
- Use the fallback buttons and confirm they work without JS errors.
- After a submit starts, try pressing keys or clicking again and confirm the answer is not sent twice.

## Recovery

- Refresh while a question card is open and confirm the same question returns.
- Submit an answer, stay on the result card, refresh, and confirm the same result card returns.
- Advance through all 10 works and confirm the final screen appears.

## Review

- Confirm `/review` redirects to `/play` before the run is completed.
- Finish the run and confirm `/review` shows all reviewed works with verdicts and explanations.

## Accessibility

- Tab through the page and confirm visible focus appears on links, form inputs, buttons, and the question card.
- Confirm the question card can receive focus.
- Confirm status text is announced when an answer is submitted if a screen reader is active.

## Cross-Browser

- Test on iPhone Safari if available.
- Test on Android Chrome if available.
- Test on desktop Chrome or Safari.
